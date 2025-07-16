# pyEight

Python library to interact with the Eight Sleep API for temperature control, alarm management, and bedtime scheduling.

> **⚠️ Important Update**: Eight Sleep removed the "Routines" feature from their app, which broke alarm functionality. This library has been updated with working alarm management using the new direct API endpoints.

## 🆕 What's New (2025)

### ✅ **Alarm Management Restored**
- **Fixed broken alarm functionality** after Eight Sleep's Routines removal
- **Direct alarm control** using new API endpoints
- **Comprehensive alarm configuration** (time, vibration, thermal, smart features)
- **Bedtime scheduling** with smart temperature profiles
- **Backward compatibility** - existing code continues to work

### ✅ **New Features**
- Enable/disable alarms by time: `await user.enable_alarm_by_time("06:30")`
- Bedtime automation: `await user.set_bedtime_schedule("22:30:00", bedtime_temp=-10)`
- Advanced alarm settings: vibration patterns, thermal wake, smart features
- Shift work profiles and automation examples

## Requirements

* Python >= 3.11
* aiohttp >= 2.0
* asyncio
* httpx

## Authentication

You'll need your Eight Sleep credentials:
* Email address
* Password  
* Timezone (e.g., "America/New_York")

Optional for advanced features:
* client_id (can use built-in default)
* client_secret (can use built-in default)

## Installation

```bash
pip install pyeight
```

## Quick Start

### Basic Temperature Control

```python
from pyEight.eight import EightSleep
import asyncio

async def basic_temperature_control():
    eight = EightSleep("your-email@example.com", "your-password", "America/New_York")
    
    try:
        await eight.start()
        await eight.update_device_data()
        await eight.update_user_data()
        
        # Get your user
        user = next(iter(eight.users.values()))
        
        # Set temperature
        await user.set_heating_level(-10)  # Cool
        print("Temperature set!")
        
    finally:
        await eight.stop()

asyncio.run(basic_temperature_control())
```

### Alarm Management

```python
from pyEight.eight import EightSleep
import asyncio

async def alarm_management():
    eight = EightSleep("your-email@example.com", "your-password", "America/New_York")
    
    try:
        await eight.start()
        await eight.update_device_data()
        await eight.update_user_data()
        
        # Get your user
        user = next(iter(eight.users.values()))
        
        # Simple alarm control
        await user.enable_alarm_by_time("06:30")
        await user.disable_alarm_by_time("07:00")
        
        # Advanced alarm configuration
        alarm = user.get_alarm_by_time("06:30")
        if alarm:
            await user.set_alarm_direct(
                alarm_id=alarm['id'],
                enabled=True,
                weekdays={
                    "monday": True, "tuesday": True, "wednesday": True,
                    "thursday": True, "friday": True, 
                    "saturday": False, "sunday": False
                },
                vibration_power=75,
                thermal_enabled=True,
                smart_light_sleep=True
            )
        
        print("Alarms configured!")
        
    finally:
        await eight.stop()

asyncio.run(alarm_management())
```

### Bedtime Scheduling

```python
from pyEight.eight import EightSleep
import asyncio

async def bedtime_automation():
    eight = EightSleep("your-email@example.com", "your-password", "America/New_York")
    
    try:
        await eight.start()
        await eight.update_device_data()
        await eight.update_user_data()
        
        # Get your user
        user = next(iter(eight.users.values()))
        
        # Set bedtime schedule with smart temperature control
        await user.set_bedtime_schedule(
            bedtime="22:30:00",
            bedtime_temp=-11,        # Cool prep temperature
            initial_sleep_temp=-8,   # Comfortable initial sleep
            final_sleep_temp=-8,     # Maintain through night
            days=["monday", "tuesday", "wednesday", "thursday", "friday"]
        )
        
        print("Bedtime schedule set!")
        
    finally:
        await eight.stop()

asyncio.run(bedtime_automation())
```

## Advanced Usage

### Get Alarm Information

```python
# Get all alarms
all_alarms = user.get_all_alarms()
enabled_alarms = user.get_enabled_alarms()
next_alarm = user.get_next_scheduled_alarm()

# Find specific alarm
morning_alarm = user.get_alarm_by_time("06:30")
```

### Advanced Alarm Configuration

```python
# Configure specific alarm features
await user.set_alarm_vibration(alarm_id, enabled=True, power=60, pattern="INTENSE")
await user.set_alarm_thermal(alarm_id, enabled=True, level=25)
await user.set_alarm_smart_features(alarm_id, light_sleep=True, sleep_cap=False)

# Set weekday schedule
work_days = {
    "monday": True, "tuesday": True, "wednesday": True,
    "thursday": True, "friday": True, "saturday": False, "sunday": False
}
await user.set_alarm_weekdays(alarm_id, work_days)
```

