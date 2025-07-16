# Eight Sleep Alarm API Update Guide
# Author: https://github.com/nroszko

## Overview

Eight Sleep removed the "Routines" feature from their app, breaking existing alarm management functionality. This update replaces the broken routine-based alarm system with the new direct alarm API that the Eight Sleep app currently uses.

## What's Fixed

### ✅ Working Again
- **Alarm retrieval**: Now fetches alarm data from device endpoint 
- **Alarm enable/disable**: Uses new direct PUT API to `/v1/users/{user_id}/alarms/{alarm_id}`
- **Alarm configuration**: Full access to all alarm settings (time, vibration, thermal, smart features, weekdays)
- **Next alarm detection**: Automatically finds next scheduled alarm
- **Legacy compatibility**: Old methods still work but use new API internally

### ❌ Still Limitations
- **Creating new alarms**: Not possible via API - must use Eight Sleep app
- **Snooze/Stop/Dismiss**: May need API endpoint updates (old routine endpoints might not work)

## New Alarm Management Functions

### Basic Alarm Control
```python
# Enable/disable by alarm ID
await user.enable_alarm(alarm_id)
await user.disable_alarm(alarm_id)

# Enable/disable by time
await user.enable_alarm_by_time("04:30")
await user.disable_alarm_by_time("16:00")

# Bulk operations
await user.enable_all_alarms()
await user.disable_all_alarms()
```

### Alarm Information
```python
# Get all alarms
all_alarms = user.get_all_alarms()
enabled_alarms = user.get_enabled_alarms()
disabled_alarms = user.get_disabled_alarms()

# Find specific alarms
alarm = user.get_alarm_by_time("04:30")
alarm = user.get_alarm_by_id("7c9ad0b0-348e-419b-b70d-6b29223f3fff")
next_alarm = user.get_next_scheduled_alarm()
```

### Advanced Configuration
```python
# Comprehensive alarm setup
await user.set_alarm_direct(
    alarm_id="alarm_id_here",
    enabled=True,
    time="05:00:00",
    weekdays={
        "monday": True, "tuesday": True, "wednesday": True,
        "thursday": True, "friday": True, "saturday": False, "sunday": False
    },
    vibration_enabled=True,
    vibration_power=60,
    vibration_pattern="INTENSE",
    thermal_enabled=True,
    thermal_level=25,
    smart_light_sleep=True,
    smart_sleep_cap=False
)

# Individual setting updates
await user.set_alarm_time(alarm_id, "05:30:00")
await user.set_alarm_weekdays(alarm_id, {"monday": True, "friday": True})
await user.set_alarm_vibration(alarm_id, True, 75, "GENTLE")
await user.set_alarm_thermal(alarm_id, True, 50)
await user.set_alarm_smart_features(alarm_id, light_sleep=True, sleep_cap=True)
```

## New Bedtime Scheduling Functions

### Set Complete Bedtime Profile
```python
# Set bedtime with smart temperature control
await user.set_bedtime_schedule(
    bedtime="22:30:00",
    bedtime_temp=-11,        # Cool prep temperature
    initial_sleep_temp=-8,   # Initial sleep comfort
    final_sleep_temp=-8,     # Maintain through night
    days=["monday", "tuesday", "wednesday", "thursday", "friday"]
)

# Update just temperatures
await user.set_bedtime_temp_levels(
    bedtime_temp=-12,
    initial_sleep_temp=-10
)

# Update just schedule time
await user.set_bedtime_time("23:00:00", ["friday", "saturday"])

# Get current bedtime settings
bedtime_settings = await user.get_bedtime_settings()
```

## Updated Files

### 1. `user.py` - Core Functionality
**New Methods Added:**
- `get_alarm_by_id()`, `get_alarm_by_time()`, `get_all_alarms()`
- `enable_alarm()`, `disable_alarm()`, `enable_alarm_by_time()`, `disable_alarm_by_time()`
- `set_alarm_direct()` - Main comprehensive alarm configuration
- `set_alarm_time()`, `set_alarm_weekdays()`, `set_alarm_vibration()`, `set_alarm_thermal()`
- `enable_all_alarms()`, `disable_all_alarms()`
- `get_next_scheduled_alarm()`, `update_alarm_data()`
- `set_bedtime_schedule()`, `get_bedtime_settings()`, `set_bedtime_temp_levels()`, `set_bedtime_time()`
- `bootstrap_alarm_discovery()` - Automatic alarm detection

**Updated Methods:**
- `update_user()` - Now calls `update_alarm_data()` instead of `update_routines_data()`
- `get_alarm_enabled()` - Uses new alarm data structure
- `set_alarm_enabled()` - Routes to new API (ignores routine_id parameter)
- `update_routines_data()` - Now calls `update_alarm_data()` for compatibility

