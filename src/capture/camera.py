"""Camera capture abstraction with cross-platform implementations."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Iterator, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class CameraBase(ABC):
    """Abstract base class for camera capture."""

    @abstractmethod
    def open(self) -> None:
        """Open the camera device."""

    @abstractmethod
    def close(self) -> None:
        """Release the camera device."""

    @abstractmethod
    def read_frame(self) -> Optional[np.ndarray]:
        """Read a single frame. Returns None if no frame available."""

    @abstractmethod
    def is_opened(self) -> bool:
        """Check if camera is currently open."""

    @property
    @abstractmethod
    def resolution(self) -> tuple[int, int]:
        """Return (width, height)."""

    @property
    @abstractmethod
    def fps(self) -> float:
        """Return frames per second."""

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    def frames(self) -> Iterator[np.ndarray]:
        """Yield frames continuously until camera is closed or source exhausted."""
        while self.is_opened():
            frame = self.read_frame()
            if frame is not None:
                yield frame
            else:
                break


class OpenCVCamera(CameraBase):
    """Cross-platform camera using OpenCV VideoCapture.

    Works on macOS (webcam), Linux (V4L2), and Windows.
    """

    def __init__(
        self,
        device_id: int = 0,
        resolution: tuple[int, int] = (1280, 720),
        fps: int = 30,
    ):
        self._device_id = device_id
        self._resolution = resolution
        self._fps = fps
        self._cap: Optional[cv2.VideoCapture] = None

    def open(self) -> None:
        self._cap = cv2.VideoCapture(self._device_id)
        if not self._cap.isOpened():
            raise RuntimeError(f"Failed to open camera device {self._device_id}")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._resolution[0])
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._resolution[1])
        self._cap.set(cv2.CAP_PROP_FPS, self._fps)
        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info("OpenCV camera opened: %dx%d @ %dfps", actual_w, actual_h, self._fps)

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def read_frame(self) -> Optional[np.ndarray]:
        if self._cap is None:
            return None
        ret, frame = self._cap.read()
        return frame if ret else None

    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    @property
    def resolution(self) -> tuple[int, int]:
        return self._resolution

    @property
    def fps(self) -> float:
        return float(self._fps)


class VideoFileCamera(CameraBase):
    """Plays back a video file as if it were a live camera.

    Essential for testing and development without real hardware.
    """

    def __init__(self, video_path: str, loop: bool = True, playback_fps: Optional[float] = None):
        self._video_path = video_path
        self._loop = loop
        self._cap: Optional[cv2.VideoCapture] = None
        self._playback_fps = playback_fps
        self._actual_fps: float = 30.0
        self._resolution_val: tuple[int, int] = (0, 0)

    def open(self) -> None:
        self._cap = cv2.VideoCapture(self._video_path)
        if not self._cap.isOpened():
            raise RuntimeError(f"Failed to open video file: {self._video_path}")
        self._actual_fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._resolution_val = (w, h)
        logger.info("Video file camera opened: %s (%dx%d @ %.1ffps)",
                     self._video_path, w, h, self._actual_fps)

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def read_frame(self) -> Optional[np.ndarray]:
        if self._cap is None:
            return None
        ret, frame = self._cap.read()
        if not ret and self._loop:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self._cap.read()
        if ret and self._playback_fps:
            time.sleep(1.0 / self._playback_fps)
        return frame if ret else None

    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    @property
    def resolution(self) -> tuple[int, int]:
        return self._resolution_val

    @property
    def fps(self) -> float:
        return self._playback_fps or self._actual_fps


class MockCamera(CameraBase):
    """Generates synthetic frames for unit testing.

    No real camera or video file needed.
    """

    def __init__(
        self,
        resolution: tuple[int, int] = (1280, 720),
        fps: float = 30.0,
        num_frames: Optional[int] = None,
        color: tuple[int, int, int] = (128, 128, 128),
    ):
        self._resolution = resolution
        self._fps = fps
        self._num_frames = num_frames
        self._color = color
        self._opened = False
        self._frame_count = 0

    def open(self) -> None:
        self._opened = True
        self._frame_count = 0
        logger.info("Mock camera opened: %dx%d @ %.1ffps",
                     self._resolution[0], self._resolution[1], self._fps)

    def close(self) -> None:
        self._opened = False

    def read_frame(self) -> Optional[np.ndarray]:
        if not self._opened:
            return None
        if self._num_frames is not None and self._frame_count >= self._num_frames:
            return None

        h, w = self._resolution[1], self._resolution[0]
        frame = np.full((h, w, 3), self._color, dtype=np.uint8)
        # Add frame counter text for visual identification
        cv2.putText(
            frame,
            f"Frame {self._frame_count}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 255),
            2,
        )
        self._frame_count += 1
        return frame

    def is_opened(self) -> bool:
        return self._opened

    @property
    def resolution(self) -> tuple[int, int]:
        return self._resolution

    @property
    def fps(self) -> float:
        return self._fps


class PiCamera(CameraBase):
    """Raspberry Pi camera using picamera2 + libcamera backend.

    Requires picamera2 package (pre-installed on Raspberry Pi OS).
    """

    def __init__(
        self,
        resolution: tuple[int, int] = (1280, 720),
        fps: int = 30,
    ):
        self._resolution = resolution
        self._fps = fps
        self._picam2 = None
        self._opened = False

    def open(self) -> None:
        from picamera2 import Picamera2

        self._picam2 = Picamera2()
        config = self._picam2.create_video_configuration(
            main={"size": self._resolution, "format": "BGR888"},
            controls={"FrameRate": self._fps},
        )
        self._picam2.configure(config)
        self._picam2.start()
        self._opened = True
        logger.info("PiCamera opened: %dx%d @ %dfps",
                     self._resolution[0], self._resolution[1], self._fps)

    def close(self) -> None:
        if self._picam2 is not None:
            self._picam2.stop()
            self._picam2.close()
            self._picam2 = None
        self._opened = False

    def read_frame(self) -> Optional[np.ndarray]:
        if self._picam2 is None or not self._opened:
            return None
        return self._picam2.capture_array("main")

    def is_opened(self) -> bool:
        return self._opened and self._picam2 is not None

    @property
    def resolution(self) -> tuple[int, int]:
        return self._resolution

    @property
    def fps(self) -> float:
        return float(self._fps)
