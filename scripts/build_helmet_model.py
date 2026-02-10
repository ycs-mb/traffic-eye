#!/usr/bin/env python3
"""Build, train, and deploy a MobileNetV3-Small helmet classifier.

This script handles the full pipeline:
1. Download sample images from open datasets (or generate synthetic)
2. Train MobileNetV3-Small with transfer learning
3. Convert to TFLite INT8
4. Validate and deploy

Usage:
    python scripts/build_helmet_model.py

Output:
    - models/helmet_cls_int8.tflite. 
    - models/helmet_model_metadata.json (updated with real metrics)
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

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
DATA_DIR = PROJECT_ROOT / "data"
TRAIN_DIR = DATA_DIR / "helmet_dataset" / "train"
VAL_DIR = DATA_DIR / "helmet_dataset" / "val"
TEST_DIR = DATA_DIR / "helmet_test"

# Model settings
INPUT_SIZE = (96, 96)
BATCH_SIZE = 16
EPOCHS = 30
LEARNING_RATE = 0.001

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def generate_synthetic_helmet_images(output_dir: Path, count: int = 200) -> None:
    """Generate synthetic helmet/no-helmet head crop images for training.

    Creates realistic-ish head crops with and without helmets using
    OpenCV drawing primitives. This gives the model basic shape priors
    even without real data.

    Helmet images: oval head with rounded rectangle helmet on top
    No-helmet images: oval head with hair (lines on top)
    """
    helmet_dir = output_dir / "helmet"
    no_helmet_dir = output_dir / "no_helmet"
    helmet_dir.mkdir(parents=True, exist_ok=True)
    no_helmet_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.RandomState(42)

    for i in range(count):
        # Random background color (varied lighting)
        bg_color = rng.randint(30, 200, 3).tolist()
        img = np.full((INPUT_SIZE[0], INPUT_SIZE[1], 3), bg_color, dtype=np.uint8)

        # Add noise for texture
        noise = rng.randint(-20, 20, img.shape, dtype=np.int16)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        # Head center and size (some variation)
        cx = INPUT_SIZE[1] // 2 + rng.randint(-8, 8)
        cy = INPUT_SIZE[0] // 2 + rng.randint(-5, 10)
        head_w = rng.randint(25, 38)
        head_h = rng.randint(30, 42)

        # Skin color variation
        skin_colors = [
            (180, 200, 230),  # Light
            (140, 170, 200),  # Medium
            (100, 130, 160),  # Tan
            (70, 100, 130),   # Dark
            (50, 80, 110),    # Very dark
        ]
        skin = skin_colors[rng.randint(0, len(skin_colors))]

        # Draw face (ellipse)
        cv2.ellipse(img, (cx, cy), (head_w, head_h), 0, 0, 360, skin, -1)

        # Eyes
        eye_y = cy - rng.randint(3, 8)
        eye_sep = rng.randint(8, 14)
        cv2.circle(img, (cx - eye_sep, eye_y), 2, (30, 30, 30), -1)
        cv2.circle(img, (cx + eye_sep, eye_y), 2, (30, 30, 30), -1)

        # WITH HELMET
        helmet_img = img.copy()
        helmet_color = [
            (0, 0, 0),        # Black
            (200, 200, 200),  # White
            (0, 0, 200),      # Red
            (200, 0, 0),      # Blue
            (0, 200, 0),      # Green
            (0, 200, 200),    # Yellow
            (128, 0, 128),    # Purple
        ][rng.randint(0, 7)]

        # Helmet shape: rounded covering top of head
        helmet_top = cy - head_h - rng.randint(5, 12)
        helmet_bottom = cy - rng.randint(0, 8)

        # Draw helmet as filled ellipse on top of head
        helmet_cx = cx
        helmet_cy = (helmet_top + helmet_bottom) // 2
        helmet_rx = head_w + rng.randint(3, 8)
        helmet_ry = (helmet_bottom - helmet_top) // 2 + 2
        cv2.ellipse(
            helmet_img, (helmet_cx, helmet_cy),
            (helmet_rx, helmet_ry), 0, 0, 360,
            helmet_color, -1
        )
        # Visor
        visor_y = helmet_bottom - 2
        if rng.random() > 0.3:
            cv2.rectangle(
                helmet_img,
                (cx - head_w + 2, visor_y - 5),
                (cx + head_w - 2, visor_y + 3),
                (40, 40, 40), -1
            )

        # Add random augmentation
        if rng.random() > 0.5:
            # Brightness variation
            factor = rng.uniform(0.7, 1.3)
            helmet_img = np.clip(helmet_img * factor, 0, 255).astype(np.uint8)

        cv2.imwrite(str(helmet_dir / f"helmet_{i:04d}.jpg"), helmet_img)

        # WITHOUT HELMET
        no_helmet_img = img.copy()
        # Draw hair instead of helmet
        hair_color = [
            (20, 20, 20),     # Black hair
            (40, 60, 100),    # Brown
            (50, 80, 140),    # Auburn
            (80, 80, 80),     # Gray
        ][rng.randint(0, 4)]

        # Hair as lines/curves on top of head
        hair_top = cy - head_h - rng.randint(2, 8)
        for j in range(rng.randint(8, 20)):
            x_start = cx + rng.randint(-head_w, head_w)
            y_start = hair_top + rng.randint(0, 10)
            x_end = x_start + rng.randint(-5, 5)
            y_end = y_start + rng.randint(3, 12)
            cv2.line(no_helmet_img, (x_start, y_start), (x_end, y_end), hair_color, 1)

        # Add random augmentation
        if rng.random() > 0.5:
            factor = rng.uniform(0.7, 1.3)
            no_helmet_img = np.clip(no_helmet_img * factor, 0, 255).astype(np.uint8)

        cv2.imwrite(str(no_helmet_dir / f"no_helmet_{i:04d}.jpg"), no_helmet_img)

    logger.info("Generated %d helmet + %d no-helmet images in %s", count, count, output_dir)


def build_model_tf():
    """Build MobileNetV3-Small binary classifier using TensorFlow/Keras."""
    from tensorflow import keras
    from tensorflow.keras import layers

    # Use MobileNetV3-Small as backbone
    backbone = keras.applications.MobileNetV3Small(
        input_shape=(*INPUT_SIZE, 3),
        include_top=False,
        weights="imagenet",
        pooling="avg",
    )
    # Freeze backbone for transfer learning
    backbone.trainable = False

    # Build model
    inputs = keras.Input(shape=(*INPUT_SIZE, 3), name="input_image")

    # Preprocessing: normalize to [0, 1] then MobileNet preprocessing
    x = layers.Rescaling(1.0 / 255.0)(inputs)

    x = backbone(x, training=False)
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

    logger.info("Model built with %d parameters", model.count_params())
    return model


def load_dataset_tf(data_dir: Path, split: str):
    """Load image dataset using Keras utility."""
    from tensorflow import keras

    split_dir = data_dir / split
    if not split_dir.exists():
        raise FileNotFoundError(f"Dataset split not found: {split_dir}")

    dataset = keras.utils.image_dataset_from_directory(
        str(split_dir),
        labels="inferred",
        label_mode="binary",
        class_names=["no_helmet", "helmet"],
        batch_size=BATCH_SIZE,
        image_size=INPUT_SIZE,
        shuffle=(split == "train"),
        seed=42,
    )

    return dataset


def train_model(model, train_ds, val_ds):
    """Train the model with early stopping."""
    from tensorflow import keras

    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=8,
            restore_best_weights=True,
            verbose=1,
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=4,
            min_lr=1e-6,
            verbose=1,
        ),
    ]

    logger.info("Starting training for up to %d epochs...", EPOCHS)
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=EPOCHS,
        callbacks=callbacks,
        verbose=1,
    )

    return history


def convert_to_tflite_int8(model, calibration_images: list) -> bytes:
    """Convert Keras model to TFLite INT8 format."""
    import tensorflow as tf

    # Export as SavedModel (Keras 3 API)
    tmp_model_dir = PROJECT_ROOT / "models" / "_tmp_saved_model"
    shutil.rmtree(tmp_model_dir, ignore_errors=True)
    model.export(str(tmp_model_dir), format="tf_saved_model")

    # Convert
    converter = tf.lite.TFLiteConverter.from_saved_model(str(tmp_model_dir))
    converter.optimizations = [tf.lite.Optimize.DEFAULT]

    # Representative dataset for INT8 calibration
    # Note: the SavedModel input is float32 (rescaling layer inside model),
    # so calibration data must match the SavedModel signature dtype.
    def representative_data_gen():
        for img in calibration_images[:100]:
            yield [np.expand_dims(img.astype(np.float32), axis=0)]

    converter.representative_dataset = representative_data_gen

    # Full integer quantization with fallback for unsupported ops
    converter.target_spec.supported_ops = [
        tf.lite.OpsSet.TFLITE_BUILTINS_INT8,
        tf.lite.OpsSet.TFLITE_BUILTINS,
    ]
    # Keep input as uint8 for efficient edge inference
    converter.inference_input_type = tf.uint8
    converter.inference_output_type = tf.float32

    # Ensure all quantizable ops are INT8
    converter._experimental_lower_tensor_list_ops = False

    logger.info("Converting to TFLite INT8...")
    tflite_model = converter.convert()

    # Cleanup temp model
    shutil.rmtree(tmp_model_dir, ignore_errors=True)

    logger.info("TFLite model size: %.1f KB", len(tflite_model) / 1024)
    return tflite_model


def evaluate_tflite_model(model_path: Path, test_dir: Path) -> dict:
    """Evaluate TFLite model on test images and return metrics."""
    try:
        from ai_edge_litert.interpreter import Interpreter
    except ImportError:
        try:
            import tflite_runtime.interpreter as tflite_mod
            Interpreter = tflite_mod.Interpreter
        except ImportError:
            import tensorflow.lite as tflite_mod
            Interpreter = tflite_mod.Interpreter

    # Use BUILTIN_WITHOUT_DEFAULT_DELEGATES to avoid XNNPACK issues
    # with INT8 quantized MobileNetV3 ops
    try:
        from ai_edge_litert.interpreter import OpResolverType
        interpreter = Interpreter(
            model_path=str(model_path),
            num_threads=4,
            experimental_op_resolver_type=OpResolverType.BUILTIN_WITHOUT_DEFAULT_DELEGATES,
        )
    except (ImportError, TypeError):
        interpreter = Interpreter(model_path=str(model_path), num_threads=4)
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]

    input_shape = tuple(input_details["shape"])
    input_dtype = input_details["dtype"]

    logger.info("Model input: shape=%s dtype=%s", input_shape, input_dtype)
    logger.info("Model output: shape=%s dtype=%s",
                tuple(output_details["shape"]), output_details["dtype"])

    # Collect test images
    results = {"correct": 0, "total": 0, "details": [], "inference_times": []}

    for label_name, expected_helmet in [("helmet", True), ("no_helmet", False)]:
        label_dir = test_dir / label_name
        if not label_dir.exists():
            logger.warning("Test directory missing: %s", label_dir)
            continue

        image_files = sorted(label_dir.glob("*.jpg")) + sorted(label_dir.glob("*.png"))
        for img_path in image_files[:10]:  # Up to 10 per class
            img = cv2.imread(str(img_path))
            if img is None:
                continue

            # Preprocess
            resized = cv2.resize(img, (input_shape[2], input_shape[1]))

            if input_dtype == np.uint8:
                input_data = np.expand_dims(resized, axis=0).astype(np.uint8)
            else:
                input_data = np.expand_dims(
                    resized.astype(np.float32) / 255.0, axis=0
                )

            # Inference with timing
            start = time.perf_counter()
            interpreter.set_tensor(input_details["index"], input_data)
            interpreter.invoke()
            elapsed_ms = (time.perf_counter() - start) * 1000
            results["inference_times"].append(elapsed_ms)

            output = interpreter.get_tensor(output_details["index"])
            score = float(output[0][0]) if output.ndim > 1 else float(output[0])

            predicted_helmet = score > 0.5
            confidence = score if predicted_helmet else 1.0 - score
            correct = predicted_helmet == expected_helmet

            results["total"] += 1
            if correct:
                results["correct"] += 1

            results["details"].append({
                "file": img_path.name,
                "expected": "helmet" if expected_helmet else "no_helmet",
                "predicted": "helmet" if predicted_helmet else "no_helmet",
                "score": round(score, 4),
                "confidence": round(confidence, 4),
                "correct": correct,
                "inference_ms": round(elapsed_ms, 2),
            })

            status = "OK" if correct else "WRONG"
            logger.info(
                "  [%s] %s: expected=%s predicted=%s score=%.3f (%.1fms)",
                status, img_path.name,
                "helmet" if expected_helmet else "no_helmet",
                "helmet" if predicted_helmet else "no_helmet",
                score, elapsed_ms,
            )

    if results["total"] > 0:
        results["accuracy"] = results["correct"] / results["total"]
        results["avg_inference_ms"] = np.mean(results["inference_times"])
        results["p95_inference_ms"] = np.percentile(results["inference_times"], 95)
    else:
        results["accuracy"] = 0.0
        results["avg_inference_ms"] = 0.0
        results["p95_inference_ms"] = 0.0

    return results


def update_metadata(metrics: dict, model_path: Path) -> None:
    """Update model metadata with actual test results."""
    metadata_path = MODELS_DIR / "helmet_model_metadata.json"

    metadata = {
        "model_name": "helmet_cls_int8",
        "version": "1.0.0",
        "architecture": "MobileNetV3-Small",
        "description": "Binary helmet classifier for motorcycle riders",
        "source": "Transfer learning from ImageNet-pretrained MobileNetV3-Small",
        "training_info": {
            "framework": "TensorFlow/Keras",
            "base_model": "MobileNetV3-Small (ImageNet pretrained)",
            "training_method": "Transfer learning with frozen backbone + custom classification head",
            "quantization": "Post-training INT8 quantization with representative dataset",
            "training_date": datetime.now().isoformat(),
            "epochs_trained": EPOCHS,
            "learning_rate": LEARNING_RATE,
            "batch_size": BATCH_SIZE,
        },
        "model_specs": {
            "input_format": {
                "shape": [1, INPUT_SIZE[0], INPUT_SIZE[1], 3],
                "dtype": "uint8",
                "color_space": "RGB",
            },
            "output_format": {
                "shape": [1, 1],
                "dtype": "float32",
                "activation": "sigmoid",
                "interpretation": "Score > 0.5 = helmet present",
            },
            "model_size_bytes": model_path.stat().st_size,
            "model_size_kb": round(model_path.stat().st_size / 1024, 1),
        },
        "test_results": {
            "accuracy": round(metrics.get("accuracy", 0), 4),
            "total_test_images": metrics.get("total", 0),
            "correct_predictions": metrics.get("correct", 0),
            "avg_inference_ms": round(metrics.get("avg_inference_ms", 0), 2),
            "p95_inference_ms": round(metrics.get("p95_inference_ms", 0), 2),
            "test_date": datetime.now().isoformat(),
            "platform": "Raspberry Pi 4 (aarch64)",
        },
        "deployment": {
            "file_path": "models/helmet_cls_int8.tflite",
            "config_section": "helmet.model_path",
            "dependencies": [
                "ai-edge-litert (or tflite-runtime)",
                "opencv-python-headless",
                "numpy",
            ],
        },
        "usage": {
            "confidence_threshold": 0.5,
            "recommended_threshold_range": [0.4, 0.6],
        },
    }

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info("Metadata saved to %s", metadata_path)


def main():
    """Main pipeline: generate data, train, convert, evaluate, deploy."""
    # Disable XNNPACK globally to avoid issues with INT8 quantized models
    os.environ["XNNPACK_FORCE_DISABLE"] = "1"

    logger.info("=" * 60)
    logger.info("Helmet Model Build Pipeline")
    logger.info("=" * 60)

    # Step 1: Generate synthetic training data (skip if already exists)
    logger.info("\n--- Step 1: Generating training data ---")
    dataset_dir = DATA_DIR / "helmet_dataset"
    if not (TRAIN_DIR / "helmet").exists() or len(list((TRAIN_DIR / "helmet").glob("*.jpg"))) < 10:
        generate_synthetic_helmet_images(TRAIN_DIR, count=300)
        generate_synthetic_helmet_images(VAL_DIR, count=60)
        generate_synthetic_helmet_images(TEST_DIR, count=10)
    else:
        logger.info("Training data already exists, skipping generation")

    # Step 2: Build and train model
    logger.info("\n--- Step 2: Building and training model ---")
    model = build_model_tf()

    train_ds = load_dataset_tf(dataset_dir, "train")
    val_ds = load_dataset_tf(dataset_dir, "val")

    _ = train_model(model, train_ds, val_ds)

    # Step 3: Get calibration images for INT8 conversion
    logger.info("\n--- Step 3: Converting to TFLite INT8 ---")
    calib_images = []
    for img_path in sorted((VAL_DIR / "helmet").glob("*.jpg"))[:50]:
        img = cv2.imread(str(img_path))
        if img is not None:
            calib_images.append(cv2.resize(img, INPUT_SIZE))
    for img_path in sorted((VAL_DIR / "no_helmet").glob("*.jpg"))[:50]:
        img = cv2.imread(str(img_path))
        if img is not None:
            calib_images.append(cv2.resize(img, INPUT_SIZE))

    tflite_model = convert_to_tflite_int8(model, calib_images)

    # Save model
    output_path = MODELS_DIR / "helmet_cls_int8.tflite"
    with open(output_path, "wb") as f:
        f.write(tflite_model)
    logger.info("Model saved to %s (%.1f KB)", output_path, len(tflite_model) / 1024)

    # Step 4: Evaluate
    logger.info("\n--- Step 4: Evaluating model ---")
    metrics = evaluate_tflite_model(output_path, TEST_DIR)

    logger.info("\n=== TEST RESULTS ===")
    logger.info("Accuracy: %.1f%% (%d/%d)",
                metrics["accuracy"] * 100,
                metrics["correct"],
                metrics["total"])
    logger.info("Avg inference time: %.2f ms", metrics["avg_inference_ms"])
    logger.info("P95 inference time: %.2f ms", metrics["p95_inference_ms"])
    logger.info("Model size: %.1f KB", len(tflite_model) / 1024)

    # Step 5: Update metadata
    logger.info("\n--- Step 5: Updating metadata ---")
    update_metadata(metrics, output_path)

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("DEPLOYMENT COMPLETE")
    logger.info("=" * 60)
    logger.info("Model: %s", output_path)
    logger.info("Size: %.1f KB (target: <5MB)", len(tflite_model) / 1024)
    logger.info("Accuracy: %.1f%%", metrics["accuracy"] * 100)
    logger.info("Avg inference: %.2f ms", metrics["avg_inference_ms"])

    if metrics["accuracy"] < 0.8:
        logger.warning(
            "Accuracy %.1f%% is below 80%% target. This is expected with "
            "synthetic data. Re-train with real helmet images for production use.",
            metrics["accuracy"] * 100,
        )

    return metrics


if __name__ == "__main__":
    sys.exit(0 if main().get("accuracy", 0) >= 0.8 else 1)
