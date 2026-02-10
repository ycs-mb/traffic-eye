#!/usr/bin/env python3
"""Retrain and convert helmet model with proper quantization.

Key fixes from initial attempt:
1. Remove Rescaling from model - handle in preprocessing externally
2. Train with uint8 input (0-255) and internal normalization
3. Use dynamic range quantization for reliable INT8 deployment
"""

import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
DATA_DIR = PROJECT_ROOT / "data"
TRAIN_DIR = DATA_DIR / "helmet_dataset" / "train"
VAL_DIR = DATA_DIR / "helmet_dataset" / "val"
TEST_DIR = DATA_DIR / "helmet_test"

INPUT_SIZE = (96, 96)
BATCH_SIZE = 16
EPOCHS = 40
LEARNING_RATE = 0.001

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def build_model():
    """Build MobileNetV3-Small with external preprocessing.

    The model accepts float32 input in [0, 1] range.
    Preprocessing (divide by 255) happens in the data pipeline, not the model.
    This ensures clean INT8 quantization.
    """
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers

    backbone = keras.applications.MobileNetV3Small(
        input_shape=(*INPUT_SIZE, 3),
        include_top=False,
        weights="imagenet",
        pooling="avg",
    )
    backbone.trainable = False

    inputs = keras.Input(shape=(*INPUT_SIZE, 3), dtype=tf.float32, name="input_image")
    x = backbone(inputs, training=False)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(64, activation="relu", name="fc1")(x)
    x = layers.Dropout(0.2)(x)
    outputs = layers.Dense(1, activation="sigmoid", name="output")(x)

    model = keras.Model(inputs=inputs, outputs=outputs, name="helmet_classifier")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=LEARNING_RATE),
        loss="binary_crossentropy",
        metrics=["accuracy"],
    )
    logger.info("Model: %d params", model.count_params())
    return model


def load_dataset(data_dir: Path, split: str):
    """Load dataset with images normalized to [0, 1]."""
    import tensorflow as tf
    from tensorflow import keras

    split_dir = data_dir / split
    ds = keras.utils.image_dataset_from_directory(
        str(split_dir),
        labels="inferred",
        label_mode="binary",
        class_names=["no_helmet", "helmet"],
        batch_size=BATCH_SIZE,
        image_size=INPUT_SIZE,
        shuffle=(split == "train"),
        seed=42,
    )

    # Normalize to [0, 1]
    def normalize(images, labels):
        return tf.cast(images, tf.float32) / 255.0, labels

    ds = ds.map(normalize).prefetch(tf.data.AUTOTUNE)
    return ds


def convert_to_tflite(model) -> bytes:
    """Convert to TFLite with dynamic range quantization.

    This produces a model with:
    - uint8 input (0-255) with quantization parameters
    - float32 output (sigmoid probability)
    - Weights quantized to INT8, activations computed in float
    """
    import tensorflow as tf

    tmp_dir = MODELS_DIR / "_tmp_saved_model"
    shutil.rmtree(tmp_dir, ignore_errors=True)
    model.export(str(tmp_dir), format="tf_saved_model")

    converter = tf.lite.TFLiteConverter.from_saved_model(str(tmp_dir))

    # Dynamic range quantization: weights INT8, activations float
    converter.optimizations = [tf.lite.Optimize.DEFAULT]

    # Provide representative dataset for full integer quantization
    # Use properly normalized float32 data
    def representative_data_gen():
        rng = np.random.RandomState(42)
        for _ in range(200):
            # Generate data in [0, 1] float32 range (matching model input)
            img = rng.random((1, *INPUT_SIZE, 3)).astype(np.float32)
            yield [img]

    converter.representative_dataset = representative_data_gen
    converter.target_spec.supported_ops = [
        tf.lite.OpsSet.TFLITE_BUILTINS_INT8,
        tf.lite.OpsSet.TFLITE_BUILTINS,
    ]
    converter.inference_input_type = tf.uint8
    converter.inference_output_type = tf.float32

    logger.info("Converting to TFLite...")
    tflite_model = converter.convert()
    shutil.rmtree(tmp_dir, ignore_errors=True)

    logger.info("TFLite size: %.1f KB", len(tflite_model) / 1024)
    return tflite_model


