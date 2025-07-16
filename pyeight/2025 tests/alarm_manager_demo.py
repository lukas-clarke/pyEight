#!/usr/bin/env python3
"""
alarm_manager_demo.py
author: github.com/nroszko

Comprehensive demo of the new Eight Sleep alarm management functions.
Shows how to use all the alarm-related features from external applications.

Usage:
    python alarm_manager_demo.py
"""

import sys
import os
import asyncio
from datetime import datetime

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from peight.eight import EightSleep

# TODO: WARNING: Running this demo will modify your Eight Sleep alarms and bedtime settings with the values from the demo.
# TODO: ------------------------------------------------------------------------
# TODO: Replace with your actual Eight Sleep credentials ---------------------------------------
EMAIL = "Your8SleepEmail@example.com" # Use your actual Eight Sleep account credentials
PASSWORD = "Your8SleepPassword" # Use your actual Eight Sleep account credentials
PROFILE = "YourName"  # The profile name for your Eight Sleep account.
TIMEZONE = "America/Edmonton"  # Adjust to your timezone
# TODO: Replace with your actual Eight Sleep credentials -------------------
# TODO: ------------------------------------------------------------------------
CLIENT_ID = None
CLIENT_SECRET = None

async def demo_alarm_management():
    """Comprehensive demo of alarm management features."""
    
    print("🔧 Eight Sleep Alarm Management Demo")
    print("=" * 50)
    
    # Connect to Eight Sleep
    es = EightSleep(EMAIL, PASSWORD, TIMEZONE, CLIENT_ID, CLIENT_SECRET)
    
    try:
        print("Connecting to Eight Sleep...")
        success = await es.start()
        
        if not success:
            print("❌ Failed to authenticate")
            return
        
        print("✅ Connected successfully!")
        await es.update_device_data()
        await es.update_user_data()
        
        # Find user by profile name
        target_user = None
        for user_id, user in es.users.items():
            if user.user_profile.get('firstName', '').lower() == PROFILE.lower():
                target_user = user
                break
        
        if not target_user:
            print(f"❌ {PROFILE} not found")
            return
        
        print(f"✅ Found {PROFILE}'s account (Side: {target_user.side})")
        
        # =================================================================
        # DEMO 1: List all alarms
        # =================================================================
        print("\n" + "="*50)
        print("📋 DEMO 1: Listing All Alarms")
        print("="*50)
        
        all_alarms = target_user.get_all_alarms()
        print(f"Total alarms found: {len(all_alarms)}")
        
        for i, alarm in enumerate(all_alarms, 1):
            status = "🟢 ENABLED" if alarm.get('enabled') else "🔴 DISABLED"
            time_str = alarm.get('time', 'Unknown')
            alarm_id = alarm.get('id', 'Unknown')
            
            print(f"\n  Alarm {i}: {time_str} - {status}")
            print(f"    ID: {alarm_id}")
            print(f"    Vibration: {'✅' if alarm.get('vibration', {}).get('enabled') else '❌'} (Power: {alarm.get('vibration', {}).get('powerLevel', 0)})")
            print(f"    Thermal: {'✅' if alarm.get('thermal', {}).get('enabled') else '❌'} (Level: {alarm.get('thermal', {}).get('level', 0)})")
            print(f"    Smart Wake: {'✅' if alarm.get('smart', {}).get('lightSleepEnabled') else '❌'}")
            
            # Show weekdays
            weekdays = alarm.get('repeat', {}).get('weekDays', {})
            active_days = [day.title() for day, enabled in weekdays.items() if enabled]
            print(f"    Days: {', '.join(active_days) if active_days else 'None'}")
        
        # =================================================================
        # DEMO 2: Get specific alarms
        # =================================================================
        print("\n" + "="*50)
        print("🔍 DEMO 2: Finding Specific Alarms")
        print("="*50)
        
        # Get enabled alarms
        enabled_alarms = target_user.get_enabled_alarms()
        print(f"Enabled alarms: {len(enabled_alarms)}")
        for alarm in enabled_alarms:
            print(f"  - {alarm.get('time')} (ID: {alarm.get('id', '')[:8]}...)")
        
        # Get disabled alarms
        disabled_alarms = target_user.get_disabled_alarms()
        print(f"Disabled alarms: {len(disabled_alarms)}")
        for alarm in disabled_alarms:
            print(f"  - {alarm.get('time')} (ID: {alarm.get('id', '')[:8]}...)")
        
        # Get next scheduled alarm
        next_alarm = target_user.get_next_scheduled_alarm()
        if next_alarm:
            print(f"Next scheduled alarm: {next_alarm.get('time')} at {next_alarm.get('nextTimestamp', 'Unknown time')}")
        else:
            print("No next alarm scheduled")
        
        # Find alarm by time
        morning_alarm = target_user.get_alarm_by_time("04:30")
        if morning_alarm:
            print(f"Found 04:30 alarm: {'Enabled' if morning_alarm.get('enabled') else 'Disabled'}")
        
        # =================================================================
        # DEMO 3: Basic alarm enable/disable
        # =================================================================
        print("\n" + "="*50)
        print("🔧 DEMO 3: Basic Alarm Control")
        print("="*50)
        
        if all_alarms:
            test_alarm = all_alarms[0]
            alarm_id = test_alarm['id']
            current_status = test_alarm.get('enabled', False)
            
            print(f"Testing with alarm: {test_alarm.get('time')} (currently {'enabled' if current_status else 'disabled'})")
            
            # Toggle the alarm
            new_status = not current_status
            print(f"Setting alarm to: {'enabled' if new_status else 'disabled'}")
            
            if new_status:
                success = await target_user.enable_alarm(alarm_id)
            else:
                success = await target_user.disable_alarm(alarm_id)
            
            if success:
                print(f"✅ Successfully {'enabled' if new_status else 'disabled'} alarm")
                
                # Verify the change
                await target_user.update_alarm_data()
                updated_alarm = target_user.get_alarm_by_id(alarm_id)
                if updated_alarm:
                    verified_status = updated_alarm.get('enabled', False)
                    print(f"✓ Verified: Alarm is now {'enabled' if verified_status else 'disabled'}")
            else:
                print(f"❌ Failed to {'enable' if new_status else 'disable'} alarm")
            
            # Reset to original state
            print(f"Resetting alarm to original state...")
            if current_status:
                await target_user.enable_alarm(alarm_id)
            else:
                await target_user.disable_alarm(alarm_id)
            print("✓ Reset complete")
        
        # =================================================================
        # DEMO 4: Advanced alarm configuration
        # =================================================================
        print("\n" + "="*50)
        print("⚙️  DEMO 4: Advanced Alarm Configuration")
        print("="*50)
        
        if all_alarms:
            test_alarm = all_alarms[0]
            alarm_id = test_alarm['id']
            
            print(f"Configuring alarm: {test_alarm.get('time')}")
            
            # Demo: Set vibration settings
            print("Setting vibration to gentle with 75% power...")
            success = await target_user.set_alarm_vibration(alarm_id, True, 75, "GENTLE")
            if success:
                print("✅ Vibration settings updated")
            
            # Demo: Configure smart features
            print("Enabling smart wake features...")
            success = await target_user.set_alarm_smart_features(
                alarm_id, 
                light_sleep=True, 
                sleep_cap=True, 
                sleep_cap_minutes=420  # 7 hours
            )
            if success:
                print("✅ Smart features configured")
            
            # Demo: Set specific weekdays
            print("Setting alarm for work days only...")
            work_days = {
                "monday": True,
                "tuesday": True,
                "wednesday": True,
                "thursday": True,
                "friday": True,
                "saturday": False,
                "sunday": False
            }
            success = await target_user.set_alarm_weekdays(alarm_id, work_days)
            if success:
                print("✅ Weekday schedule updated")
            
            # Demo: Comprehensive alarm setup
            print("Setting up comprehensive alarm configuration...")
            success = await target_user.set_alarm_direct(
                alarm_id=alarm_id,
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
            if success:
                print("✅ Comprehensive alarm configuration complete")
            
            # Verify changes
            await target_user.update_alarm_data()
            updated_alarm = target_user.get_alarm_by_id(alarm_id)
            if updated_alarm:
                print("\n📋 Updated alarm configuration:")
                print(f"  Time: {updated_alarm.get('time')}")
                print(f"  Enabled: {updated_alarm.get('enabled')}")
                print(f"  Vibration: {updated_alarm.get('vibration', {}).get('enabled')} (Power: {updated_alarm.get('vibration', {}).get('powerLevel')})")
                print(f"  Thermal: {updated_alarm.get('thermal', {}).get('enabled')} (Level: {updated_alarm.get('thermal', {}).get('level')})")
                print(f"  Smart Features: {updated_alarm.get('smart', {})}")
        
        # =================================================================
        # DEMO 5: Bulk operations
        # =================================================================
        print("\n" + "="*50)
        print("📦 DEMO 5: Bulk Operations")
        print("="*50)
        
        print("Current alarm states:")
        for alarm in target_user.get_all_alarms():
            status = "🟢" if alarm.get('enabled') else "🔴"
            print(f"  {status} {alarm.get('time')} - {alarm.get('id', '')[:8]}...")
        
        # Note: Uncomment these for actual testing, but they're commented to avoid 
        # disrupting your actual alarms during demo
        
        # print("\nDisabling all alarms...")
        # results = await target_user.disable_all_alarms()
        # success_count = sum(1 for r in results if r)
        # print(f"✅ Successfully disabled {success_count}/{len(results)} alarms")
        
        # print("\nRe-enabling all alarms...")
        # results = await target_user.enable_all_alarms()
        # success_count = sum(1 for r in results if r)
        # print(f"✅ Successfully enabled {success_count}/{len(results)} alarms")
        
        # =================================================================
        # DEMO 6: Legacy compatibility
        # =================================================================
        print("\n" + "="*50)
        print("🔄 DEMO 6: Legacy Compatibility")
        print("="*50)
        
        if target_user.next_alarm_id:
            print(f"Next alarm ID (legacy): {target_user.next_alarm_id}")
            print(f"Next alarm time (legacy): {target_user.next_alarm}")
            
            # Test legacy method
            is_enabled = target_user.get_alarm_enabled(None)  # None means next alarm
            print(f"Next alarm enabled (legacy method): {is_enabled}")
            
            # Test legacy set method
            print("Testing legacy set_alarm_enabled method...")
            await target_user.set_alarm_enabled(None, None, is_enabled)  # No change
            print("✅ Legacy method works")
        
        print("\n🎉 Demo completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await es.stop()
        print("✓ Disconnected from Eight Sleep")

# =================================================================
# EXTERNAL APPLICATION EXAMPLE FUNCTIONS
# =================================================================

async def simple_alarm_enable_example(alarm_time: str):
    """Simple example for external applications - enable an alarm by time."""
    es = EightSleep(EMAIL, PASSWORD, TIMEZONE, CLIENT_ID, CLIENT_SECRET)
    
    try:
        await es.start()
        await es.update_device_data()
        await es.update_user_data()
        
        # Find target user
        target_user = None
        for user in es.users.values():
            if user.user_profile.get('firstName', '').lower() == PROFILE.lower():
                target_user = user
                break
        
        if target_user:
            success = await target_user.enable_alarm_by_time(alarm_time)
            return success
        return False
    finally:
        await es.stop()

async def create_work_alarm_example(time: str):
    """Example: Create a work-day only alarm with specific settings."""
    es = EightSleep(EMAIL, PASSWORD, TIMEZONE, CLIENT_ID, CLIENT_SECRET)
    
    try:
        await es.start()
        await es.update_device_data()
        await es.update_user_data()
        
        target_user = None
        for user in es.users.values():
            if user.user_profile.get('firstName', '').lower() == PROFILE.lower():
                target_user = user
                break
        
        if target_user:
            # Find alarm by time
            alarm = target_user.get_alarm_by_time(time)
            if alarm:
                success = await target_user.set_alarm_direct(
                    alarm_id=alarm['id'],
                    enabled=True,
                    weekdays={
                        "monday": True, "tuesday": True, "wednesday": True,
                        "thursday": True, "friday": True, "saturday": False, "sunday": False
                    },
                    vibration_enabled=True,
                    vibration_power=50,
                    thermal_enabled=False,
                    smart_light_sleep=True
                )
                return success
        return False
    finally:
        await es.stop()

async def weekend_alarm_disable_example():
    """Example: Disable all alarms on weekends."""
    es = EightSleep(EMAIL, PASSWORD, TIMEZONE, CLIENT_ID, CLIENT_SECRET)
    
    try:
        await es.start()
        await es.update_device_data()
        await es.update_user_data()
        
        target_user = None
        for user in es.users.values():
            if user.user_profile.get('firstName', '').lower() == PROFILE.lower():
                target_user = user
                break
        
        if target_user:
            # Check if it's weekend
            today = datetime.now().strftime('%A').lower()
            if today in ['saturday', 'sunday']:
                results = await target_user.disable_all_alarms()
                return all(results)
        return False
    finally:
        await es.stop()

if __name__ == "__main__":
    # Run the comprehensive demo
    asyncio.run(demo_alarm_management())
    
    # Example of how to call individual functions:
    # asyncio.run(simple_alarm_enable_example("04:30"))
    # asyncio.run(create_work_alarm_example("04:30"))
    # asyncio.run(weekend_alarm_disable_example())