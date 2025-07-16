#!/usr/bin/env python3
"""
eight_sleep_profile.py [DayShift|NightShift|DaysOff]

Enhanced Eight Sleep profile script using new alarm and bedtime APIs:
- DayShift: Evening bedtime routine + enable 04:30 alarm
- NightShift: Morning bedtime routine + enable 16:00 alarm  
- DaysOff: Relaxed routine + disable all work alarms

Usage:
    python eight_sleep_profile.py DayShift
    python eight_sleep_profile.py NightShift
    python eight_sleep_profile.py DaysOff
"""

import sys
import os
import asyncio

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from pyeight.eight import EightSleep

# TODO: ------------------------------------------------------------------------
# TODO: Replace with your actual Eight Sleep credentials ---------------------------------------
EMAIL = "Your8SleepEmail@example.com" # Use your actual Eight Sleep account credentials
PASSWORD = "Your8SleepPassword" # Use your actual Eight Sleep account credentials
PROFILE = "YourName"  # The profile name for your Eight Sleep account.
TIMEZONE = "America/Edmonton"  # Adjust to your timezone
# TODO: Replace with your actual Eight Sleep credentials ---------------------------------------
# TODO: ------------------------------------------------------------------------
CLIENT_ID = None
CLIENT_SECRET = None

# Profile configurations - Now with bedtime scheduling
PROFILES = {
    "DayShift": {
        "description": "Day Shift Profile",
        "bedtime": "20:30:00",  # 08:30 PM bedtime
        "bedtime_temp": -11,    # Cool for evening sleep prep
        "initial_sleep_temp": -8,  # Comfortable initial sleep
        "final_sleep_temp": -8,    # Maintain comfort through night
        "bedtime_days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
        "enable_alarms": ["04:30:00"],  # Enable 04:30 alarm  
        "disable_alarms": ["16:00:00"], # Disable night shift alarm
    },
    "NightShift": {
        "description": "Night Shift Profile", 
        "bedtime": "06:30:00",  # 06:30 AM bedtime (daytime sleep)
        "bedtime_temp": -11,    # Cool for evening sleep prep
        "initial_sleep_temp": -8,  # Comfortable initial sleep
        "final_sleep_temp": -8,    # Maintain comfort through night
        "bedtime_days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
        "enable_alarms": ["16:00:00"],  # Enable 16:00 alarm
        "disable_alarms": ["04:30:00"], # Disable day shift alarm
    },
    "DaysOff": {
        "description": "Days Off Profile",
        "bedtime": "22:30:00",  # Later bedtime on days off
        "bedtime_temp": -11,    # Cool for evening sleep prep
        "initial_sleep_temp": -8,  # Comfortable initial sleep
        "final_sleep_temp": -8,    # Maintain comfort through night
        "bedtime_days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
        "enable_alarms": [],    # No work alarms needed
        "disable_alarms": ["04:30:00", "16:00:00"], # Disable all work alarms
    }
}

