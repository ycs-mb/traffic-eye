# src/cloud/

Cloud verification via vision AI APIs (Google Gemini Vision or OpenAI GPT-4V) and offline queue management.

## Files

| File | Purpose |
|------|---------|
| `verifier.py` | `CloudVerifier` - sends evidence to cloud APIs for verification; `CloudVerificationProcessor` - batch processing |
| `queue.py` | `CloudQueue` - offline queue for pending verification requests |

## verifier.py - Cloud Verification

### When Cloud Verification is Used

Violations with aggregated confidence between 0.70 and 0.96 are queued for cloud verification. This reduces false positives by having a vision AI model independently analyze the evidence image.

### CloudVerifier

Sends the best evidence frame (base64-encoded JPEG) to a cloud vision API with a structured prompt requesting:
- `is_violation` (boolean)
- `violation_type` (string)
- `confidence` (float 0.0-1.0)
- `plate_number` (string or null)
- `description` (string)

### Supported Providers

| Provider | API | Model |
|----------|-----|-------|
| `gemini` | Gemini Vision API | `gemini-pro-vision` |
| `openai` | OpenAI Chat Completions | `gpt-4-vision-preview` |

Set the provider in config:
```yaml
cloud:
  provider: "gemini"    # or "openai"
  api_key_env: "TRAFFIC_EYE_CLOUD_API_KEY"
```

### Retry Logic

- Up to `max_retries` (default: 3) attempts per request
- Exponential backoff between retries: 2s, 4s, 8s
- Handles timeouts, HTTP errors, and general exceptions

### Response Parsing

The cloud API response text is parsed as JSON. Handles:
- Raw JSON responses
- JSON wrapped in markdown code blocks (`` ```json ... ``` ``)
- Both Gemini format (`candidates[0].content.parts[0].text`) and OpenAI format (`choices[0].message.content`)

### CloudVerificationProcessor

Batch processor that:
1. Checks connectivity before processing
2. Reads pending items from the cloud queue (up to 5 at a time)
3. Retrieves violation data and evidence files from the database
4. Sends to `CloudVerifier`
5. If confirmed (confidence >= threshold): marks as verified, queues email
6. If rejected: marks as discarded

## queue.py - Cloud Queue

`CloudQueue` manages the offline queue of verification requests, persisted in SQLite.

### Queue Lifecycle

```
Violation detected (conf 0.70-0.96)
         |
         v
  CloudQueue.enqueue(violation_id)
         |
         v
  [Stored in cloud_queue table as "pending"]
         |
         v
  CloudVerificationProcessor.process_batch()
         |
    +-----------+-----------+
    |                       |
    v                       v
  Confirmed              Rejected
  (mark "done")          (mark "failed")
  Queue email            Mark violation
  Update status          as "discarded"
```

### Connectivity Check

`CloudQueue.is_online()` pings `https://www.google.com/generate_204` with a 5-second timeout to verify internet connectivity before attempting cloud API calls. Processing is skipped when offline.

### Configuration

```yaml
cloud:
  provider: "gemini"
  api_key_env: "TRAFFIC_EYE_CLOUD_API_KEY"
  confidence_threshold: 0.96    # Cloud must return >= this to confirm
  max_retries: 3
  timeout_seconds: 30
```

### API Key Setup

```bash
# For Google Gemini
export TRAFFIC_EYE_CLOUD_API_KEY="your-gemini-api-key"

# For OpenAI
export TRAFFIC_EYE_CLOUD_API_KEY="your-openai-api-key"
```

## Deployment on Raspberry Pi

Cloud verification runs via the `traffic-eye-sender.service` systemd unit, triggered every 5 minutes by `traffic-eye-sender.timer`. This decouples cloud API calls from the real-time detection loop.

The offline queue ensures no violations are lost during network outages. Pending requests are retried on the next timer invocation.