### 2. `alarm_manager_demo.py` - Comprehensive Demo
- Full demonstration of all new features
- Examples for external application integration
- Shows advanced configuration options
- Testing and verification examples

### 3. `eight_sleep_profile.py` - Enhanced Profile Management
- Complete bedtime and alarm automation
- Shift work profile optimization (DayShift, NightShift, DaysOff)
- Smart temperature scheduling
- Work-day vs weekend alarm configuration

## Usage Examples

### Quick Alarm Control
```python
import asyncio
from pyEight.eight import EightSleep

async def enable_morning_alarm():
    es = EightSleep(email, password, timezone)
    try:
        await es.start()
        await es.update_device_data()
        await es.update_user_data()
        
        # Find your user
        user = next(u for u in es.users.values() 
                   if u.user_profile.get('firstName') == 'YourName')
        
        # Enable 6:30 AM alarm for work days only
        alarm = user.get_alarm_by_time("06:30")
        if alarm:
            await user.set_alarm_direct(
                alarm_id=alarm['id'],
                enabled=True,
                weekdays={
                    "monday": True, "tuesday": True, "wednesday": True,
                    "thursday": True, "friday": True, 
                    "saturday": False, "sunday": False
                }
            )
            return True
        return False
    finally:
        await es.stop()

# Use it
success = asyncio.run(enable_morning_alarm())
```

### Profile Management Scripts
```bash
# Run comprehensive demo
python alarm_manager_demo.py

# Set work profiles
python eight_sleep_profile.py DayShift     # Evening bedtime + 04:30 alarm
python eight_sleep_profile.py NightShift  # Morning bedtime + 16:00 alarm  
python eight_sleep_profile.py DaysOff     # Relaxed schedule + disable work alarms
```

## API Endpoint Details

### What We Discovered
1. **Device Data Contains Alarms**: Alarm information is returned in device data under `{side}Kelvin.alarms`
2. **Direct Alarm API**: `PUT /v1/users/{user_id}/alarms/{alarm_id}` for alarm control
3. **Bedtime API**: `PUT /v1/users/{user_id}/bedtime` for bedtime scheduling
4. **No Individual GET**: The `GET /v1/users/{user_id}/alarms/{alarm_id}` returns 405 Method Not Allowed
5. **Timestamp Handling**: Disabled alarms get `startTimestamp` and `endTimestamp` fields

### Request Structure
```json
{
  "id": "alarm_id",
  "enabled": true,
  "time": "04:30:00",
  "repeat": {
    "enabled": true,
    "weekDays": {
      "monday": true, "tuesday": true, "wednesday": true,
      "thursday": true, "friday": true, "saturday": true, "sunday": true
    }
  },
  "vibration": {
    "enabled": true,
    "powerLevel": 50,
    "pattern": "INTENSE"
  },
  "thermal": {
    "enabled": false,
    "level": 50
  },
  "smart": {
    "lightSleepEnabled": true,
    "sleepCapEnabled": false,
    "sleepCapMinutes": 480
  },
  "audio": {
    "enabled": false,
    "trackId": "futuristic",
    "level": 30
  },
  "snoozing": false
}
```

## Migration Notes

### From Old Code
```python
# OLD (broken)
await user.set_alarm_enabled(routine_id, alarm_id, True)

# NEW (working)
await user.enable_alarm(alarm_id)
# OR
await user.enable_alarm_by_time("04:30")
```

### Compatibility
- All existing code should work without changes
- Old method signatures preserved but use new API internally
- `routine_id` parameter is ignored in `set_alarm_enabled()`

## Troubleshooting

### Common Issues
1. **405 Method Not Allowed**: Use device endpoint to get alarm data, not individual alarm GET
2. **Alarm not found**: Check alarm exists using `get_all_alarms()` first
3. **Changes not visible**: Call `update_alarm_data()` to refresh from server
4. **Authentication errors**: Ensure credentials are correct and API access is working

### Debug Steps
```python
# Check alarm data
user = target_user
all_alarms = user.get_all_alarms()
print(f"Found {len(all_alarms)} alarms")
for alarm in all_alarms:
    print(f"  {alarm.get('time')}: {'enabled' if alarm.get('enabled') else 'disabled'}")

# Test basic enable/disable
if all_alarms:
    test_alarm = all_alarms[0]
    success = await user.enable_alarm(test_alarm['id'])
    print(f"Enable test: {'success' if success else 'failed'}")
```

This update restores full alarm management functionality and provides a foundation for advanced automation features.