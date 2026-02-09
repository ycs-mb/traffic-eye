#!/usr/bin/env python3
"""Convert trained helmet model to TFLite with float16 quantization.

Float16 quantization:
- Reduces model size by ~50% vs float32
- No accuracy loss (unlike INT8)
- Works reliably with all op types including hard-swish
- Inference uses float16 where supported, falls back to float32
"""
import logging
import os
import shutil
import sys
import time
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
LR = 0.001

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def build_and_train():
    """Build and train MobileNetV3-Small."""
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

    inputs = keras.Input(shape=(*INPUT_SIZE, 3), dtype=tf.float32)
    x = backbone(inputs, training=False)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(64, activation="relu")(x)
    x = layers.Dropout(0.2)(x)
    outputs = layers.Dense(1, activation="sigmoid")(x)

    model = keras.Model(inputs=inputs, outputs=outputs)
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=LR),
        loss="binary_crossentropy",
        metrics=["accuracy"],
    )
    logger.info("Model: %d params", model.count_params())

    # Load datasets (normalized to [0, 1])
    def make_ds(split):
        ds = keras.utils.image_dataset_from_directory(
            str(DATA_DIR / "helmet_dataset" / split),
            labels="inferred", label_mode="binary",
            class_names=["no_helmet", "helmet"],
            batch_size=BATCH_SIZE, image_size=INPUT_SIZE,
            shuffle=(split == "train"), seed=42,
        )
        return ds.map(lambda x, y: (tf.cast(x, tf.float32) / 255.0, y)).prefetch(tf.data.AUTOTUNE)

    train_ds = make_ds("train")
    val_ds = make_ds("val")

    callbacks = [
        keras.callbacks.EarlyStopping(monitor="val_loss", patience=10, restore_best_weights=True),
        keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=5, min_lr=1e-6),
    ]
    model.fit(train_ds, validation_data=val_ds, epochs=EPOCHS, callbacks=callbacks, verbose=1)

    val_loss, val_acc = model.evaluate(val_ds, verbose=0)
    logger.info("Keras val: loss=%.4f acc=%.1f%%", val_loss, val_acc * 100)

    return model


def convert_float16(model) -> bytes:
    """Convert to TFLite with float16 quantization (no accuracy loss)."""
    import tensorflow as tf

    tmp_dir = MODELS_DIR / "_tmp_sm"
    shutil.rmtree(tmp_dir, ignore_errors=True)
    model.export(str(tmp_dir), format="tf_saved_model")

    converter = tf.lite.TFLiteConverter.from_saved_model(str(tmp_dir))
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    # Keep input/output as float32 for compatibility
    converter.inference_input_type = tf.float32
    converter.inference_output_type = tf.float32

    tflite_bytes = converter.convert()
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return tflite_bytes


def convert_dynamic_range(model) -> bytes:
    """Convert with dynamic range quantization (weights INT8, compute float32).

    This is the safest quantization - no representative dataset needed,
    no risk of accuracy collapse.
    """
    import tensorflow as tf

    tmp_dir = MODELS_DIR / "_tmp_sm2"
    shutil.rmtree(tmp_dir, ignore_errors=True)
    model.export(str(tmp_dir), format="tf_saved_model")

    converter = tf.lite.TFLiteConverter.from_saved_model(str(tmp_dir))
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    # No representative_dataset = dynamic range quantization
    # No inference_input_type override = float32 input

    tflite_bytes = converter.convert()
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return tflite_bytes