### Bulk Operations

```python
# Enable or disable all alarms
await user.enable_all_alarms()
await user.disable_all_alarms()
```

### Temperature Management

```python
# Set immediate temperature
await user.set_heating_level(-10)  # Cool
await user.set_heating_level(0)    # Neutral
await user.set_heating_level(10)   # Warm

# Set temperature with duration
await user.set_heating_level(15, duration=3600)  # 1 hour

# Smart heating levels for sleep stages
await user.set_smart_heating_level(-5, "bedTimeLevel")
await user.set_smart_heating_level(-8, "initialSleepLevel")
await user.set_smart_heating_level(-8, "finalSleepLevel")
```

## Example Scripts

The library includes comprehensive example scripts:

### `examples/alarm_manager_demo.py`
Complete demonstration of alarm management features:
- List and filter alarms
- Enable/disable individual and bulk alarms
- Advanced configuration examples
- Testing and verification

### `examples/eight_sleep_profile.py`
Advanced profile management for shift workers:
- **DayShift**: Evening bedtime + 04:30 alarm + work schedule
- **NightShift**: Morning bedtime + 16:00 alarm + daytime sleep
- **DaysOff**: Relaxed schedule + disable work alarms

```bash
# Run profile examples
python examples/eight_sleep_profile.py DayShift
python examples/eight_sleep_profile.py NightShift
python examples/eight_sleep_profile.py DaysOff

# Run comprehensive demo
python examples/alarm_manager_demo.py
```

## API Methods

### Alarm Management
- `get_all_alarms()` - Get all alarms
- `get_enabled_alarms()` - Get enabled alarms only
- `get_alarm_by_time(time)` - Find alarm by time
- `enable_alarm_by_time(time)` - Enable alarm by time
- `disable_alarm_by_time(time)` - Disable alarm by time
- `set_alarm_direct(**kwargs)` - Comprehensive alarm configuration
- `enable_all_alarms()` - Enable all alarms
- `disable_all_alarms()` - Disable all alarms

### Bedtime Scheduling
- `set_bedtime_schedule()` - Set bedtime with temperature profile
- `get_bedtime_settings()` - Get current bedtime configuration  
- `set_bedtime_temp_levels()` - Update temperature settings only
- `set_bedtime_time()` - Update schedule time only

### Temperature Control
- `set_heating_level(level, duration=0)` - Set immediate temperature
- `set_smart_heating_level(level, stage)` - Set temperature for sleep stage
- `get_current_heating_level()` - Get current temperature setting
- `turn_on_side()` / `turn_off_side()` - Control side power

### Device Control
- `set_base_angle(leg, torso)` - Control bed base (if available)
- `set_base_preset(preset)` - Set bed base preset
- `prime_pod()` - Prime the pod system
- `set_away_mode(action)` - Set away mode

## Migration from Old Code

If you were using the old routine-based alarm system:

```python
# OLD (broken after Routines removal)
await user.set_alarm_enabled(routine_id, alarm_id, True)

# NEW (working)
await user.enable_alarm(alarm_id)
# OR
await user.enable_alarm_by_time("06:30")
```

All existing code continues to work - old methods internally use the new API.

## Troubleshooting

### Alarm Issues
1. **"No alarms found"**: The library will automatically try to discover alarms
2. **"405 Method Not Allowed"**: This is expected for some endpoints - the library handles this
3. **Changes not visible**: Call `await user.update_alarm_data()` to refresh

### Authentication Issues
1. **Invalid credentials**: Verify email/password work in the Eight Sleep app
2. **API errors**: The library includes built-in client credentials that should work

### Debug Mode
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

This library is actively maintained. Contributions welcome!

### Recent Major Updates
- **2025**: Complete alarm API overhaul after Eight Sleep Routines removal
- **2025**: Added bedtime scheduling and automation features
- **2025**: Added comprehensive examples and documentation

## Thanks

* **@mezz64** - Original pyEight python library foundation
* **@lukas-clarke** - OAuth2 implementation and ongoing maintenance  
* **Contributors** - Alarm API fixes and bedtime automation features

## Home Assistant Integration

This library is used in the official Home Assistant Eight Sleep integration:
https://github.com/lukas-clarke/eight_sleep

## License

MIT License - see LICENSE file for details.
