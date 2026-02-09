# Power Supply Guide for Traffic-Eye System

## Current Status

Your Raspberry Pi is showing throttling warnings: `0x50005`

This indicates **past power issues** but the system is currently stable.

## What Does This Mean?

| Bit | Meaning | Status |
|-----|---------|--------|
| 0x1 | Under-voltage detected | ⚠️ Occurred in the past |
| 0x4 | ARM frequency capped | ⚠️ Occurred in the past |
| 0x10000 | Under-voltage since boot | ⚠️ Has occurred |
| 0x40000 | Frequency capping since boot | ⚠️ Has occurred |

## Why This Matters

Under-voltage can cause:
- ❌ **SD card corruption** (data loss)
- ❌ **System crashes** and freezes
- ❌ **Camera initialization failures**
- ❌ **Reduced performance** (CPU throttling)
- ❌ **Unreliable operation** in production

## Recommended Power Supply

For Raspberry Pi 4 with camera:

✅ **Official Raspberry Pi 5V/3A USB-C Power Supply**
- Model: SC0218 (UK), SC0212 (US/EU)
- Output: 5.1V @ 3A (15W)
- Price: ~$8-10

### Alternative Options

1. **Anker PowerPort III Mini** (18W USB-C PD)
   - Higher quality, less voltage drop
   - Price: ~$15

2. **CanaKit 5V/3.5A USB-C Power Supply**
   - Good alternative to official
   - Price: ~$10

3. **For Field Deployment**: Use a **power bank** (20,000mAh+)
   - Anker PowerCore 20100 (3A output)
   - RAVPower 26800 PD

## How to Check Power Supply

```bash
# Check current status (should be 0x0 when healthy)
vcgencmd get_throttled

# Monitor voltage in real-time
watch -n 1 vcgencmd get_throttled

# Check power supply voltage (should be ~5.0-5.2V)
vcgencmd pmic_read_adc EXT5V_V
```

### Healthy Output

```
throttled=0x0
```

### Current Output (Warning)

```
throttled=0x50005
```

## Cable Quality Also Matters

- Use **short, thick USB-C cables** (< 1m, 20 AWG or better)
- Avoid thin, long cables (voltage drop)
- Official Raspberry Pi cable recommended

## Temporary Workaround

If you can't upgrade immediately, reduce power consumption:

```yaml
# Edit config/settings.yaml
camera:
  fps: 10  # Lower FPS (currently 15)
  process_every_nth_frame: 5  # Process fewer frames (currently 3)
```

## Verifying the Fix

After replacing power supply:

1. Reboot the Pi
2. Wait 5 minutes
3. Check status:
   ```bash
   vcgencmd get_throttled
   ```
4. Should show: `throttled=0x0`

## Field Deployment Power Options

### Option 1: AC Power (Mains)
- Use official power supply
- Ensure stable mains voltage
- Consider UPS for critical deployments

### Option 2: Battery Power
- 20,000mAh power bank (~8-10 hours runtime)
- USB-C Power Delivery (PD) support required
- Solar panel for extended deployment

### Option 3: Car Power (12V)
- 12V to 5V USB-C converter (3A minimum)
- Example: Anker 24W Dual USB Car Charger
- Wire directly to vehicle battery (with fuse)

## Impact on Camera

The OV5647 camera draws additional current:
- Camera active: +250mA
- With IR LEDs: +500mA
- Total system load: ~2.5A (camera + Pi + processing)

**This is why a 3A supply is critical.**

## Monitoring in Production

Add this to your monitoring script:

```bash
#!/bin/bash
# check_power.sh

THROTTLED=$(vcgencmd get_throttled | cut -d'=' -f2)

if [ "$THROTTLED" != "0x0" ]; then
    echo "⚠️  POWER WARNING: $THROTTLED"
    # Send alert (email, SMS, etc.)
    exit 1
else
    echo "✅ Power supply healthy"
    exit 0
fi
```

Add to crontab for hourly checks:
```bash
0 * * * * /home/yashcs/traffic-eye/scripts/check_power.sh >> /var/log/power_check.log 2>&1
```

## Summary

| Component | Current | Required | Status |
|-----------|---------|----------|--------|
| Power Supply | Unknown | 5V/3A | ⚠️ Upgrade recommended |
| Cable | Unknown | 20 AWG, <1m | ⚠️ Check quality |
| Voltage | Unknown | 5.0-5.2V | ⚠️ Measure with multimeter |
| Temperature | 40°C | <70°C | ✅ Good |
| CPU Usage | 80% | <90% | ✅ Good |

## Next Steps

1. **Immediate**: System is working, monitor for crashes
2. **Within 24 hours**: Order official power supply
3. **Before production**: Replace power supply and verify `0x0` status
4. **Long term**: Add power monitoring to alerting system

## Questions?

If you experience:
- Random reboots → Power supply
- SD card corruption → Power supply
- Camera not initializing → Power supply
- System freezing → Power supply

**90% of Raspberry Pi issues are power-related.**
