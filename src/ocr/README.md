# src/ocr/

License plate optical character recognition and Indian plate format validation.

## Files

| File | Purpose |
|------|---------|
| `plate_ocr.py` | PaddleOCR integration with preprocessing pipeline for plate text extraction |
| `validators.py` | Indian license plate format validation and OCR error correction |

## plate_ocr.py - OCR Extraction

Provides PaddleOCR integration with a comprehensive preprocessing pipeline for extracting text from license plate images.

### Architecture

The module follows clean architecture principles:
- **Small, composable functions**: Each preprocessing step is a separate function (<30 lines)
- **Fail gracefully**: Returns None on error, never crashes
- **Input validation**: Validates images at system boundaries
- **Comprehensive logging**: Logs warnings/errors for debugging

### OCR Pipeline

```python
from src.ocr.plate_ocr import extract_and_validate_plate
import cv2

# Load plate crop
plate_crop = cv2.imread("plate_crop.jpg")

# Extract and validate in one step
text, is_valid, state = extract_and_validate_plate(plate_crop)

if is_valid:
    print(f"Detected {state} plate: {text}")
else:
    print(f"Invalid or unreadable plate")
```

### Preprocessing Pipeline

The preprocessing pipeline enhances OCR accuracy through three stages:

1. **Grayscale Conversion**: Reduces noise and simplifies processing
2. **Adaptive Thresholding**: Handles varying lighting conditions (shadows, glare, night)
3. **Deskewing**: Corrects rotation up to ±45 degrees

Each step can be used independently:

```python
from src.ocr.plate_ocr import (
    convert_to_grayscale,
    apply_adaptive_threshold,
    deskew_image,
    preprocess_plate_image,
)

# Individual steps
gray = convert_to_grayscale(plate_crop)
binary = apply_adaptive_threshold(gray)
deskewed = deskew_image(binary)

# Or use the complete pipeline
preprocessed = preprocess_plate_image(plate_crop)
```

### Functions

| Function | Description |
|----------|-------------|
| `extract_plate_text(image, confidence_threshold, preprocess)` | Main OCR function - extracts text from plate image |
| `extract_and_validate_plate(image, confidence_threshold)` | OCR + validation in one step |
| `preprocess_plate_image(image)` | Complete preprocessing pipeline |
| `convert_to_grayscale(image)` | Convert BGR/RGB to grayscale |
| `apply_adaptive_threshold(image)` | Adaptive thresholding for contrast enhancement |
| `deskew_image(image)` | Correct rotation/skew |
| `validate_image(image)` | Input validation at boundaries |

### Configuration

OCR behavior can be tuned via parameters:

```python
# Lower confidence threshold for difficult conditions
text = extract_plate_text(
    plate_crop,
    confidence_threshold=0.5,  # Default: 0.6
    preprocess=True,            # Default: True
)

# Disable preprocessing if image is already clean
text = extract_plate_text(plate_crop, preprocess=False)
```

### Accuracy Expectations

| Condition | Expected Accuracy | Notes |
|-----------|-------------------|-------|
| Clear, daytime, stationary | 85-95% | Best case scenario |
| Daytime, moving vehicle | 70-85% | Motion blur reduces accuracy |
| Night, stationary | 60-75% | Low light affects quality |
| Night, moving vehicle | 50-65% | Combination of challenges |
| Skewed/angled plates | 50-70% | Deskewing helps but has limits |
| Partial/occluded plates | 30-50% | Missing characters hurt accuracy |

**Recommendations**:
- Use cloud verification (Gemini/GPT-4V) for low-confidence results
- Require multiple consecutive frames with same plate for confirmation
- Set confidence threshold based on operating conditions

### Error Handling

The module handles errors gracefully:

```python
# Invalid image returns None
result = extract_plate_text(None)
assert result is None

# Corrupted image returns None
result = extract_plate_text(corrupted_array)
assert result is None

# Low confidence returns None
result = extract_plate_text(blurry_image, confidence_threshold=0.9)
assert result is None  # If confidence < 0.9
```

