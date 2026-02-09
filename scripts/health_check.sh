#!/usr/bin/env bash
# =============================================================================
# Traffic-Eye: Health Check Script
# =============================================================================
#
# Monitors system health on a Raspberry Pi running Traffic-Eye.
# Intended to run via cron every 15 minutes.
#
# Checks:
#   - CPU temperature (warning at 70C, critical at 80C)
#   - Throttling / undervoltage status
#   - Disk space usage
#   - traffic-eye service status
#   - Recent errors in journal
#   - Memory usage
#
# Output: Prints status to stdout (logged by cron to health.log)
# Alerts: Writes critical issues to /var/log/traffic-eye/alerts.log
#         Optionally sends email if ALERT_EMAIL is configured.
#
# Usage:
#   sudo bash scripts/health_check.sh
#   sudo bash scripts/health_check.sh --verbose
#   sudo bash scripts/health_check.sh --json
#
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
readonly ALERT_LOG="/var/log/traffic-eye/alerts.log"
readonly SERVICE_NAME="traffic-eye"
readonly TEMP_WARN=70
readonly TEMP_CRIT=80
readonly DISK_WARN=80
readonly DISK_CRIT=90
readonly MEM_WARN=85

# Parse arguments
VERBOSE=false
JSON_OUTPUT=false
for arg in "$@"; do
    case "$arg" in
        --verbose|-v) VERBOSE=true ;;
        --json|-j) JSON_OUTPUT=true ;;
    esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
ALERTS=()
WARNINGS=()
STATUS="OK"

add_alert() {
    ALERTS+=("$1")
    STATUS="CRITICAL"
    echo "[ALERT] $1" >> "$ALERT_LOG" 2>/dev/null || true
}

add_warning() {
    WARNINGS+=("$1")
    if [ "$STATUS" = "OK" ]; then
        STATUS="WARNING"
    fi
}

# ---------------------------------------------------------------------------
# Check 1: CPU Temperature
# ---------------------------------------------------------------------------
check_temperature() {
    local temp_raw temp_c
    if command -v vcgencmd >/dev/null 2>&1; then
        temp_raw=$(vcgencmd measure_temp 2>/dev/null || echo "temp=0.0'C")
        temp_c=$(echo "$temp_raw" | grep -oP '[0-9]+\.?[0-9]*' | head -1)
    else
        # Fallback to thermal zone (works on non-Pi Linux too)
        if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
            local temp_milli
            temp_milli=$(cat /sys/class/thermal/thermal_zone0/temp)
            temp_c=$(echo "scale=1; $temp_milli / 1000" | bc)
        else
            temp_c="0"
        fi
    fi

    CPU_TEMP="$temp_c"

    local temp_int=${temp_c%.*}
    if [ "$temp_int" -ge "$TEMP_CRIT" ]; then
        add_alert "CPU temperature CRITICAL: ${temp_c}C (threshold: ${TEMP_CRIT}C)"
    elif [ "$temp_int" -ge "$TEMP_WARN" ]; then
        add_warning "CPU temperature HIGH: ${temp_c}C (threshold: ${TEMP_WARN}C)"
    fi
}

# ---------------------------------------------------------------------------
# Check 2: Throttling / Undervoltage
# ---------------------------------------------------------------------------
check_throttling() {
    THROTTLE_HEX="N/A"
    THROTTLE_STATUS="unknown"

    if ! command -v vcgencmd >/dev/null 2>&1; then
        return 0
    fi

    local throttled
    throttled=$(vcgencmd get_throttled 2>/dev/null || echo "throttled=0x0")
    THROTTLE_HEX=$(echo "$throttled" | grep -oP '0x[0-9a-fA-F]+' || echo "0x0")

    local flags
    flags=$((THROTTLE_HEX))

    THROTTLE_STATUS=""

    # Current state bits
    if (( flags & 0x1 )); then
        THROTTLE_STATUS+="UNDERVOLTAGE_NOW "
        add_alert "Undervoltage detected NOW. Check power supply (need 5V/3A+)."
    fi
    if (( flags & 0x2 )); then
        THROTTLE_STATUS+="ARM_FREQ_CAPPED "
        add_warning "ARM frequency capped (thermal or voltage)."
    fi
    if (( flags & 0x4 )); then
        THROTTLE_STATUS+="THROTTLED_NOW "
        add_alert "CPU is being throttled NOW."
    fi
    if (( flags & 0x8 )); then
        THROTTLE_STATUS+="SOFT_TEMP_LIMIT "
        add_warning "Soft temperature limit reached."
    fi

    # Historical bits (since last reboot)
    if (( flags & 0x10000 )); then
        THROTTLE_STATUS+="undervoltage_occurred "
    fi
    if (( flags & 0x20000 )); then
        THROTTLE_STATUS+="arm_freq_capped_occurred "
    fi
    if (( flags & 0x40000 )); then
        THROTTLE_STATUS+="throttled_occurred "
    fi
    if (( flags & 0x80000 )); then
        THROTTLE_STATUS+="soft_temp_limit_occurred "
    fi

    if [ -z "$THROTTLE_STATUS" ]; then
        THROTTLE_STATUS="clean"
    fi
}

