#!/usr/bin/env python3
"""Train a MobileNetV3-Small helmet detection classifier.

This script trains a binary helmet classifier optimized for deployment on Raspberry Pi.
The model is designed to classify head crops from motorcycle riders in Indian traffic.

Usage:
    # Train from scratch
    python scripts/train_helmet.py --data-dir data/helmet_dataset --epochs 50

    # Resume training from checkpoint
    python scripts/train_helmet.py --data-dir data/helmet_dataset --resume models/helmet_model_v1

    # Fine-tune with custom learning rate
    python scripts/train_helmet.py --data-dir data/helmet_dataset --lr 0.0001 --epochs 20

Dataset structure expected:
    data_dir/
    ├── train/
    │   ├── helmet/      # Images with helmet
    │   └── no_helmet/   # Images without helmet
    └── val/
        ├── helmet/
        └── no_helmet/
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path


import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

# Constants
INPUT_SIZE = (96, 96)
BATCH_SIZE = 32
DEFAULT_EPOCHS = 50
DEFAULT_LR = 0.001
CONFIDENCE_THRESHOLD = 0.5

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Train MobileNetV3-Small helmet classifier",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="Path to dataset directory (must contain train/ and val/ subdirs)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("models"),
        help="Output directory for trained model (default: models/)"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=DEFAULT_EPOCHS,
        help=f"Number of training epochs (default: {DEFAULT_EPOCHS})"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"Batch size (default: {BATCH_SIZE})"
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=DEFAULT_LR,
        help=f"Learning rate (default: {DEFAULT_LR})"
    )
    parser.add_argument(
        "--resume",
        type=Path,
        help="Resume training from saved model checkpoint"
    )
    parser.add_argument(
        "--augment",
        action="store_true",
        default=True,
        help="Enable data augmentation (default: True)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    return parser.parse_args()


def set_random_seed(seed: int) -> None:
    """Set random seeds for reproducibility."""
    tf.random.set_seed(seed)
    logger.info(f"Random seed set to {seed}")


def validate_dataset_structure(data_dir: Path) -> None:
    """Validate that dataset has required structure."""
    required_dirs = [
        data_dir / "train" / "helmet",
        data_dir / "train" / "no_helmet",
        data_dir / "val" / "helmet",
        data_dir / "val" / "no_helmet",
    ]

    for dir_path in required_dirs:
        if not dir_path.exists():
            raise FileNotFoundError(
                f"Required directory not found: {dir_path}\n"
                f"See script docstring for expected dataset structure."
            )

        num_files = len(list(dir_path.glob("*.jpg")) + list(dir_path.glob("*.png")))
        if num_files == 0:
            logger.warning(f"No images found in {dir_path}")
        else:
            logger.info(f"Found {num_files} images in {dir_path.name}")


def create_data_augmentation() -> keras.Sequential:
    """Create data augmentation pipeline for training robustness."""
    return keras.Sequential([
        layers.RandomFlip("horizontal"),
        layers.RandomRotation(0.1),  # ±10% rotation
        layers.RandomZoom(0.1),      # ±10% zoom
        layers.RandomContrast(0.2),  # ±20% contrast
        layers.RandomBrightness(0.2), # ±20% brightness
    ], name="data_augmentation")


def create_preprocessing() -> keras.Sequential:
    """Create preprocessing pipeline for MobileNetV3."""
    return keras.Sequential([
        layers.Rescaling(1./255),
        layers.Normalization(mean=[0.485, 0.456, 0.406],
                           variance=[0.229**2, 0.224**2, 0.225**2]),
    ], name="preprocessing")


def build_model(use_augmentation: bool = True) -> keras.Model:
    """Build MobileNetV3-Small classifier with custom head."""
    inputs = keras.Input(shape=(*INPUT_SIZE, 3), name="input_image")

    # Data augmentation (training only)
    x = inputs
    if use_augmentation:
        x = create_data_augmentation()(x, training=True)

    # Preprocessing
    x = create_preprocessing()(x)

    # MobileNetV3-Small backbone (pretrained on ImageNet)
    backbone = keras.applications.MobileNetV3Small(
        input_shape=(*INPUT_SIZE, 3),
        include_top=False,
        weights="imagenet",
        pooling="avg",
    )
    x = backbone(x, training=False)  # Freeze backbone initially

    # Classification head
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(64, activation="relu", name="fc1")(x)
    x = layers.Dropout(0.2)(x)
    outputs = layers.Dense(1, activation="sigmoid", name="output")(x)

    model = keras.Model(inputs=inputs, outputs=outputs, name="helmet_classifier")
    logger.info(f"Model created with {model.count_params():,} parameters")

    return model


def load_dataset(
    data_dir: Path,
    split: str,
    batch_size: int,
) -> tf.data.Dataset:
    """Load and prepare image dataset from directory."""
    split_dir = data_dir / split

    dataset = keras.utils.image_dataset_from_directory(
        split_dir,
        labels="inferred",
        label_mode="binary",
        class_names=["helmet", "no_helmet"],
        batch_size=batch_size,
        image_size=INPUT_SIZE,
        shuffle=(split == "train"),
        seed=42,
    )

    # Optimize performance
    dataset = dataset.prefetch(tf.data.AUTOTUNE)

    return dataset


def create_callbacks(output_dir: Path, model_name: str) -> list:
    """Create training callbacks for monitoring and checkpointing."""
    checkpoint_path = output_dir / f"{model_name}_checkpoint.keras"

    callbacks = [
        keras.callbacks.ModelCheckpoint(
            checkpoint_path,
            monitor="val_accuracy",
            save_best_only=True,
            mode="max",
            verbose=1,
        ),
        keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=10,
            restore_best_weights=True,
            verbose=1,
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=5,
            min_lr=1e-7,
            verbose=1,
        ),
        keras.callbacks.CSVLogger(
            output_dir / f"{model_name}_training_log.csv",
            append=True,
        ),
    ]

    return callbacks


def evaluate_model(
    model: keras.Model,
    val_dataset: tf.data.Dataset,
) -> dict:
    """Evaluate model and return metrics."""
    loss, accuracy = model.evaluate(val_dataset, verbose=0)

    # Calculate precision and recall
    y_true = []
    y_pred = []

    for images, labels in val_dataset:
        predictions = model.predict(images, verbose=0)
        y_true.extend(labels.numpy())
        y_pred.extend((predictions > CONFIDENCE_THRESHOLD).astype(int).flatten())

    from sklearn.metrics import precision_score, recall_score, f1_score

    metrics = {
        "loss": float(loss),
        "accuracy": float(accuracy),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1_score": float(f1_score(y_true, y_pred, zero_division=0)),
    }

    return metrics


def save_model_with_metadata(
    model: keras.Model,
    output_dir: Path,
    model_name: str,
    metrics: dict,
    args: argparse.Namespace,
) -> None:
    """Save trained model and metadata."""
    # Save model in SavedModel format
    model_path = output_dir / model_name
    model.save(model_path, save_format="tf")
    logger.info(f"Model saved to {model_path}")

    # Save metadata
    metadata = {
        "model_name": model_name,
        "version": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "training_date": datetime.now().isoformat(),
        "architecture": "MobileNetV3-Small",
        "input_size": list(INPUT_SIZE),
        "input_format": "RGB uint8",
        "output_format": "sigmoid probability (0=no_helmet, 1=helmet)",
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "metrics": metrics,
        "training_params": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.lr,
            "augmentation": args.augment,
        },
    }

    metadata_path = output_dir / "helmet_model_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Metadata saved to {metadata_path}")


def main() -> None:
    """Main training pipeline."""
    args = parse_args()

    # Setup
    set_random_seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Validate dataset
    logger.info("Validating dataset structure...")
    validate_dataset_structure(args.data_dir)

    # Load datasets
    logger.info("Loading datasets...")
    train_dataset = load_dataset(args.data_dir, "train", args.batch_size)
    val_dataset = load_dataset(args.data_dir, "val", args.batch_size)

    # Build or load model
    if args.resume:
        logger.info(f"Resuming from checkpoint: {args.resume}")
        model = keras.models.load_model(args.resume)
    else:
        logger.info("Building new model...")
        model = build_model(use_augmentation=args.augment)

    # Compile model
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=args.lr),
        loss="binary_crossentropy",
        metrics=["accuracy"],
    )

    # Train model
    model_name = f"helmet_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"Starting training: {model_name}")

    _ = model.fit(
        train_dataset,
        validation_data=val_dataset,
        epochs=args.epochs,
        callbacks=create_callbacks(args.output_dir, model_name),
        verbose=1,
    )

    # Evaluate final model
    logger.info("Evaluating model on validation set...")
    metrics = evaluate_model(model, val_dataset)

    logger.info("Validation Metrics:")
    for metric_name, value in metrics.items():
        logger.info(f"  {metric_name}: {value:.4f}")

    # Save model and metadata
    save_model_with_metadata(model, args.output_dir, model_name, metrics, args)

    logger.info("Training complete!")


if __name__ == "__main__":
    main()