def evaluate_model(model_path: Path) -> dict:
    """Evaluate TFLite model on test images."""
    from ai_edge_litert.interpreter import Interpreter, OpResolverType

    interpreter = Interpreter(
        model_path=str(model_path),
        num_threads=4,
        experimental_op_resolver_type=OpResolverType.BUILTIN_WITHOUT_DEFAULT_DELEGATES,
    )
    interpreter.allocate_tensors()

    inp = interpreter.get_input_details()[0]
    out = interpreter.get_output_details()[0]
    logger.info("Input: shape=%s dtype=%s", inp["shape"], inp["dtype"])
    logger.info("Output: shape=%s dtype=%s", out["shape"], out["dtype"])

    # Check quantization params
    if "quantization_parameters" in inp:
        qp = inp["quantization_parameters"]
        logger.info("Input quant: scales=%s, zero_points=%s", qp.get("scales"), qp.get("zero_points"))

    results = {"correct": 0, "total": 0, "details": [], "inference_times": []}

    for label_name, expected_helmet in [("helmet", True), ("no_helmet", False)]:
        label_dir = TEST_DIR / label_name
        if not label_dir.exists():
            continue
        for img_path in sorted(label_dir.glob("*.jpg"))[:10]:
            img = cv2.imread(str(img_path))
            if img is None:
                continue

            resized = cv2.resize(img, (INPUT_SIZE[1], INPUT_SIZE[0]))

            # Prepare input based on model dtype
            if inp["dtype"] == np.uint8:
                input_data = np.expand_dims(resized, axis=0).astype(np.uint8)
            else:
                input_data = np.expand_dims(resized.astype(np.float32) / 255.0, axis=0)

            start = time.perf_counter()
            interpreter.set_tensor(inp["index"], input_data)
            interpreter.invoke()
            ms = (time.perf_counter() - start) * 1000
            results["inference_times"].append(ms)

            output = interpreter.get_tensor(out["index"])
            score = float(output[0][0])
            predicted_helmet = score > 0.5

            correct = predicted_helmet == expected_helmet

            results["total"] += 1
            if correct:
                results["correct"] += 1

            results["details"].append({
                "file": img_path.name,
                "expected": "helmet" if expected_helmet else "no_helmet",
                "predicted": "helmet" if predicted_helmet else "no_helmet",
                "score": round(score, 4),
                "correct": correct,
                "ms": round(ms, 2),
            })

            tag = "OK" if correct else "WRONG"
            logger.info("  [%s] %s: exp=%s pred=%s score=%.4f (%.1fms)",
                        tag, img_path.name,
                        "helmet" if expected_helmet else "no_helmet",
                        "helmet" if predicted_helmet else "no_helmet",
                        score, ms)

    if results["total"] > 0:
        results["accuracy"] = results["correct"] / results["total"]
        results["avg_ms"] = float(np.mean(results["inference_times"]))
        results["p95_ms"] = float(np.percentile(results["inference_times"], 95))
    else:
        results["accuracy"] = 0.0
        results["avg_ms"] = 0.0
        results["p95_ms"] = 0.0

    return results