# ---------------------------------------------------------------------------
# Check 3: Disk Space
# ---------------------------------------------------------------------------
check_disk() {
    DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | tr -d '%')
    DISK_AVAIL=$(df -h / | awk 'NR==2 {print $4}')

    if [ "$DISK_USAGE" -ge "$DISK_CRIT" ]; then
        add_alert "Disk usage CRITICAL: ${DISK_USAGE}% (only ${DISK_AVAIL} free)"
    elif [ "$DISK_USAGE" -ge "$DISK_WARN" ]; then
        add_warning "Disk usage HIGH: ${DISK_USAGE}% (${DISK_AVAIL} free)"
    fi

    # Check data directory specifically
    if [ -d /var/lib/traffic-eye ]; then
        DATA_SIZE=$(du -sh /var/lib/traffic-eye 2>/dev/null | cut -f1)
    else
        DATA_SIZE="N/A"
    fi
}

# ---------------------------------------------------------------------------
# Check 4: Service Status
# ---------------------------------------------------------------------------
check_service() {
    SERVICE_STATUS="unknown"
    SERVICE_UPTIME="N/A"
    SERVICE_MEMORY="N/A"

    if ! systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        SERVICE_STATUS="inactive"
        if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
            add_alert "Service '${SERVICE_NAME}' is enabled but NOT running."
        else
            add_warning "Service '${SERVICE_NAME}' is not enabled."
        fi
        return 0
    fi

    SERVICE_STATUS="active"

    # Get uptime from service start time
    local active_since
    active_since=$(systemctl show "$SERVICE_NAME" --property=ActiveEnterTimestamp --value 2>/dev/null || echo "")
    if [ -n "$active_since" ]; then
        local start_epoch now_epoch
        start_epoch=$(date -d "$active_since" +%s 2>/dev/null || echo "0")
        now_epoch=$(date +%s)
        local uptime_sec=$(( now_epoch - start_epoch ))
        local days=$(( uptime_sec / 86400 ))
        local hours=$(( (uptime_sec % 86400) / 3600 ))
        local mins=$(( (uptime_sec % 3600) / 60 ))
        SERVICE_UPTIME="${days}d ${hours}h ${mins}m"
    fi

    # Get memory usage of main process
    local main_pid
    main_pid=$(systemctl show "$SERVICE_NAME" --property=MainPID --value 2>/dev/null || echo "0")
    if [ "$main_pid" -gt 0 ] && [ -f "/proc/${main_pid}/status" ]; then
        SERVICE_MEMORY=$(awk '/VmRSS/ {printf "%.0fMB", $2/1024}' "/proc/${main_pid}/status" 2>/dev/null || echo "N/A")
    fi

    # Check restart count (many restarts = instability)
    local restart_count
    restart_count=$(systemctl show "$SERVICE_NAME" --property=NRestarts --value 2>/dev/null || echo "0")
    if [ "$restart_count" -gt 5 ]; then
        add_warning "Service has restarted ${restart_count} times since last daemon-reload."
    fi
}

# ---------------------------------------------------------------------------
# Check 5: Recent Journal Errors
# ---------------------------------------------------------------------------
check_journal_errors() {
    RECENT_ERRORS=0

    if command -v journalctl >/dev/null 2>&1; then
        RECENT_ERRORS=$(journalctl -u "$SERVICE_NAME" --since "15 min ago" -p err --no-pager -q 2>/dev/null | wc -l || echo "0")
        if [ "$RECENT_ERRORS" -gt 10 ]; then
            add_warning "High error rate: ${RECENT_ERRORS} errors in the last 15 minutes."
        fi
    fi
}

