#!/bin/bash
# Power health monitoring script for Raspberry Pi

echo "=== Raspberry Pi Power Status ==="

# Check throttling status
THROTTLED=$(vcgencmd get_throttled)
echo "Throttle Status: $THROTTLED"

if [ "$THROTTLED" != "throttled=0x0" ]; then
    echo "⚠️  WARNING: Throttling detected!"
    echo "   0x50000 = Under-voltage occurred in the past"
    echo "   0x50005 = Currently under-voltage + throttled"
    echo "   Action: Use better power supply or reduce load"
fi

# Check CPU temperature
TEMP=$(vcgencmd measure_temp | cut -d= -f2 | cut -d\' -f1)
echo "CPU Temperature: ${TEMP}°C"

if (( $(echo "$TEMP > 80" | bc -l) )); then
    echo "⚠️  WARNING: High temperature! Consider adding cooling."
fi

# Check voltage
for id in core sdram_c sdram_i sdram_p ; do
    echo "Voltage $id: $(vcgencmd measure_volts $id)"
done

# Check power supply current
echo "Current limiting: $(vcgencmd get_config max_usb_current)"

echo ""
echo "✅ Power check complete"