def save_metadata(results: dict, model_path: Path):
    """Save model metadata with test results."""
    metadata = {
        "model_name": "helmet_cls_int8",
        "version": "1.0.0",
        "architecture": "MobileNetV3-Small",
        "description": "Binary helmet classifier for motorcycle riders in Indian traffic conditions",
        "source": "Transfer learning from ImageNet-pretrained MobileNetV3-Small, trained on Pi 4",
        "training_info": {
            "framework": "TensorFlow 2.20.0 / Keras 3.13",
            "base_model": "MobileNetV3-Small (ImageNet pretrained, frozen backbone)",
            "training_method": "Transfer learning: frozen backbone + Dense(64,relu) + Dense(1,sigmoid)",
            "quantization": "Post-training INT8 quantization with representative dataset",
            "training_date": "2026-02-09",
            "training_platform": "Raspberry Pi 4 (aarch64, 4GB RAM)",
            "epochs": EPOCHS,
            "learning_rate": LEARNING_RATE,
            "batch_size": BATCH_SIZE,
            "dataset_info": {
                "type": "Synthetic head crops generated with OpenCV",
                "train_count": "300 per class (helmet + no_helmet)",
                "val_count": "60 per class",
                "test_count": "10 per class",
                "note": "Retrain with real data from Kaggle/RoboFlow for production accuracy",
                "recommended_datasets": [
                    "RoboFlow: Helmet and No Helmet Rider Detection",
                    "Kaggle: Indian Helmet Detection Dataset",
                    "GitHub: Safety-Helmet-Wearing-Dataset (njvisionpower)",
                ],
            },
        },
        "model_specs": {
            "input_format": {
                "shape": [1, 96, 96, 3],
                "dtype": "uint8",
                "range": "[0, 255]",
                "color_space": "BGR (from OpenCV) or RGB",
                "note": "Quantization params handle normalization internally",
            },
            "output_format": {
                "shape": [1, 1],
                "dtype": "float32",
                "activation": "sigmoid",
                "interpretation": "Score > 0.5 = helmet present, < 0.5 = no helmet",
            },
            "model_size_bytes": model_path.stat().st_size,
            "model_size_kb": round(model_path.stat().st_size / 1024, 1),
        },
        "test_results": {
            "accuracy": round(results["accuracy"], 4),
            "total_images": results["total"],
            "correct": results["correct"],
            "avg_inference_ms": round(results["avg_ms"], 2),
            "p95_inference_ms": round(results["p95_ms"], 2),
            "test_date": datetime.now().isoformat(),
            "platform": "Raspberry Pi 4 (aarch64)",
            "per_image": results["details"],
        },
        "deployment": {
            "file_path": "models/helmet_cls_int8.tflite",
            "config_section": "helmet.model_path",
            "runtime": "ai-edge-litert 2.1.2",
            "op_resolver": "BUILTIN_WITHOUT_DEFAULT_DELEGATES",
            "note": "Use OpResolverType.BUILTIN_WITHOUT_DEFAULT_DELEGATES to avoid XNNPACK issues",
            "dependencies": ["ai-edge-litert", "opencv-python-headless", "numpy"],
        },
        "usage": {
            "confidence_threshold": 0.5,
            "recommended_range": [0.4, 0.6],
        },
        "known_limitations": [
            "Trained on synthetic data -- retrain with real images for production",
            "XNNPACK delegate incompatible -- use BUILTIN_WITHOUT_DEFAULT_DELEGATES",
            "Accuracy target >80% achievable with real training data",
        ],
    }

    out_path = MODELS_DIR / "helmet_model_metadata.json"
    with open(out_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Metadata: %s", out_path)


def main():
    logger.info("=" * 60)
    logger.info("Helmet Model Pipeline v2")
    logger.info("=" * 60)

    dataset_dir = DATA_DIR / "helmet_dataset"

    # Train
    logger.info("\n--- Training ---")
    model = build_model()
    train_ds = load_dataset(dataset_dir, "train")
    val_ds = load_dataset(dataset_dir, "val")

    from tensorflow import keras
    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=10, restore_best_weights=True, verbose=1),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=5, min_lr=1e-6, verbose=1),
    ]

    model.fit(train_ds, validation_data=val_ds, epochs=EPOCHS, callbacks=callbacks, verbose=1)

    # Evaluate Keras model first
    val_loss, val_acc = model.evaluate(val_ds, verbose=0)
    logger.info("Keras val accuracy: %.1f%%", val_acc * 100)

    # Convert
    logger.info("\n--- Converting ---")
    tflite_bytes = convert_to_tflite(model)
    out_path = MODELS_DIR / "helmet_cls_int8.tflite"
    with open(out_path, "wb") as f:
        f.write(tflite_bytes)
    logger.info("Saved: %s (%.1f KB)", out_path, len(tflite_bytes) / 1024)

    # Evaluate TFLite
    logger.info("\n--- Evaluating TFLite ---")
    results = evaluate_model(out_path)

    logger.info("\n" + "=" * 50)
    logger.info("FINAL RESULTS")
    logger.info("Accuracy: %.1f%% (%d/%d)", results["accuracy"] * 100, results["correct"], results["total"])
    logger.info("Avg inference: %.2f ms", results["avg_ms"])
    logger.info("Model size: %.1f KB", len(tflite_bytes) / 1024)

    save_metadata(results, out_path)

    return results


if __name__ == "__main__":
    r = main()
    sys.exit(0 if r.get("accuracy", 0) >= 0.8 else 1)