async def set_profile(profile_name):
    """Set the Eight Sleep profile using new APIs."""
    
    if profile_name not in PROFILES:
        print(f"❌ Unknown profile: {profile_name}")
        print(f"Available profiles: {', '.join(PROFILES.keys())}")
        return False
    
    profile = PROFILES[profile_name]
    print(f"🔧 Setting Eight Sleep profile: {profile['description']}")
    print("=" * 60)
    
    es = EightSleep(EMAIL, PASSWORD, TIMEZONE, CLIENT_ID, CLIENT_SECRET)
    
    try:
        print("Connecting to Eight Sleep...")
        success = await es.start()
        
        if not success:
            print("❌ Failed to authenticate with Eight Sleep")
            return False
            
        print("✅ Successfully authenticated!")
        
        # Update data
        await es.update_device_data()
        await es.update_user_data()
        
        # Find target user by profile name
        target_user = None
        for user_id, user in es.users.items():
            user_name = user.user_profile.get('firstName', 'User')
            if user_name.lower() == PROFILE.lower():
                target_user = user
                break
        
        if not target_user:
            print(f"❌ {PROFILE} not found")
            return False
            
        print(f"✅ Found {PROFILE} on {target_user.side} side")
        
        # =================================================================
        # 1. SET BEDTIME SCHEDULE
        # =================================================================
        print(f"\n🛏️  Setting bedtime schedule...")
        try:
            success = await target_user.set_bedtime_schedule(
                bedtime=profile['bedtime'],
                bedtime_temp=profile['bedtime_temp'],
                initial_sleep_temp=profile['initial_sleep_temp'],
                final_sleep_temp=profile['final_sleep_temp'],
                days=profile['bedtime_days']
            )
            if success:
                print(f"✅ Bedtime set to {profile['bedtime'][:5]} with smart temperature profile")
                print(f"   📊 Bedtime temp: {profile['bedtime_temp']}°")
                print(f"   📊 Initial sleep: {profile['initial_sleep_temp']}°") 
                print(f"   📊 Final sleep: {profile['final_sleep_temp']}°")
                print(f"   📅 Days: {', '.join(profile['bedtime_days'])}")
            else:
                print(f"❌ Failed to set bedtime schedule")
        except Exception as e:
            print(f"❌ Bedtime schedule error: {e}")
        
        # =================================================================
        # 2. MANAGE ALARMS
        # =================================================================
        print(f"\n⏰ Managing alarms...")
        
        # First, force an alarm data update with debug info
        print("🔍 Updating alarm data...")
        await target_user.update_alarm_data()
        
        # Show current alarm status
        all_alarms = target_user.get_all_alarms()
        if all_alarms:
            print("📋 Current alarm status:")
            for alarm in all_alarms:
                time_str = alarm.get('time', 'Unknown')
                status = "🟢 ENABLED" if alarm.get('enabled') else "🔴 DISABLED"
                alarm_id = alarm.get('id', 'No ID')
                print(f"   {time_str}: {status} (ID: {alarm_id[:8]}...)")
        else:
            print("⚠️  No alarms found in cache")
            
            # Try bootstrap discovery
            print("🔍 Attempting alarm discovery...")
            discovered = await target_user.bootstrap_alarm_discovery()
            if discovered:
                all_alarms = target_user.get_all_alarms()
                print(f"✅ Discovered {len(all_alarms)} alarms!")
                for alarm in all_alarms:
                    time_str = alarm.get('time', 'Unknown')
                    status = "🟢 ENABLED" if alarm.get('enabled') else "🔴 DISABLED"
                    print(f"   {time_str}: {status}")
            else:
                print("❌ Could not discover alarms automatically")
                print("💡 Try running debug_alarm_discovery.py to troubleshoot")
                # Continue anyway - maybe we can discover during enable/disable attempts
        
        alarm_changes_made = False
        
        # Enable target alarms
        for alarm_time in profile['enable_alarms']:
            try:
                # Convert to HH:MM format for lookup
                lookup_time = alarm_time[:5] if len(alarm_time) > 5 else alarm_time
                alarm = target_user.get_alarm_by_time(lookup_time)
                
                if alarm:
                    current_status = alarm.get('enabled', False)
                    if not current_status:
                        # Configure alarm with work-appropriate settings
                        success = await target_user.set_alarm_direct(
                            alarm_id=alarm['id'],
                            enabled=True,
                            time=alarm_time,
                            weekdays={
                                "monday": True, "tuesday": True, "wednesday": True,
                                "thursday": True, "friday": True, "saturday": False, "sunday": False
                            } if profile_name != "DaysOff" else {
                                "monday": False, "tuesday": False, "wednesday": False,
                                "thursday": False, "friday": False, "saturday": True, "sunday": True
                            },
                            vibration_enabled=True,
                            vibration_power=60,
                            vibration_pattern="INTENSE",
                            thermal_enabled=True,
                            thermal_level=25,
                            smart_light_sleep=True,
                            smart_sleep_cap=False
                        )
                        if success:
                            print(f"✅ Enabled and configured {lookup_time} alarm")
                            alarm_changes_made = True
                        else:
                            print(f"❌ Failed to enable {lookup_time} alarm")
                    else:
                        print(f"ℹ️  {lookup_time} alarm already enabled")
                else:
                    print(f"⚠️  {lookup_time} alarm not found")
            except Exception as e:
                print(f"❌ Error enabling {alarm_time} alarm: {e}")
        
        # Disable unwanted alarms
        for alarm_time in profile['disable_alarms']:
            try:
                # Convert to HH:MM format for lookup
                lookup_time = alarm_time[:5] if len(alarm_time) > 5 else alarm_time
                alarm = target_user.get_alarm_by_time(lookup_time)
                
                if alarm:
                    current_status = alarm.get('enabled', False)
                    if current_status:
                        success = await target_user.disable_alarm(alarm['id'])
                        if success:
                            print(f"❌ Disabled {lookup_time} alarm")
                            alarm_changes_made = True
                        else:
                            print(f"❌ Failed to disable {lookup_time} alarm")
                    else:
                        print(f"ℹ️  {lookup_time} alarm already disabled")
                else:
                    print(f"⚠️  {lookup_time} alarm not found")
            except Exception as e:
                print(f"❌ Error disabling {alarm_time} alarm: {e}")
        
        # =================================================================
        # 3. SHOW FINAL STATUS
        # =================================================================
        if alarm_changes_made:
            print(f"\n📋 Updated alarm status:")
            await target_user.update_alarm_data()  # Refresh
            all_alarms = target_user.get_all_alarms()
            for alarm in all_alarms:
                time_str = alarm.get('time', 'Unknown')
                status = "🟢 ENABLED" if alarm.get('enabled') else "🔴 DISABLED"
                
                # Show weekday schedule for enabled alarms
                if alarm.get('enabled'):
                    weekdays = alarm.get('repeat', {}).get('weekDays', {})
                    active_days = [day[:3].title() for day, enabled in weekdays.items() if enabled]
                    day_str = f" ({', '.join(active_days)})" if active_days else ""
                    print(f"   {time_str}: {status}{day_str}")
                else:
                    print(f"   {time_str}: {status}")
        
        # Show next scheduled alarm
        next_alarm = target_user.get_next_scheduled_alarm()
        if next_alarm:
            next_time = next_alarm.get('time', 'Unknown')
            next_timestamp = next_alarm.get('nextTimestamp', '')
            if next_timestamp:
                try:
                    next_dt = target_user.device.convert_string_to_datetime(next_timestamp)
                    next_local = next_dt.strftime('%Y-%m-%d %H:%M')
                    print(f"\n⏰ Next alarm: {next_time} at {next_local}")
                except:
                    print(f"\n⏰ Next alarm: {next_time}")
            else:
                print(f"\n⏰ Next alarm: {next_time}")
        else:
            if profile['enable_alarms']:
                print(f"\n⚠️  No next alarm scheduled, but {profile['enable_alarms']} should be enabled")
            else:
                print(f"\n✅ No alarms scheduled (as expected for {profile_name})")
        
        # Show bedtime status
        try:
            bedtime_settings = await target_user.get_bedtime_settings()
            if bedtime_settings and 'nextScheduledTimestamp' in bedtime_settings:
                next_bedtime = bedtime_settings['nextScheduledTimestamp']
                next_dt = target_user.device.convert_string_to_datetime(next_bedtime)
                next_local = next_dt.strftime('%Y-%m-%d %H:%M')
                print(f"🛏️  Next bedtime: {next_local}")
        except Exception as e:
            print(f"ℹ️  Could not get next bedtime info: {e}")
        
        print(f"\n" + "=" * 60)
        print(f"✅ Successfully applied {profile['description']}!")
        print(f"✅ Profile optimized for {profile_name} work schedule")
        return True
        
    except Exception as e:
        print(f"❌ Error applying profile: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await es.stop()
        print("✓ Disconnected from Eight Sleep")

async def main():
    """Main function to parse arguments and set profile."""
    
    if len(sys.argv) != 2:
        print("❌ Usage: python eight_sleep_profile.py [DayShift|NightShift|DaysOff]")
        print("\nAvailable profiles:")
        for name, config in PROFILES.items():
            enable_list = [t[:5] for t in config['enable_alarms']] or ['None']
            disable_list = [t[:5] for t in config['disable_alarms']] or ['None']
            print(f"\n  🔧 {name}: {config['description']}")
            print(f"     🛏️  Bedtime: {config['bedtime'][:5]} ({', '.join(config['bedtime_days'])})")
            print(f"     🌡️  Temps: Bedtime {config['bedtime_temp']}°, Sleep {config['initial_sleep_temp']}°→{config['final_sleep_temp']}°")
            print(f"     ⏰ Enable alarms: {', '.join(enable_list)}")
            print(f"     ⏰ Disable alarms: {', '.join(disable_list)}")
        return
    
    profile_name = sys.argv[1]
    success = await set_profile(profile_name)
    
    if success:
        print(f"\n🎉 Profile '{profile_name}' applied successfully!")
    else:
        print(f"\n💥 Failed to apply profile '{profile_name}'")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())