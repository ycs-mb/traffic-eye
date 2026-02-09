#!/usr/bin/env python3
"""Evaluate the helmet TFLite model on test images and update metadata."""
import json
import logging
import time
from pathlib import Path

import cv2
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
TEST_DIR = PROJECT_ROOT / "data" / "helmet_test"
MODEL_PATH = MODELS_DIR / "helmet_cls_int8.tflite"


def evaluate():
    from ai_edge_litert.interpreter import Interpreter, OpResolverType

    interpreter = Interpreter(
        model_path=str(MODEL_PATH),
        num_threads=4,
        experimental_op_resolver_type=OpResolverType.BUILTIN_WITHOUT_DEFAULT_DELEGATES,
    )
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]
    input_shape = tuple(input_details["shape"])

    logger.info("Model input: shape=%s dtype=%s", input_shape, input_details["dtype"])
    logger.info("Model output: shape=%s dtype=%s",
                tuple(output_details["shape"]), output_details["dtype"])

    results = {"correct": 0, "total": 0, "details": [], "inference_times": []}

    for label_name, expected_helmet in [("helmet", True), ("no_helmet", False)]:
        label_dir = TEST_DIR / label_name
        if not label_dir.exists():
            logger.warning("Missing: %s", label_dir)
            continue

        image_files = sorted(label_dir.glob("*.jpg")) + sorted(label_dir.glob("*.png"))
        for img_path in image_files[:10]:
            img = cv2.imread(str(img_path))
            if img is None:
                continue

            resized = cv2.resize(img, (input_shape[2], input_shape[1]))
            input_data = np.expand_dims(resized, axis=0).astype(np.uint8)

            start = time.perf_counter()
            interpreter.set_tensor(input_details["index"], input_data)
            interpreter.invoke()
            elapsed_ms = (time.perf_counter() - start) * 1000
            results["inference_times"].append(elapsed_ms)

            output = interpreter.get_tensor(output_details["index"])
            score = float(output[0][0])

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
                "  [%s] %s: expected=%s predicted=%s score=%.4f (%.1fms)",
                status, img_path.name,
                "helmet" if expected_helmet else "no_helmet",
                "helmet" if predicted_helmet else "no_helmet",
                score, elapsed_ms,
            )

    if results["total"] > 0:
        results["accuracy"] = results["correct"] / results["total"]
        results["avg_inference_ms"] = float(np.mean(results["inference_times"]))
        results["p95_inference_ms"] = float(np.percentile(results["inference_times"], 95))
    else:
        results["accuracy"] = 0.0
        results["avg_inference_ms"] = 0.0
        results["p95_inference_ms"] = 0.0

    logger.info("")
    logger.info("=" * 50)
    logger.info("RESULTS")
    logger.info("=" * 50)
    logger.info("Accuracy: %.1f%% (%d/%d)",
                results["accuracy"] * 100, results["correct"], results["total"])
    logger.info("Avg inference: %.2f ms", results["avg_inference_ms"])
    logger.info("P95 inference: %.2f ms", results["p95_inference_ms"])
    logger.info("Model size: %.1f KB", MODEL_PATH.stat().st_size / 1024)

    # Update metadata
    from datetime import datetime
    metadata = {
        "model_name": "helmet_cls_int8",
        "version": "1.0.0",
        "architecture": "MobileNetV3-Small",
        "description": "Binary helmet classifier for motorcycle riders in Indian traffic conditions",
        "source": "Transfer learning from ImageNet-pretrained MobileNetV3-Small",
        "training_info": {
            "framework": "TensorFlow 2.20.0 / Keras 3.13",
            "base_model": "MobileNetV3-Small (ImageNet pretrained)",
            "training_method": "Transfer learning with frozen backbone + custom classification head",
            "quantization": "Post-training INT8 quantization with representative dataset calibration",
            "training_date": "2026-02-09",
            "training_platform": "Raspberry Pi 4 (aarch64)",
            "epochs": 30,
            "learning_rate": 0.001,
            "batch_size": 16,
            "dataset": "Synthetic head crops (300 train + 60 val per class)",
            "data_augmentation": [
                "Random brightness variation",
                "Varied skin tones and backgrounds",
                "Multiple helmet colors and styles",
            ],
        },
        "model_specs": {
            "input_format": {
                "shape": [1, 96, 96, 3],
                "dtype": "uint8",
                "color_space": "BGR/RGB",
            },
            "output_format": {
                "shape": [1, 1],
                "dtype": "float32",
                "activation": "sigmoid",
                "interpretation": "Score > 0.5 = helmet present",
            },
            "model_size_bytes": MODEL_PATH.stat().st_size,
            "model_size_kb": round(MODEL_PATH.stat().st_size / 1024, 1),
        },
        "test_results": {
            "accuracy": round(results["accuracy"], 4),
            "total_test_images": results["total"],
            "correct_predictions": results["correct"],
            "avg_inference_ms": round(results["avg_inference_ms"], 2),
            "p95_inference_ms": round(results["p95_inference_ms"], 2),
            "test_date": datetime.now().isoformat(),
            "platform": "Raspberry Pi 4 (aarch64)",
            "details": results["details"],
        },
        "deployment": {
            "file_path": "models/helmet_cls_int8.tflite",
            "config_section": "helmet.model_path",
            "runtime": "ai-edge-litert 2.1.2",
            "op_resolver": "BUILTIN_WITHOUT_DEFAULT_DELEGATES (avoids XNNPACK issues)",
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
        "known_limitations": [
            "Trained on synthetic data - accuracy will improve with real helmet images",
            "Requires BUILTIN_WITHOUT_DEFAULT_DELEGATES op resolver (XNNPACK incompatible)",
            "May need retraining for specific regional helmet styles",
        ],
    }

    metadata_path = MODELS_DIR / "helmet_model_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Metadata saved to %s", metadata_path)

    return results


if __name__ == "__main__":
    evaluate()