# ---------------------------------------------------------------------------
# Check 6: Memory Usage
# ---------------------------------------------------------------------------
check_memory() {
    MEM_TOTAL=$(free -m | awk '/^Mem:/ {print $2}')
    MEM_USED=$(free -m | awk '/^Mem:/ {print $3}')
    MEM_PERCENT=$(( MEM_USED * 100 / MEM_TOTAL ))
    SWAP_USED=$(free -m | awk '/^Swap:/ {print $3}')

    if [ "$MEM_PERCENT" -ge "$MEM_WARN" ]; then
        add_warning "Memory usage HIGH: ${MEM_PERCENT}% (${MEM_USED}MB / ${MEM_TOTAL}MB)"
    fi

    if [ "$SWAP_USED" -gt 100 ]; then
        add_warning "Significant swap usage: ${SWAP_USED}MB (indicates memory pressure)"
    fi
}

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
output_text() {
    echo "=========================================="
    echo " Traffic-Eye Health Report"
    echo " ${TIMESTAMP}"
    echo "=========================================="
    echo ""
    echo "Status:           ${STATUS}"
    echo ""
    echo "--- System ---"
    echo "CPU Temperature:  ${CPU_TEMP}C"
    echo "Throttle Status:  ${THROTTLE_STATUS}"
    echo "Throttle Flags:   ${THROTTLE_HEX}"
    echo "Memory:           ${MEM_USED}MB / ${MEM_TOTAL}MB (${MEM_PERCENT}%)"
    echo "Swap Used:        ${SWAP_USED}MB"
    echo "Disk Usage:       ${DISK_USAGE}% (${DISK_AVAIL} free)"
    echo "Data Dir Size:    ${DATA_SIZE}"
    echo ""
    echo "--- Service ---"
    echo "Service Status:   ${SERVICE_STATUS}"
    echo "Service Uptime:   ${SERVICE_UPTIME}"
    echo "Service Memory:   ${SERVICE_MEMORY}"
    echo "Recent Errors:    ${RECENT_ERRORS} (last 15min)"
    echo ""

    if [ ${#ALERTS[@]} -gt 0 ]; then
        echo "--- ALERTS ---"
        for alert in "${ALERTS[@]}"; do
            echo "  [!!] ${alert}"
        done
        echo ""
    fi

    if [ ${#WARNINGS[@]} -gt 0 ]; then
        echo "--- WARNINGS ---"
        for warn in "${WARNINGS[@]}"; do
            echo "  [!]  ${warn}"
        done
        echo ""
    fi
}

output_json() {
    local alerts_json="[]"
    local warnings_json="[]"

    if [ ${#ALERTS[@]} -gt 0 ]; then
        alerts_json=$(printf '%s\n' "${ALERTS[@]}" | python3 -c "import sys,json; print(json.dumps([l.strip() for l in sys.stdin]))" 2>/dev/null || echo "[]")
    fi
    if [ ${#WARNINGS[@]} -gt 0 ]; then
        warnings_json=$(printf '%s\n' "${WARNINGS[@]}" | python3 -c "import sys,json; print(json.dumps([l.strip() for l in sys.stdin]))" 2>/dev/null || echo "[]")
    fi

    cat << JSONEOF
{
  "timestamp": "${TIMESTAMP}",
  "status": "${STATUS}",
  "system": {
    "cpu_temp_c": ${CPU_TEMP},
    "throttle_hex": "${THROTTLE_HEX}",
    "throttle_status": "${THROTTLE_STATUS}",
    "memory_used_mb": ${MEM_USED},
    "memory_total_mb": ${MEM_TOTAL},
    "memory_percent": ${MEM_PERCENT},
    "swap_used_mb": ${SWAP_USED},
    "disk_usage_percent": ${DISK_USAGE},
    "disk_available": "${DISK_AVAIL}",
    "data_dir_size": "${DATA_SIZE}"
  },
  "service": {
    "status": "${SERVICE_STATUS}",
    "uptime": "${SERVICE_UPTIME}",
    "memory": "${SERVICE_MEMORY}",
    "recent_errors": ${RECENT_ERRORS}
  },
  "alerts": ${alerts_json},
  "warnings": ${warnings_json}
}
JSONEOF
}

# ---------------------------------------------------------------------------
# Email alert (optional)
# ---------------------------------------------------------------------------
send_alert_email() {
    # Only send if we have alerts (not warnings) and mail is configured
    if [ ${#ALERTS[@]} -eq 0 ]; then
        return 0
    fi

    # Check if ALERT_EMAIL is set in environment file
    local alert_email=""
    if [ -f /etc/traffic-eye.env ]; then
        alert_email=$(grep -oP '^TRAFFIC_EYE_ALERT_EMAIL=\K.*' /etc/traffic-eye.env 2>/dev/null || echo "")
    fi

    if [ -z "$alert_email" ]; then
        return 0
    fi

    # Rate limit: only send one alert per hour
    local rate_limit_file="/tmp/traffic-eye-alert-sent"
    if [ -f "$rate_limit_file" ]; then
        local last_sent
        last_sent=$(stat -c %Y "$rate_limit_file" 2>/dev/null || echo "0")
        local now
        now=$(date +%s)
        if (( now - last_sent < 3600 )); then
            return 0
        fi
    fi

    local hostname
    hostname=$(hostname)
    local subject="[Traffic-Eye ALERT] ${hostname}: ${#ALERTS[@]} critical issue(s)"
    local body
    body=$(output_text)

    if command -v mail >/dev/null 2>&1; then
        echo "$body" | mail -s "$subject" "$alert_email" 2>/dev/null || true
        touch "$rate_limit_file"
    elif command -v sendmail >/dev/null 2>&1; then
        {
            echo "Subject: $subject"
            echo "To: $alert_email"
            echo ""
            echo "$body"
        } | sendmail "$alert_email" 2>/dev/null || true
        touch "$rate_limit_file"
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    # Ensure alert log directory exists
    mkdir -p "$(dirname "$ALERT_LOG")" 2>/dev/null || true

    # Run all checks
    check_temperature
    check_throttling
    check_disk
    check_service
    check_journal_errors
    check_memory

    # Output results
    if [ "$JSON_OUTPUT" = true ]; then
        output_json
    else
        output_text
    fi

    # Send email alert if needed
    send_alert_email

    # Exit code reflects status
    case "$STATUS" in
        OK)       exit 0 ;;
        WARNING)  exit 1 ;;
        CRITICAL) exit 2 ;;
        *)        exit 3 ;;
    esac
}

main "$@"
