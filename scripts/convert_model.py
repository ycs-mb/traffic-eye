#!/usr/bin/env python3
"""Convert trained helmet model to TFLite INT8 quantized format.

This script converts a TensorFlow SavedModel to TFLite INT8 for edge deployment
on Raspberry Pi. It includes post-training quantization with representative dataset
calibration and validation checks.

Usage:
    # Convert from SavedModel
    python scripts/convert_model.py --model models/helmet_model_20260209_120000

    # Convert with custom representative dataset
    python scripts/convert_model.py --model models/helmet_model --calib-dir data/helmet_dataset/val

    # Convert and validate
    python scripts/convert_model.py --model models/helmet_model --validate

Output:
    - models/helmet_cls_int8.tflite (quantized model)
    - Validation report (if --validate flag is used)
"""

import argparse
import logging
from pathlib import Path
from typing import Generator, Optional

import numpy as np
import tensorflow as tf
from tensorflow import keras

# Constants
INPUT_SIZE = (96, 96)
NUM_CALIBRATION_SAMPLES = 100
OUTPUT_FILENAME = "helmet_cls_int8.tflite"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert helmet model to TFLite INT8",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--model",
        type=Path,
        required=True,
        help="Path to trained TensorFlow SavedModel directory"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=f"Output path for TFLite model (default: models/{OUTPUT_FILENAME})"
    )
    parser.add_argument(
        "--calib-dir",
        type=Path,
        default=None,
        help="Directory with calibration images (default: use random data)"
    )
    parser.add_argument(
        "--num-calib",
        type=int,
        default=NUM_CALIBRATION_SAMPLES,
        help=f"Number of calibration samples (default: {NUM_CALIBRATION_SAMPLES})"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate converted model after conversion"
    )
    return parser.parse_args()


def validate_model_path(model_path: Path) -> None:
    """Validate that model path exists and is valid."""
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    # Check for SavedModel format
    saved_model_pb = model_path / "saved_model.pb"
    keras_metadata = model_path / "keras_metadata.pb"

    if not saved_model_pb.exists() and not keras_metadata.exists():
        raise ValueError(
            f"Invalid model directory: {model_path}\n"
            f"Expected TensorFlow SavedModel or Keras format."
        )

    logger.info(f"Validated model path: {model_path}")


def load_calibration_images(
    calib_dir: Optional[Path],
    num_samples: int,
) -> list:
    """Load calibration images from directory or generate random data."""
    if calib_dir and calib_dir.exists():
        logger.info(f"Loading calibration images from {calib_dir}")

        image_paths = list(calib_dir.rglob("*.jpg")) + list(calib_dir.rglob("*.png"))

        if not image_paths:
            logger.warning(f"No images found in {calib_dir}, using random data")
            return generate_random_calibration_data(num_samples)

        # Sample random images
        import random
        selected_paths = random.sample(image_paths, min(num_samples, len(image_paths)))

        images = []
        for path in selected_paths:
            img = keras.utils.load_img(path, target_size=INPUT_SIZE)
            img_array = keras.utils.img_to_array(img)
            images.append(img_array.astype(np.uint8))

        logger.info(f"Loaded {len(images)} calibration images")
        return images

    else:
        logger.warning("No calibration directory provided, using random data")
        return generate_random_calibration_data(num_samples)


def generate_random_calibration_data(num_samples: int) -> list:
    """Generate random calibration data for quantization."""
    logger.info(f"Generating {num_samples} random calibration samples")

    images = []
    for _ in range(num_samples):
        # Generate random RGB image
        img = np.random.randint(0, 256, (*INPUT_SIZE, 3), dtype=np.uint8)
        images.append(img)

    return images


def create_representative_dataset(
    calibration_images: list,
) -> Generator[list, None, None]:
    """Create representative dataset generator for quantization."""
    def representative_data_gen():
        for image in calibration_images:
            # Expand dimensions to match model input shape
            yield [np.expand_dims(image, axis=0)]

    return representative_data_gen


