"""Helmet classifier abstraction."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import numpy as np

logger = logging.getLogger(__name__)


class HelmetClassifierBase(ABC):
    """Abstract base class for helmet classification on head crops."""

    @abstractmethod
    def load_model(self, model_path: str) -> None:
        """Load classifier model."""

    @abstractmethod
    def classify(self, head_crop: np.ndarray) -> tuple[bool, float]:
        """Classify whether a head crop shows a helmet.

        Args:
            head_crop: BGR image of a cropped head region.

        Returns:
            (has_helmet, confidence) tuple.
        """

    @abstractmethod
    def is_loaded(self) -> bool:
        """Check if model is loaded."""


class MockHelmetClassifier(HelmetClassifierBase):
    """Returns configurable helmet classification for testing."""

    def __init__(
        self,
        default_has_helmet: bool = False,
        default_confidence: float = 0.92,
    ):
        self._has_helmet = default_has_helmet
        self._confidence = default_confidence
        self._loaded = False
        # Per-call overrides: (frame_id, track_id) -> (has_helmet, confidence)
        self._overrides: dict[tuple[int, int], tuple[bool, float]] = {}

    def load_model(self, model_path: str = "") -> None:
        self._loaded = True
        logger.info("Mock helmet classifier loaded")

    def classify(self, head_crop: np.ndarray) -> tuple[bool, float]:
        return (self._has_helmet, self._confidence)

    def is_loaded(self) -> bool:
        return self._loaded

    def set_result(self, has_helmet: bool, confidence: float) -> None:
        """Override default result for subsequent calls."""
        self._has_helmet = has_helmet
        self._confidence = confidence


class TFLiteHelmetClassifier(HelmetClassifierBase):
    """TFLite-based binary helmet classifier optimized for Raspberry Pi.

    This classifier uses a float16-quantized MobileNetV3-Small for efficient
    inference on edge devices. It expects head crop images and returns binary
    classification with confidence scores.

    Input: BGR/RGB head crop image (any size, will be resized to 96x96)
    Output: (has_helmet: bool, confidence: float)

    Important deployment notes:
        - Uses ai-edge-litert (successor to tflite-runtime) on Pi
        - Must use BUILTIN_WITHOUT_DEFAULT_DELEGATES op resolver to avoid
          XNNPACK failures on MobileNetV3 hard-swish operations
        - Model input is float32 [0, 1] range; uint8 images are normalized
          automatically in classify()

    Attributes:
        _input_size: Expected input dimensions (96x96 by default)
        _num_threads: Number of threads for TFLite inference (4 for Raspberry Pi)
        _confidence_threshold: Threshold for helmet classification (0.5)
    """

    def __init__(
        self,
        input_size: tuple[int, int] = (96, 96),
        num_threads: int = 4,
        confidence_threshold: float = 0.5,
    ):
        self._input_size = input_size
        self._num_threads = num_threads
        self._confidence_threshold = confidence_threshold
        self._interpreter = None
        self._input_details = None
        self._output_details = None
        self._loaded = False

    def load_model(self, model_path: str) -> None:
        """Load TFLite model from file path.

        Tries ai-edge-litert first (modern Pi runtime), then falls back to
        tflite-runtime and finally tensorflow.lite. Uses
        BUILTIN_WITHOUT_DEFAULT_DELEGATES to avoid XNNPACK compatibility
        issues with MobileNetV3 hard-swish operations.

        Args:
            model_path: Path to .tflite model file

        Raises:
            FileNotFoundError: If model file doesn't exist
            ImportError: If no TFLite runtime is installed
            RuntimeError: If model loading or allocation fails
        """
        from pathlib import Path

        # Validate model file exists
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"Helmet model not found: {model_path}\n"
                f"Run scripts/convert_float16.py to build the model first."
            )

        # Import TFLite runtime (try ai-edge-litert first, then fallbacks)
        Interpreter = None
        OpResolverType = None

        try:
            from ai_edge_litert.interpreter import (
                Interpreter as _Interp,
                OpResolverType as _OpRes,
            )
            Interpreter = _Interp
            OpResolverType = _OpRes
            logger.debug("Using ai-edge-litert runtime")
        except ImportError:
            try:
                import tflite_runtime.interpreter as tflite
                Interpreter = tflite.Interpreter
                try:
                    from tflite_runtime.interpreter import OpResolverType as _OpRes
                    OpResolverType = _OpRes
                except ImportError:
                    pass
                logger.debug("Using tflite-runtime")
            except ImportError:
                try:
                    import tensorflow.lite as tflite
                    Interpreter = tflite.Interpreter
                    logger.debug("Using tensorflow.lite")
                except ImportError:
                    raise ImportError(
                        "No TFLite runtime found. Install one of:\n"
                        "  pip install ai-edge-litert\n"
                        "  pip install tflite-runtime\n"
                        "  pip install tensorflow"
                    )

        try:
            # Build interpreter kwargs -- use BUILTIN_WITHOUT_DEFAULT_DELEGATES
            # to avoid XNNPACK failures on MobileNetV3 hard-swish ops
            kwargs: dict = {
                "model_path": model_path,
                "num_threads": self._num_threads,
            }
            if OpResolverType is not None:
                try:
                    kwargs["experimental_op_resolver_type"] = (
                        OpResolverType.BUILTIN_WITHOUT_DEFAULT_DELEGATES
                    )
                except AttributeError:
                    pass  # Older runtime without this option

            self._interpreter = Interpreter(**kwargs)
            self._interpreter.allocate_tensors()

            # Get input/output details
            self._input_details = self._interpreter.get_input_details()
            self._output_details = self._interpreter.get_output_details()

            # Validate model input/output shapes
            self._validate_model_format()

            self._loaded = True
            logger.info(
                "TFLite helmet classifier loaded: %s (threads=%d)",
                model_path,
                self._num_threads,
            )

        except Exception as e:
            raise RuntimeError(f"Failed to load helmet model: {e}") from e

    def _validate_model_format(self) -> None:
        """Validate that model has expected input/output format."""
        input_shape = self._input_details[0]["shape"]
        output_shape = self._output_details[0]["shape"]

        expected_input = (1, *self._input_size, 3)
        expected_output = (1, 1)

        if tuple(input_shape) != expected_input:
            logger.warning(
                f"Unexpected input shape: {input_shape}, expected {expected_input}"
            )

        if tuple(output_shape) != expected_output:
            logger.warning(
                f"Unexpected output shape: {output_shape}, expected {expected_output}"
            )

    def classify(self, head_crop: np.ndarray) -> tuple[bool, float]:
        """Classify whether head crop shows a helmet.

        Args:
            head_crop: BGR or RGB image of cropped head region (any size)

        Returns:
            Tuple of (has_helmet, confidence) where:
                - has_helmet: True if helmet detected, False otherwise
                - confidence: Float in [0.0, 1.0] representing model confidence

        Notes:
            - Returns (False, 0.0) if model is not loaded
            - Handles inference errors gracefully with logging
        """
        if not self._loaded or self._interpreter is None:
            logger.warning("Helmet classifier not loaded, returning default")
            return (False, 0.0)

        try:
            import cv2

            # Preprocess image
            resized = cv2.resize(head_crop, self._input_size)

            # Handle input dtype (INT8 or FLOAT32)
            input_dtype = self._input_details[0]["dtype"]
            if input_dtype == np.uint8:
                input_data = np.expand_dims(resized, axis=0)
            else:
                # Normalize to [0, 1] for float32 models
                input_data = np.expand_dims(
                    resized.astype(np.float32) / 255.0, axis=0
                )

            # Run inference
            self._interpreter.set_tensor(
                self._input_details[0]["index"], input_data
            )
            self._interpreter.invoke()

            # Get output
            output = self._interpreter.get_tensor(
                self._output_details[0]["index"]
            )

            # Parse sigmoid output (>threshold = helmet)
            score = float(output[0][0]) if output.ndim > 1 else float(output[0])
            has_helmet = score > self._confidence_threshold
            confidence = score if has_helmet else 1.0 - score

            return (has_helmet, confidence)

        except Exception as e:
            logger.error(f"Helmet classification error: {e}", exc_info=True)
            return (False, 0.0)

    def is_loaded(self) -> bool:
        """Check if model is successfully loaded."""
        return self._loaded
