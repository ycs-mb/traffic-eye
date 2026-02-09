# src/violation/

Violation detection logic: rule evaluation, temporal consistency checking, and confidence aggregation.

## Files

| File | Purpose |
|------|---------|
| `rules.py` | Violation rules (no helmet, red light, wrong side) and the `RuleEngine` |
| `temporal.py` | Temporal consistency checker (N consecutive frames) |
| `confidence.py` | Weighted confidence score aggregation |

## rules.py - Violation Rules

### ViolationRule Base Class

All rules implement:

```python
class ViolationRule(ABC):
    @property
    def violation_type(self) -> ViolationType
    def evaluate(self, frame_data: FrameData, context: dict) -> list[(track_id, confidence)]
```

### NoHelmetRule

Detects motorcycle riders without helmets.

**Logic:**
1. Find all `motorcycle` and `person` detections in the frame
2. For each motorcycle-person pair, check spatial association:
   - IoU overlap >= `proximity_threshold` (default 0.3), OR
   - Person bounding box is vertically positioned on/above the motorcycle
3. Look up helmet classification result from context (`has_helmet[track_id]`)
4. If `has_helmet == False`, emit violation with confidence = min(motorcycle_conf, person_conf, helmet_conf)

### RedLightJumpRule

Detects vehicles crossing during a red traffic signal.

**Logic:**
1. Check if `signal_state` in context is `RED`
2. Find all vehicle detections (car, truck, bus, motorcycle)
3. A vehicle in the lower half of the frame (center Y > 50% frame height) is considered at/past the stop line
4. Emit violation with confidence = vehicle detection confidence

**Limitation**: This is a simplified heuristic. Production use would need a calibrated stop-line reference.

### WrongSideRule

Detects wrong-side driving using GPS heading deviation.

**Logic:**
1. Compare GPS heading against expected `road_bearing` from context
2. If angular deviation exceeds `heading_deviation_threshold` (default 120 degrees), emit violation
3. Confidence is proportional to deviation (deviation / 180)

**Limitation**: Requires GPS data and known road bearing. High false positive rate near U-turns and intersections.

### RuleEngine

Orchestrates all rules for each frame:

```
For each frame:
  1. GPS speed gate check (skip if < 5 km/h)
  2. Run all enabled rules
  3. Filter by confidence threshold
  4. Check temporal consistency (N consecutive frames)
  5. Aggregate confidence scores
  6. Check cooldown (per violation type)
  7. Check hourly rate limit
  8. Emit ViolationCandidate
```

**Cooldown**: After emitting a violation, the same type is suppressed for `cooldown_seconds` (default 30s) to avoid duplicate reports.

**Rate limiting**: Maximum `max_reports_per_hour` (default 20) violations per hour across all types.

## temporal.py - Temporal Consistency

`TemporalConsistencyChecker` ensures violations persist across multiple frames before confirming.

**Key concept**: A violation is only confirmed when the condition holds for `min_consecutive_frames` frames **for the same tracked object** (identified by `(violation_type, track_id)` pair).

```python
checker = TemporalConsistencyChecker()

# Returns True when threshold is met
confirmed = checker.update("no_helmet", track_id=5, condition_met=True, min_frames=3)
# Frame 1: count=1, returns False
# Frame 2: count=2, returns False
# Frame 3: count=3, returns True

# Counter resets if condition is not met
checker.update("no_helmet", track_id=5, condition_met=False, min_frames=3)
# count=0, returns False
```

This eliminates single-frame false positives from transient detection errors.

## confidence.py - Confidence Aggregation

`ConfidenceAggregator` computes a weighted average of multiple confidence signals:

| Signal | Default Weight | Source |
|--------|---------------|--------|
| Detection confidence | 0.30 | Object detector output |
| Classification confidence | 0.30 | Helmet/signal classifier |
| Temporal consistency ratio | 0.20 | consecutive_frames / min_required |
| OCR confidence | 0.20 | License plate OCR (when available) |

When OCR confidence is not available, its weight is redistributed proportionally among the other signals.

### Confidence Routing

The aggregated confidence determines the action:

| Range | Action |
|-------|--------|
| >= 0.96 | Report directly (local processing) |
| 0.70 - 0.96 | Queue for cloud verification |
| < 0.70 | Discard as unreliable |

```python
aggregator = ConfidenceAggregator()

# Full confidence with all signals
score = aggregator.compute(
    detection_conf=0.92,
    classification_conf=0.88,
    temporal_ratio=1.0,
    ocr_conf=0.75,
)

# Route based on score
if aggregator.meets_local_threshold(score):
    send_report_directly()
elif aggregator.needs_cloud_verification(score):
    queue_for_cloud()
else:
    discard()
```

## Usage on Raspberry Pi

The violation module is pure Python with no hardware dependencies. It runs identically on Pi and desktop. The computational cost is negligible compared to detection and classification.
