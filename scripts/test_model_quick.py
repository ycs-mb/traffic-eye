#!/usr/bin/env python3
"""Quick test of the helmet TFLite model."""
import os
os.environ["XNNPACK_FORCE_DISABLE"] = "1"

import numpy as np
from ai_edge_litert.interpreter import Interpreter

model_path = "/home/yashcs/traffic-eye/models/helmet_cls_int8.tflite"
interp = Interpreter(model_path=model_path, num_threads=4, experimental_delegates=[])
interp.allocate_tensors()

inp = interp.get_input_details()[0]
out = interp.get_output_details()[0]
print(f"Input: shape={inp['shape']}, dtype={inp['dtype']}")
print(f"Output: shape={out['shape']}, dtype={out['dtype']}")

test_img = np.random.randint(0, 255, tuple(inp['shape']), dtype=np.uint8)
interp.set_tensor(inp['index'], test_img)
interp.invoke()
result = interp.get_tensor(out['index'])
print(f"Test output: {result}")
print("Model loads and runs OK!")