def convert_to_tflite_int8(
    model_path: Path,
    calibration_images: list,
) -> bytes:
    """Convert model to TFLite INT8 quantized format."""
    logger.info("Loading model for conversion...")

    # Create converter
    converter = tf.lite.TFLiteConverter.from_saved_model(str(model_path))

    # Configure INT8 quantization
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = create_representative_dataset(calibration_images)

    # Full integer quantization
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.uint8
    converter.inference_output_type = tf.float32  # Keep output as float for precision

    logger.info("Converting to TFLite INT8 (this may take a few minutes)...")
    tflite_model = converter.convert()

    logger.info(f"Conversion complete! Model size: {len(tflite_model) / 1024:.1f} KB")

    return tflite_model


def get_model_info(tflite_model_path: Path) -> dict:
    """Extract model information from TFLite file."""
    try:
        import tflite_runtime.interpreter as tflite
    except ImportError:
        import tensorflow.lite as tflite

    interpreter = tflite.Interpreter(model_path=str(tflite_model_path))
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]

    info = {
        "input_shape": list(input_details["shape"]),
        "input_dtype": str(input_details["dtype"]),
        "output_shape": list(output_details["shape"]),
        "output_dtype": str(output_details["dtype"]),
    }

    return info


def validate_tflite_model(
    tflite_model_path: Path,
    original_model_path: Path,
    test_images: list,
) -> None:
    """Validate TFLite model against original model."""
    logger.info("Validating TFLite model...")

    # Load TFLite interpreter
    try:
        import tflite_runtime.interpreter as tflite
    except ImportError:
        import tensorflow.lite as tflite

    interpreter = tflite.Interpreter(model_path=str(tflite_model_path))
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]

    # Load original model
    original_model = keras.models.load_model(original_model_path)

    # Test on sample images
    differences = []

    for i, img in enumerate(test_images[:10]):  # Test on first 10 images
        # TFLite inference
        input_data = np.expand_dims(img, axis=0)
        interpreter.set_tensor(input_details["index"], input_data)
        interpreter.invoke()
        tflite_output = interpreter.get_tensor(output_details["index"])[0][0]

        # Original model inference
        original_output = original_model.predict(input_data, verbose=0)[0][0]

        diff = abs(tflite_output - original_output)
        differences.append(diff)

        logger.debug(
            f"Sample {i+1}: Original={original_output:.4f}, "
            f"TFLite={tflite_output:.4f}, Diff={diff:.4f}"
        )

    avg_diff = np.mean(differences)
    max_diff = np.max(differences)

    logger.info("Validation complete:")
    logger.info(f"  Average difference: {avg_diff:.6f}")
    logger.info(f"  Maximum difference: {max_diff:.6f}")

    if max_diff > 0.1:
        logger.warning(
            f"Large quantization error detected (max diff: {max_diff:.6f}). "
            f"Consider using more calibration samples or check model compatibility."
        )
    else:
        logger.info("Quantization quality: GOOD")


def main() -> None:
    """Main conversion pipeline."""
    args = parse_args()

    # Validate input model
    validate_model_path(args.model)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_path = Path("models") / OUTPUT_FILENAME

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load calibration data
    calibration_images = load_calibration_images(args.calib_dir, args.num_calib)

    # Convert to TFLite INT8
    tflite_model = convert_to_tflite_int8(args.model, calibration_images)

    # Save TFLite model
    with open(output_path, "wb") as f:
        f.write(tflite_model)

    logger.info(f"TFLite model saved to: {output_path}")

    # Display model info
    model_info = get_model_info(output_path)
    logger.info("Model Info:")
    logger.info(f"  Input:  shape={model_info['input_shape']}, dtype={model_info['input_dtype']}")
    logger.info(f"  Output: shape={model_info['output_shape']}, dtype={model_info['output_dtype']}")

    # Validate if requested
    if args.validate:
        validate_tflite_model(output_path, args.model, calibration_images)

    logger.info("Conversion complete!")
    logger.info("\nTo use this model, update your config:")
    logger.info("  helmet:")
    logger.info(f"    model_path: {output_path}")
    logger.info("    enabled: true")


if __name__ == "__main__":
    main()
