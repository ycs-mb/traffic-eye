# src/capture/

Camera input and GPS reader abstractions with cross-platform implementations.

## Files

| File | Purpose |
|------|---------|
| `camera.py` | Camera capture classes (Pi, OpenCV, video file, mock) |
| `buffer.py` | Circular frame buffer for rolling evidence window |
| `gps.py` | GPS reader classes (gpsd, NMEA file, mock) |

## camera.py - Camera Capture

All camera implementations extend `CameraBase` (abstract base class) with a consistent interface:

```python
class CameraBase(ABC):
    def open(self) -> None          # Open camera device
    def close(self) -> None         # Release camera device
    def read_frame(self) -> ndarray # Read single frame (None if unavailable)
    def is_opened(self) -> bool     # Check if camera is open
    def resolution -> (int, int)    # (width, height)
    def fps -> float                # Frames per second
    def frames() -> Iterator        # Yield frames continuously
```

Supports context manager (`with camera: ...`) for automatic open/close.

### Implementations

| Class | Platform | Description |
|-------|----------|-------------|
| `PiCamera` | Raspberry Pi | Uses `picamera2` + libcamera. Configures video mode with BGR888 format. |
| `OpenCVCamera` | macOS, Linux, Windows | Uses `cv2.VideoCapture`. Works with webcams and V4L2 devices. |
| `VideoFileCamera` | All | Plays a video file. Supports looping and custom playback FPS. For testing. |
| `MockCamera` | All | Generates solid-color frames with frame counter text. For unit tests. |

### Usage

The `platform_factory.create_camera()` function selects the right implementation automatically:
- If `--video` flag is provided: `VideoFileCamera`
- If platform is `"mock"`: `MockCamera`
- If platform is `"pi"` and picamera2 is available: `PiCamera`
- Otherwise: `OpenCVCamera`

### Raspberry Pi Camera Setup

1. Enable the camera interface: `sudo raspi-config` -> Interface Options -> Camera -> Enable
2. Verify camera: `libcamera-hello --timeout 5000`
3. The `PiCamera` class configures:
   - Resolution: 1280x720 (configurable)
   - Format: BGR888 (direct OpenCV compatibility)
   - Frame rate: 30 fps (configurable)

## buffer.py - Circular Frame Buffer

`CircularFrameBuffer` maintains a rolling window of the most recent N seconds of processed frames in memory. When a violation is detected, frames from before and after the event can be extracted for evidence.

```python
buffer = CircularFrameBuffer(max_seconds=10, fps=6.0)

# Push frames as they are processed
buffer.push(frame, timestamp, frame_id)

# Extract a time-bounded clip for evidence
clip = buffer.get_clip(start_time, end_time)

# Get the last N seconds
recent = buffer.get_recent(seconds=5.0)
```

Key properties:
- Uses `collections.deque` with `maxlen` for O(1) push/pop
- Frames are copied on push to prevent reference issues
- At 720p and 6 fps, 10 seconds uses approximately 160MB of RAM
- `memory_usage_bytes` property reports current memory consumption

## gps.py - GPS Input

All GPS implementations extend `GPSBase`:

```python
class GPSBase(ABC):
    def start(self) -> None                    # Start reading
    def stop(self) -> None                     # Stop reading
    def get_reading(self) -> GPSReading | None # Latest fix (None if no fix)
    def has_fix(self) -> bool                  # Whether GPS has valid fix
```

### Implementations

| Class | Description |
|-------|-------------|
| `GpsdGPS` | Reads from the `gpsd` daemon via `gps3` library. Background thread for non-blocking reads. |
| `NMEAFileGPS` | Replays NMEA sentence files (supports GPRMC/GNRMC). For testing with recorded routes. |
| `MockGPS` | Returns configurable static or sequential GPS readings. For unit tests. |

### GPSReading Fields

| Field | Type | Description |
|-------|------|-------------|
| `latitude` | float | Decimal degrees |
| `longitude` | float | Decimal degrees |
| `altitude` | float | Meters |
| `speed_kmh` | float | Speed in km/h |
| `heading` | float | Bearing in degrees (0-360) |
| `fix_quality` | int | 0=no fix, 1+=valid fix |
| `satellites` | int | Number of satellites |

### GPS Hardware Setup (Raspberry Pi)

1. Connect NEO-6M GPS module to Pi UART:
   - GPS TX -> Pi GPIO 15 (RXD)
   - GPS RX -> Pi GPIO 14 (TXD)
   - GPS VCC -> Pi 3.3V
   - GPS GND -> Pi GND

2. Enable serial port:
   ```bash
   sudo raspi-config  # Interface Options -> Serial Port
   # Disable login shell over serial: No
   # Enable serial port hardware: Yes
   ```

3. Configure and start gpsd:
   ```bash
   sudo systemctl enable gpsd
   sudo systemctl start gpsd
   # Test: cgps -s
   ```

4. Set `gps.enabled: true` in `config/settings.yaml`

The `GpsdGPS` class connects to gpsd on `127.0.0.1:2947` and reads in a background thread, so GPS data is always fresh without blocking the main detection loop.