All errors are logged with appropriate level:
- `logger.error()`: OCR engine failures, exceptions
- `logger.warning()`: Invalid inputs, preprocessing failures
- `logger.debug()`: Low confidence, no results
- `logger.info()`: Successful extractions

### Integration Example

Full pipeline from detection to validated plate:

```python
import cv2
from src.ocr.plate_ocr import extract_and_validate_plate

# After YOLOv8n detects plate region
plate_bbox = [x1, y1, x2, y2]
plate_crop = frame[y1:y2, x1:x2]

# Extract and validate
text, is_valid, state = extract_and_validate_plate(plate_crop)

if is_valid:
    # Attach to violation candidate
    candidate.plate_number = text
    candidate.state_code = state
else:
    # Mark for cloud verification
    candidate.needs_verification = True
```

## validators.py - Plate Validation

Provides a complete pipeline for processing raw OCR output into validated Indian license plate numbers.

### Processing Pipeline

```python
from src.ocr.validators import process_plate

corrected, is_valid, state_code = process_plate("MH 12-AB 1234")
# corrected = "MH12AB1234"
# is_valid = True
# state_code = "MH"
```

### Functions

| Function | Description |
|----------|-------------|
| `clean_plate_text(raw)` | Remove spaces, hyphens, dots; uppercase; strip non-alphanumeric |
| `correct_ocr_errors(text)` | Position-aware character correction (e.g., `0` -> `O` in letter positions) |
| `validate_plate(text)` | Check against Indian plate format patterns |
| `extract_state_code(plate)` | Extract 2-letter state/UT code |
| `process_plate(raw_text)` | Full pipeline: clean -> correct -> validate -> extract state |

### Indian Plate Formats

Supported patterns:

| Pattern | Example | Description |
|---------|---------|-------------|
| `AA00XX0000` | MH12AB1234 | Standard format |
| `AA00XXX0000` | MH12ABC1234 | Extended series |
| `AA000000` | MH121234 | Without alpha series |
| `00BH0000XX` | 22BH1234AB | Bharat (national) series |
| `AA00X0000` | MH12A1234 | Single letter series |
| `CD000000` | CD121234 | Diplomatic plates |
| `AA00S0000` | DL01S1234 | Government/special |

### OCR Error Correction

Position-aware correction based on Indian plate structure `AA 00 XX 0000`:

- **Positions 0-1** (state code): Must be letters. Digit-to-alpha corrections: `0->O`, `1->I`, `5->S`, `8->B`
- **Positions 2-3** (district code): Must be digits. Alpha-to-digit corrections: `O->0`, `I->1`, `S->5`, `Z->2`
- **Middle section** (series): Must be letters. Same digit-to-alpha corrections.
- **Last 4 positions** (number): Must be digits. Same alpha-to-digit corrections.

### Supported State Codes

All 28 states and 8 Union Territories are recognized:
`AN, AP, AR, AS, BR, CG, CH, DD, DL, GA, GJ, HP, HR, JH, JK, KA, KL, LA, MH, ML, MN, MP, MZ, NL, OD, PB, PY, RJ, SK, TN, TR, TS, UK, UP, WB`

### Integration with Detection Pipeline

In the full pipeline, plate detection and OCR work as follows:

1. YOLOv8n detects plate regions in the frame
2. Plate regions are cropped, preprocessed (grayscale, adaptive threshold, deskew)
3. PaddleOCR extracts raw text from the crop
4. `process_plate()` validates and corrects the raw OCR output
5. If valid, the plate text is attached to the `ViolationCandidate`

### Limitations

- OCR accuracy is 50-65% at night on moving vehicles (see accuracy table above)
- Small or angled plates have lower detection rates
- Cloud verification via Gemini/GPT-4V can improve plate reading accuracy
- Preprocessing pipeline adds ~50-100ms per plate (trade-off for accuracy)
