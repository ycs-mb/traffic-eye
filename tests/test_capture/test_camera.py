"""Tests for camera abstraction."""

import numpy as np

from src.capture.camera import MockCamera


class TestMockCamera:
    def test_open_close(self):
        cam = MockCamera(resolution=(320, 240))
        assert not cam.is_opened()
        cam.open()
        assert cam.is_opened()
        cam.close()
        assert not cam.is_opened()

    def test_read_frame_shape(self):
        cam = MockCamera(resolution=(320, 240))
        cam.open()
        frame = cam.read_frame()
        assert frame is not None
        assert frame.shape == (240, 320, 3)
        assert frame.dtype == np.uint8
        cam.close()

    def test_context_manager(self):
        with MockCamera(resolution=(160, 120)) as cam:
            assert cam.is_opened()
            frame = cam.read_frame()
            assert frame is not None

    def test_num_frames_limit(self):
        cam = MockCamera(num_frames=3)
        cam.open()
        frames = []
        for _ in range(5):
            f = cam.read_frame()
            if f is not None:
                frames.append(f)
        assert len(frames) == 3
        cam.close()

    def test_frames_iterator(self):
        cam = MockCamera(num_frames=5)
        cam.open()
        frames = list(cam.frames())
        assert len(frames) == 5
        cam.close()

    def test_properties(self):
        cam = MockCamera(resolution=(640, 480), fps=15.0)
        assert cam.resolution == (640, 480)
        assert cam.fps == 15.0

    def test_closed_returns_none(self):
        cam = MockCamera()
        assert cam.read_frame() is None