def evaluate(model_path: Path) -> dict:
    """Evaluate TFLite model."""
    from ai_edge_litert.interpreter import Interpreter, OpResolverType

    interpreter = Interpreter(
        model_path=str(model_path),
        num_threads=4,
        experimental_op_resolver_type=OpResolverType.BUILTIN_WITHOUT_DEFAULT_DELEGATES,
    )
    interpreter.allocate_tensors()

    inp = interpreter.get_input_details()[0]
    out = interpreter.get_output_details()[0]
    input_shape = tuple(inp["shape"])
    logger.info("Input: shape=%s dtype=%s", input_shape, inp["dtype"])
    logger.info("Output: shape=%s dtype=%s", tuple(out["shape"]), out["dtype"])

    results = {"correct": 0, "total": 0, "details": [], "times": []}
    scores_seen = set()

    for label, exp_helmet in [("helmet", True), ("no_helmet", False)]:
        d = TEST_DIR / label
        if not d.exists():
            continue
        for p in sorted(d.glob("*.jpg"))[:10]:
            img = cv2.imread(str(p))
            if img is None:
                continue
            resized = cv2.resize(img, (INPUT_SIZE[1], INPUT_SIZE[0]))

            if inp["dtype"] == np.float32:
                data = np.expand_dims(resized.astype(np.float32) / 255.0, axis=0)
            else:
                data = np.expand_dims(resized.astype(np.uint8), axis=0)

            start = time.perf_counter()
            interpreter.set_tensor(inp["index"], data)
            interpreter.invoke()
            ms = (time.perf_counter() - start) * 1000
            results["times"].append(ms)

            o = interpreter.get_tensor(out["index"])
            score = float(o[0][0])
            scores_seen.add(round(score, 4))
            pred = score > 0.5
            ok = pred == exp_helmet
            results["total"] += 1
            if ok:
                results["correct"] += 1
            results["details"].append({
                "file": p.name, "expected": label,
                "predicted": "helmet" if pred else "no_helmet",
                "score": round(score, 4), "correct": ok, "ms": round(ms, 2),
            })
            tag = "OK" if ok else "WRONG"
            logger.info("  [%s] %s: exp=%s pred=%s score=%.4f (%.1fms)",
                        tag, p.name, label,
                        "helmet" if pred else "no_helmet", score, ms)

    logger.info("Unique scores seen: %d (should be >1 for proper quantization)", len(scores_seen))

    if results["total"]:
        results["accuracy"] = results["correct"] / results["total"]
        results["avg_ms"] = float(np.mean(results["times"]))
        results["p95_ms"] = float(np.percentile(results["times"], 95))
    else:
        results["accuracy"] = 0
        results["avg_ms"] = 0
        results["p95_ms"] = 0
    return results


def main():
    logger.info("=" * 60)
    logger.info("Helmet Model - Float16/Dynamic Range Pipeline")
    logger.info("=" * 60)

    model = build_and_train()

    # Try float16 first (best accuracy preservation)
    logger.info("\n--- Converting (float16) ---")
    f16_bytes = convert_float16(model)
    f16_path = MODELS_DIR / "helmet_cls_f16.tflite"
    with open(f16_path, "wb") as f:
        f.write(f16_bytes)
    logger.info("Float16 model: %s (%.1f KB)", f16_path, len(f16_bytes) / 1024)

    # Also try dynamic range
    logger.info("\n--- Converting (dynamic range) ---")
    dr_bytes = convert_dynamic_range(model)
    dr_path = MODELS_DIR / "helmet_cls_dynrange.tflite"
    with open(dr_path, "wb") as f:
        f.write(dr_bytes)
    logger.info("Dynamic range model: %s (%.1f KB)", dr_path, len(dr_bytes) / 1024)

    # Evaluate both
    logger.info("\n--- Evaluating Float16 ---")
    f16_results = evaluate(f16_path)

    logger.info("\n--- Evaluating Dynamic Range ---")
    dr_results = evaluate(dr_path)

    # Pick the best
    logger.info("\n" + "=" * 50)
    logger.info("COMPARISON")
    logger.info("Float16:  accuracy=%.1f%% avg=%.1fms size=%.1fKB",
                f16_results["accuracy"] * 100, f16_results["avg_ms"], len(f16_bytes) / 1024)
    logger.info("DynRange: accuracy=%.1f%% avg=%.1fms size=%.1fKB",
                dr_results["accuracy"] * 100, dr_results["avg_ms"], len(dr_bytes) / 1024)

    # Deploy the best one as helmet_cls_int8.tflite
    if f16_results["accuracy"] >= dr_results["accuracy"]:
        best = f16_results
        best_path = f16_path
        best_bytes = f16_bytes
        quant_type = "float16"
    else:
        best = dr_results
        best_path = dr_path
        best_bytes = dr_bytes
        quant_type = "dynamic_range"

    deploy_path = MODELS_DIR / "helmet_cls_int8.tflite"
    shutil.copy2(best_path, deploy_path)
    logger.info("\nDeployed %s as %s (%.1f KB)", quant_type, deploy_path, len(best_bytes) / 1024)

    logger.info("ACCURACY: %.1f%% (%d/%d)", best["accuracy"] * 100, best["correct"], best["total"])
    logger.info("INFERENCE: avg=%.1fms p95=%.1fms", best["avg_ms"], best["p95_ms"])

    return best


if __name__ == "__main__":
    r = main()
    sys.exit(0 if r.get("accuracy", 0) >= 0.8 else 1)
