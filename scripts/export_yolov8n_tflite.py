#!/usr/bin/env python3
"""Export YOLOv8n to TFLite INT8 for Raspberry Pi deployment.

Usage:
    pip install ultralytics
    python scripts/export_yolov8n_tflite.py

This will:
1. Download the YOLOv8n PyTorch model (~6MB)
2. Export to TFLite with INT8 quantization using COCO calibration data
3. Save the result to models/yolov8n_int8.tflite

The exported model expects 320x320 RGB input and outputs (1, 84, 8400)
where 84 = 4 (xywh) + 80 (COCO class scores).
"""

from pathlib import Path


def export():
    from ultralytics import YOLO

    output_dir = Path(__file__).resolve().parent.parent / "models"
    output_dir.mkdir(exist_ok=True)

    # Load pretrained YOLOv8n
    model = YOLO("yolov8n.pt")

    # Export to TFLite with INT8 quantization
    # - imgsz=320: smaller input for Pi 4 speed (vs default 640)
    # - int8=True: INT8 quantization for 2-3x speedup
    # - data="coco8.yaml": calibration dataset (ships with ultralytics)
    model.export(
        format="tflite",
        imgsz=320,
        int8=True,
        data="coco8.yaml",
    )

    # Ultralytics saves the model next to the .pt file with a suffix.
    # Find it and move to our models/ dir.
    # The export creates: yolov8n_saved_model/yolov8n_full_integer_quant.tflite
    #   or yolov8n_saved_model/yolov8n_integer_quant.tflite
    #   or yolov8n_int8.tflite depending on version.
    import glob
    import shutil

    # Search for the exported tflite file
    candidates = glob.glob("yolov8n*int8*.tflite") + \
                 glob.glob("yolov8n*integer_quant*.tflite") + \
                 glob.glob("yolov8n_saved_model/*.tflite") + \
                 glob.glob("yolov8n_saved_model/**/*.tflite", recursive=True)

    if not candidates:
        # Ultralytics may return the path directly
        print("Searching for exported model...")
        candidates = glob.glob("**/yolov8n*.tflite", recursive=True)

    if candidates:
        src = candidates[0]
        dst = output_dir / "yolov8n_int8.tflite"
        shutil.copy2(src, dst)
        print(f"Model saved to: {dst}")
        print(f"Model size: {dst.stat().st_size / 1024 / 1024:.1f} MB")
    else:
        print("ERROR: Could not find exported TFLite model.")
        print("Check the ultralytics output above for the export path.")

    # Print model info for verification
    try:
        import tflite_runtime.interpreter as tflite
    except ImportError:
        import tensorflow.lite as tflite

    dst = output_dir / "yolov8n_int8.tflite"
    if dst.exists():
        interpreter = tflite.Interpreter(model_path=str(dst))
        interpreter.allocate_tensors()
        inp = interpreter.get_input_details()
        out = interpreter.get_output_details()
        print(f"\nInput:  shape={inp[0]['shape']}, dtype={inp[0]['dtype']}")
        print(f"Output: shape={out[0]['shape']}, dtype={out[0]['dtype']}")


if __name__ == "__main__":
    export()
