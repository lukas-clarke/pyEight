"""
pyeight.user
~~~~~~~~~~~~~~~~~~~~
Provides user data for Eight Sleep
Copyright (c) 2022-2023 <https://github.com/lukas-clarke/pyEight>
Licensed under the MIT license.

Enhanced with new alarm API support for post-routine era on 2025-07-08 - <https://github.com/nroszko/pyeight>
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import statistics
from typing import TYPE_CHECKING, Any, Optional, Dict, List

from .constants import APP_API_URL, DATE_FORMAT, DATE_TIME_ISO_FORMAT, CLIENT_API_URL, POSSIBLE_SLEEP_STAGES
from .util import heating_level_to_temp

if TYPE_CHECKING:
    from .eight import EightSleep

_LOGGER = logging.getLogger(__name__)


class EightUser:  # pylint: disable=too-many-public-methods
    """Class for handling data of each eight user."""

    def __init__(self, device: "EightSleep", user_id: str, side: str):
        """Initialize user class."""
        self.device = device
        self.user_id = user_id
        self.side = side
        self._user_profile: dict[str, Any] = {}
        self._base_data: dict[str, Any] = {}
        self.trends: list[dict[str, Any]] = []
        self.alarms: list[dict[str, Any]] = []  # Direct alarm data
        self.next_alarm = None
        self.next_alarm_id = None
        self.bed_state_type = None
        self.current_side_temp = None
        self.target_heating_temp = None

    def _get_trend(self, trend_num: int, keys: str | tuple[str, ...]) -> Any:
        """Get trend value for specified key."""
        if len(self.trends) < trend_num + 1:
            return None
        
        data = self.trends[-(trend_num + 1)]
        if isinstance(keys, str):
            return data.get(keys)
        
        # Navigate nested keys
        for key in keys[:-1]:
            data = data.get(key, {})
        return data.get(keys[-1])

    def _get_quality_score(self, trend_num: int, key: str) -> Any:
        """Get quality score for specified key."""
        return self._get_trend(trend_num, ("sleepQualityScore", key, "score"))

    def _get_routine_score(self, trend_num: int, key: str) -> Any:
        """Get routine score for specified key."""
        return self._get_trend(trend_num, ("sleepRoutineScore", key, "score"))

    def _get_sleep_score(self, trend_num: int) -> int | None:
        """Return sleep score for a given trend."""
        return self._get_trend(trend_num, "score")

    def _trend_timeseries(self) -> dict[str, Any] | None:
        """Return the timeseries for the latest trend."""
        if not self.trends:
            return None
        return self.trends[-1].get("sessions", [{}])[-1].get("timeseries", {})

    def _get_current_trend_property_value(self, key: str) -> int | float | None:
        """Get current property from trends."""
        timeseries_data = self._trend_timeseries()
        if not timeseries_data or timeseries_data.get(key) is None:
            return None
        return timeseries_data[key][-1][1]

    def _session_date(self, trend_num: int) -> datetime | None:
        """Get session date for given trend."""
        if len(self.trends) < trend_num + 1:
            return None
        
        session_date = self.trends[-(trend_num + 1)].get("presenceStart")
        if session_date is None:
            return None
        
        return self.device.convert_string_to_datetime(session_date)

    def _sleep_breakdown(self, trend_num: int) -> dict[str, Any] | None:
        """Return durations of sleep stages for given session."""
        if len(self.trends) < (trend_num + 1):
            return None
        
        breakdown = {
            "light": self._get_trend(trend_num, "lightDuration"),
            "deep": self._get_trend(trend_num, "deepDuration"),
            "rem": self._get_trend(trend_num, "remDuration"),
            "awake": self._get_trend(trend_num, "presenceDuration") - self._get_trend(trend_num, "sleepDuration")
        }
        return {k: v for k, v in breakdown.items() if v is not None}

    def _session_processing(self, trend_num: int) -> bool | None:
        """Return processing state of given session."""
        if len(self.trends) < trend_num + 1:
            return None
        return self.trends[-(trend_num + 1)].get("processing", False)

    # =============================================================================
    # ALARM API METHODS
    # =============================================================================

    def get_alarm_by_id(self, alarm_id: str) -> Optional[Dict[str, Any]]:
        """Get alarm data by alarm ID."""
        return next((alarm for alarm in self.alarms if alarm.get('id') == alarm_id), None)

    def get_alarm_by_time(self, time: str) -> Optional[Dict[str, Any]]:
        """Get alarm data by time (HH:MM:SS or HH:MM format)."""
        # Normalize time format
        if len(time) == 5:  # HH:MM
            time += ":00"  # Convert to HH:MM:SS
        
        return next((alarm for alarm in self.alarms if alarm.get('time') == time), None)

    def get_all_alarms(self) -> List[Dict[str, Any]]:
        """Get all alarms for this user."""
        return self.alarms.copy()

    def get_enabled_alarms(self) -> List[Dict[str, Any]]:
        """Get all enabled alarms."""
        return [alarm for alarm in self.alarms if alarm.get('enabled', False)]

    def get_disabled_alarms(self) -> List[Dict[str, Any]]:
        """Get all disabled alarms."""
        return [alarm for alarm in self.alarms if not alarm.get('enabled', False)]

    def get_next_scheduled_alarm(self) -> Optional[Dict[str, Any]]:
        """Get the next scheduled alarm based on current time and enabled status."""
        enabled_alarms = self.get_enabled_alarms()
        if not enabled_alarms:
            return None
        
        # Find alarm with earliest next timestamp
        next_alarm = None
        earliest_time = None
        
        for alarm in enabled_alarms:
            if 'nextTimestamp' in alarm and alarm['nextTimestamp']:
                try:
                    alarm_time = self.device.convert_string_to_datetime(alarm['nextTimestamp'])
                    if earliest_time is None or alarm_time < earliest_time:
                        earliest_time = alarm_time
                        next_alarm = alarm
                except Exception:
                    continue
        
        return next_alarm

    async def _api_call_alarm(self, method: str, alarm_id: str, data: dict = None) -> bool:
        """Centralized API call handler for alarm operations."""
        url = f"https://app-api.8slp.net/v1/users/{self.user_id}/alarms/{alarm_id}"
        
        try:
            response = await self.device.api_request(method, url, data=data, return_json=True)
            
            # Update alarm cache if response contains alarm data
            if response and 'alarms' in response:
                self.alarms = response['alarms']
                _LOGGER.debug(f"Updated alarm cache with {len(self.alarms)} alarms")
            
            return True
        except Exception as e:
            _LOGGER.error(f"Alarm API call failed ({method} {alarm_id}): {e}")
            return False

    async def _ensure_alarm_data(self) -> None:
        """Ensure alarm data is available, try to discover if not."""
        if not self.alarms:
            await self.update_alarm_data()
            
        # If still no alarms, try bootstrap discovery
        if not self.alarms:
            _LOGGER.info("No alarms found, attempting discovery...")
            await self._bootstrap_alarm_discovery()

    async def _bootstrap_alarm_discovery(self) -> bool:
        """Try to discover alarms using various methods."""
        # Try common alarm times with test requests
        common_times = ["04:30:00", "05:00:00", "06:00:00", "06:30:00", "07:00:00", 
                       "16:00:00", "17:00:00", "18:00:00", "22:00:00", "23:00:00"]
        
        for test_time in common_times:
            try:
                # Create minimal test alarm data
                test_data = {
                    "enabled": True,
                    "time": test_time,
                    "repeat": {"enabled": True, "weekDays": {"monday": True}},
                    "vibration": {"enabled": True, "powerLevel": 50, "pattern": "INTENSE"},
                    "thermal": {"enabled": False, "level": 50},
                    "smart": {"lightSleepEnabled": True, "sleepCapEnabled": False, "sleepCapMinutes": 480},
                    "audio": {"enabled": False, "trackId": "futuristic", "level": 30},
                    "snoozing": False
                }
                
                # Try POST to discover existing alarms
                create_url = f"https://app-api.8slp.net/v1/users/{self.user_id}/alarms"
                response = await self.device.api_request("POST", create_url, data=test_data)
                
                if response and 'alarms' in response:
                    self.alarms = response['alarms']
                    _LOGGER.info(f"Bootstrap discovered {len(self.alarms)} alarms")
                    return True
                    
            except Exception as e:
                # Try to extract alarm data from error responses
                error_msg = str(e)
                if 'alarm' in error_msg.lower():
                    try:
                        import json
                        import re
                        json_match = re.search(r'[\{\[].*[\}\]]', error_msg)
                        if json_match:
                            error_data = json.loads(json_match.group())
                            if 'alarms' in error_data:
                                self.alarms = error_data['alarms']
                                _LOGGER.info(f"Discovered {len(self.alarms)} alarms from error response")
                                return True
                    except:
                        pass
                continue
        
        return False

    async def set_alarm_direct(
        self,
        alarm_id: str,
        enabled: bool,
        time: str = None,
        weekdays: Dict[str, bool] = None,
        vibration_enabled: bool = True,
        vibration_power: int = 50,
        vibration_pattern: str = "INTENSE",
        thermal_enabled: bool = False,
        thermal_level: int = 50,
        audio_enabled: bool = False,
        audio_level: int = 30,
        audio_track: str = "futuristic",
        smart_light_sleep: bool = True,
        smart_sleep_cap: bool = False,
        smart_sleep_cap_minutes: int = 480
    ) -> bool:
        """Set alarm using the new direct API with comprehensive configuration."""
        await self._ensure_alarm_data()
        
        # Get existing alarm data to preserve current settings
        existing_alarm = self.get_alarm_by_id(alarm_id)
        if not existing_alarm:
            raise ValueError(f"Alarm with ID {alarm_id} not found")

        # Build comprehensive alarm configuration
        alarm_data = {
            "id": alarm_id,
            "enabled": enabled,
            "time": time or existing_alarm.get('time', '06:00:00'),
            "repeat": {
                "enabled": True,
                "weekDays": weekdays or existing_alarm.get('repeat', {}).get('weekDays', {
                    "monday": True, "tuesday": True, "wednesday": True,
                    "thursday": True, "friday": True, "saturday": True, "sunday": True
                })
            },
            "vibration": {
                "enabled": vibration_enabled,
                "powerLevel": vibration_power,
                "pattern": vibration_pattern
            },
            "thermal": {
                "enabled": thermal_enabled,
                "level": thermal_level
            },
            "smart": {
                "lightSleepEnabled": smart_light_sleep,
                "sleepCapEnabled": smart_sleep_cap,
                "sleepCapMinutes": smart_sleep_cap_minutes
            },
            "audio": {
                "enabled": audio_enabled,
                "trackId": audio_track,
                "level": audio_level
            },
            "snoozing": False
        }

        # Add timestamps when disabling (observed behavior from app)
        if not enabled:
            now = datetime.utcnow()
            start_time = now + timedelta(minutes=1)
            end_time = start_time + timedelta(minutes=20)
            
            alarm_data["startTimestamp"] = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            alarm_data["endTimestamp"] = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        return await self._api_call_alarm("PUT", alarm_id, alarm_data)

    async def enable_alarm(self, alarm_id: str) -> bool:
        """Enable an alarm by ID."""
        await self._ensure_alarm_data()
        
        existing_alarm = self.get_alarm_by_id(alarm_id)
        if not existing_alarm:
            raise ValueError(f"Alarm with ID {alarm_id} not found")
        
        # Preserve all existing settings, just change enabled status
        return await self.set_alarm_direct(alarm_id, enabled=True)

    async def disable_alarm(self, alarm_id: str) -> bool:
        """Disable an alarm by ID."""
        await self._ensure_alarm_data()
        
        existing_alarm = self.get_alarm_by_id(alarm_id)
        if not existing_alarm:
            raise ValueError(f"Alarm with ID {alarm_id} not found")
        
        # Preserve all existing settings, just change enabled status
        return await self.set_alarm_direct(alarm_id, enabled=False)

    async def enable_alarm_by_time(self, time: str) -> bool:
        """Enable an alarm by time (HH:MM or HH:MM:SS)."""
        await self._ensure_alarm_data()
        
        alarm = self.get_alarm_by_time(time)
        if not alarm:
            raise ValueError(f"No alarm found for time {time}")
        
        return await self.enable_alarm(alarm['id'])

    async def disable_alarm_by_time(self, time: str) -> bool:
        """Disable an alarm by time (HH:MM or HH:MM:SS)."""
        await self._ensure_alarm_data()
        
        alarm = self.get_alarm_by_time(time)
        if not alarm:
            raise ValueError(f"No alarm found for time {time}")
        
        return await self.disable_alarm(alarm['id'])

    async def set_alarm_time(self, alarm_id: str, new_time: str) -> bool:
        """Change the time of an existing alarm."""
        # Normalize time format
        if len(new_time) == 5:  # HH:MM
            new_time += ":00"  # Convert to HH:MM:SS
        
        existing_alarm = self.get_alarm_by_id(alarm_id)
        if not existing_alarm:
            raise ValueError(f"Alarm with ID {alarm_id} not found")
        
        return await self.set_alarm_direct(alarm_id, existing_alarm['enabled'], time=new_time)

    async def set_alarm_weekdays(self, alarm_id: str, weekdays: Dict[str, bool]) -> bool:
        """Set which days of the week an alarm should repeat."""
        existing_alarm = self.get_alarm_by_id(alarm_id)
        if not existing_alarm:
            raise ValueError(f"Alarm with ID {alarm_id} not found")
        
        return await self.set_alarm_direct(alarm_id, existing_alarm['enabled'], weekdays=weekdays)

    async def set_alarm_vibration(self, alarm_id: str, enabled: bool, power: int = 50, pattern: str = "INTENSE") -> bool:
        """Configure alarm vibration settings."""
        existing_alarm = self.get_alarm_by_id(alarm_id)
        if not existing_alarm:
            raise ValueError(f"Alarm with ID {alarm_id} not found")
        
        return await self.set_alarm_direct(
            alarm_id, 
            existing_alarm['enabled'],
            vibration_enabled=enabled,
            vibration_power=power,
            vibration_pattern=pattern
        )

    async def set_alarm_thermal(self, alarm_id: str, enabled: bool, level: int = 50) -> bool:
        """Configure alarm thermal wake settings."""
        existing_alarm = self.get_alarm_by_id(alarm_id)
        if not existing_alarm:
            raise ValueError(f"Alarm with ID {alarm_id} not found")
        
        return await self.set_alarm_direct(
            alarm_id,
            existing_alarm['enabled'],
            thermal_enabled=enabled,
            thermal_level=level
        )

    async def set_alarm_smart_features(
        self, 
        alarm_id: str, 
        light_sleep: bool = True, 
        sleep_cap: bool = False, 
        sleep_cap_minutes: int = 480
    ) -> bool:
        """Configure alarm smart wake features."""
        existing_alarm = self.get_alarm_by_id(alarm_id)
        if not existing_alarm:
            raise ValueError(f"Alarm with ID {alarm_id} not found")
        
        return await self.set_alarm_direct(
            alarm_id,
            existing_alarm['enabled'],
            smart_light_sleep=light_sleep,
            smart_sleep_cap=sleep_cap,
            smart_sleep_cap_minutes=sleep_cap_minutes
        )

    async def enable_all_alarms(self) -> List[bool]:
        """Enable all alarms. Returns list of success/failure for each alarm."""
        await self._ensure_alarm_data()
        
        results = []
        for alarm in self.alarms:
            result = await self.enable_alarm(alarm['id'])
            results.append(result)
        return results

    async def disable_all_alarms(self) -> List[bool]:
        """Disable all alarms. Returns list of success/failure for each alarm."""
        await self._ensure_alarm_data()
        
        results = []
        for alarm in self.alarms:
            result = await self.disable_alarm(alarm['id'])
            results.append(result)
        return results

    async def update_alarm_data(self) -> None:
        """Update alarm data by trying multiple methods to find alarm information."""
        self.alarms = []
        
        # Try direct alarm endpoints first
        endpoints_to_try = [
            f"https://app-api.8slp.net/v1/users/{self.user_id}/alarms",
            f"https://client-api.8slp.net/v1/users/{self.user_id}/alarms", 
            f"https://app-api.8slp.net/v1/users/{self.user_id}/routines",
            f"https://client-api.8slp.net/v1/users/{self.user_id}/routines"
        ]
        
        for endpoint in endpoints_to_try:
            try:
                response = await self.device.api_request("GET", endpoint)
                
                if self._extract_alarms_from_response(response):
                    _LOGGER.info(f"Found {len(self.alarms)} alarms from {endpoint}")
                    break
                    
            except Exception as e:
                _LOGGER.debug(f"Failed to get alarms from {endpoint}: {e}")
                continue
        
        # Fallback: try device endpoint
        if not self.alarms:
            try:
                await self.device.update_device_data()
                device_data = self.device.device_data
                side_key = f"{self.corrected_side_for_key}Kelvin"
                
                if side_key in device_data:
                    kelvin_data = device_data[side_key]
                    self.alarms = kelvin_data.get('alarms', [])
                    if self.alarms:
                        _LOGGER.info(f"Found {len(self.alarms)} alarms from device data")
            except Exception as e:
                _LOGGER.debug(f"Failed to get alarms from device data: {e}")
        
        # Update next alarm info
        self._update_next_alarm_info()
        _LOGGER.info(f"Total alarms loaded: {len(self.alarms)}")

    def _extract_alarms_from_response(self, response: Any) -> bool:
        """Extract alarm data from API response. Returns True if alarms found."""
        if not response:
            return False
        
        if isinstance(response, dict):
            # Direct alarms array
            if 'alarms' in response and isinstance(response['alarms'], list):
                self.alarms = response['alarms']
                return True
            
            # Routines with alarms (legacy format)
            if 'routines' in response:
                for routine in response['routines']:
                    if 'alarms' in routine:
                        self._convert_routine_alarms(routine['alarms'])
                        return len(self.alarms) > 0
        
        elif isinstance(response, list) and response:
            # Check if items look like alarms
            if all('time' in item and 'id' in item for item in response if isinstance(item, dict)):
                self.alarms = response
                return True
        
        return False

    def _convert_routine_alarms(self, routine_alarms: List[Dict]) -> None:
        """Convert routine-based alarms to new format."""
        for alarm in routine_alarms:
            alarm_time = alarm.get('timeWithOffset', {}).get('time', 'Unknown')
            alarm_id = alarm.get('alarmId', '')
            enabled = not alarm.get('disabledIndividually', False)
            
            converted_alarm = {
                'id': alarm_id,
                'time': alarm_time,
                'enabled': enabled,
                'repeat': {'enabled': True, 'weekDays': {}},
                'vibration': {'enabled': True, 'powerLevel': 50, 'pattern': 'INTENSE'},
                'thermal': {'enabled': False, 'level': 50},
                'smart': {'lightSleepEnabled': True, 'sleepCapEnabled': False},
                'audio': {'enabled': False, 'level': 30, 'trackId': 'futuristic'},
                'snoozing': False
            }
            self.alarms.append(converted_alarm)

    def _update_next_alarm_info(self) -> None:
        """Update next alarm tracking variables."""
        next_alarm = self.get_next_scheduled_alarm()
        if next_alarm:
            self.next_alarm_id = next_alarm['id']
            if 'nextTimestamp' in next_alarm:
                try:
                    self.next_alarm = self.device.convert_string_to_datetime(next_alarm['nextTimestamp'])
                except Exception:
                    self.next_alarm = None
        else:
            self.next_alarm_id = None
            self.next_alarm = None

    # =============================================================================
    # BEDTIME SCHEDULING API METHODS
    # =============================================================================

    async def set_bedtime_schedule(
        self,
        bedtime: str,
        bedtime_temp: int = -10,
        initial_sleep_temp: int = -8,
        final_sleep_temp: int = -8,
        days: List[str] = None,
        schedule_type: str = "smart"
    ) -> bool:
        """Set bedtime schedule and temperature profile."""
        if days is None:
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        # Normalize time format
        if len(bedtime) == 5:  # HH:MM
            bedtime += ":00"  # Convert to HH:MM:SS
        
        # Get existing schedule ID to preserve it
        existing_schedule_id = await self._get_existing_schedule_id()
        
        bedtime_data = {
            "scheduleType": schedule_type,
            "smart": {
                "bedTimeLevel": bedtime_temp,
                "initialSleepLevel": initial_sleep_temp,
                "finalSleepLevel": final_sleep_temp
            },
            "schedules": [
                {
                    "id": existing_schedule_id,
                    "enabled": True,
                    "time": bedtime,
                    "days": days,
                    "startSettings": {
                        "elevationPreset": "NONE",
                        "bedtime": 1
                    }
                }
            ]
        }
        
        url = f"https://app-api.8slp.net/v1/users/{self.user_id}/bedtime"
        
        try:
            await self.device.api_request("PUT", url, data=bedtime_data, return_json=False)
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to set bedtime schedule: {e}")
            return False

    async def get_bedtime_settings(self) -> Optional[Dict[str, Any]]:
        """Get current bedtime settings."""
        url = f"https://app-api.8slp.net/v1/users/{self.user_id}/temperature"
        
        try:
            response = await self.device.api_request("GET", url)
            return response
        except Exception as e:
            _LOGGER.error(f"Failed to get bedtime settings: {e}")
            return None

    async def _get_existing_schedule_id(self) -> str:
        """Get existing schedule ID or generate a new one."""
        try:
            existing_settings = await self.get_bedtime_settings()
            if existing_settings and 'settings' in existing_settings:
                schedules = existing_settings['settings'].get('schedules', [])
                if schedules:
                    return schedules[0].get('id')
        except Exception:
            pass
        
        # Generate new ID if none exists
        import uuid
        return str(uuid.uuid4())

    async def set_bedtime_temp_levels(
        self,
        bedtime_temp: int = None,
        initial_sleep_temp: int = None,
        final_sleep_temp: int = None
    ) -> bool:
        """Update just the temperature levels without changing schedule time/days."""
        existing_settings = await self.get_bedtime_settings()
        if not existing_settings or 'settings' not in existing_settings:
            raise ValueError("No existing bedtime settings found. Use set_bedtime_schedule() first.")
        
        settings = existing_settings['settings']
        smart_settings = settings.get('smart', {})
        
        # Update only provided temperature levels
        if bedtime_temp is not None:
            smart_settings['bedTimeLevel'] = bedtime_temp
        if initial_sleep_temp is not None:
            smart_settings['initialSleepLevel'] = initial_sleep_temp
        if final_sleep_temp is not None:
            smart_settings['finalSleepLevel'] = final_sleep_temp
        
        # Keep existing schedule configuration
        bedtime_data = {
            "scheduleType": settings.get('scheduleType', 'smart'),
            "smart": smart_settings,
            "schedules": settings.get('schedules', [])
        }
        
        url = f"https://app-api.8slp.net/v1/users/{self.user_id}/bedtime"
        
        try:
            await self.device.api_request("PUT", url, data=bedtime_data, return_json=False)
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to update bedtime temperatures: {e}")
            return False

    async def set_bedtime_time(self, bedtime: str, days: List[str] = None) -> bool:
        """Update bedtime schedule time and days without changing temperature levels."""
        existing_settings = await self.get_bedtime_settings()
        if not existing_settings or 'settings' not in existing_settings:
            raise ValueError("No existing bedtime settings found. Use set_bedtime_schedule() first.")
        
        settings = existing_settings['settings']
        
        # Normalize time format
        if len(bedtime) == 5:  # HH:MM
            bedtime += ":00"  # Convert to HH:MM:SS
        
        if days is None:
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        # Update schedule
        schedules = settings.get('schedules', [])
        if schedules:
            schedules[0]['time'] = bedtime
            schedules[0]['days'] = days
        else:
            import uuid
            schedules = [{
                "id": str(uuid.uuid4()),
                "enabled": True,
                "time": bedtime,
                "days": days,
                "startSettings": {
                    "elevationPreset": "NONE",
                    "bedtime": 1
                }
            }]
        
        bedtime_data = {
            "scheduleType": settings.get('scheduleType', 'smart'),
            "smart": settings.get('smart', {}),
            "schedules": schedules
        }
        
        url = f"https://app-api.8slp.net/v1/users/{self.user_id}/bedtime"
        
        try:
            await self.device.api_request("PUT", url, data=bedtime_data, return_json=False)
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to update bedtime schedule: {e}")
            return False

    # =============================================================================
    # LEGACY COMPATIBILITY METHODS
    # =============================================================================

    def get_alarm_enabled(self, alarm_id: str | None) -> bool:
        """Get alarm enabled status. If no ID specified, checks next alarm."""
        if alarm_id is None:
            alarm_id = self.next_alarm_id
            
        if not alarm_id:
            return False
        
        alarm = self.get_alarm_by_id(alarm_id)
        return alarm.get('enabled', False) if alarm else False

    async def set_alarm_enabled(self, routine_id: str | None, alarm_id: str | None, enabled: bool) -> None:
        """Legacy method updated to use new API. routine_id is ignored."""
        if alarm_id is None:
            alarm_id = self.next_alarm_id
            
        if not alarm_id:
            return
        
        await self.set_alarm_direct(alarm_id, enabled)

    # =============================================================================
    # ORIGINAL METHODS (keeping existing functionality)
    # =============================================================================

    @property
    def user_profile(self) -> dict[str, Any] | None:
        """Return userdata."""
        return self._user_profile

    @property
    def base_data(self) -> dict[str, Any]:
        """Return the base data."""
        return self._base_data

    @property
    def base_data_for_side(self) -> dict[str, Any]:
        """Return the base data for the user's side."""
        return self.base_data.get(self.corrected_side_for_key, {})

    @property
    def base_preset(self) -> str | None:
        """Return the base preset."""
        return self.base_data_for_side.get("preset", {}).get("name")

    @property
    def leg_angle(self) -> int:
        """Return the base leg angle."""
        return self.base_data_for_side.get("leg", {}).get("currentAngle", 0)

    @property
    def torso_angle(self) -> int:
        """Return the base torso angle."""
        return self.base_data_for_side.get("torso", {}).get("currentAngle", 0)

    @property
    def in_snore_mitigation(self) -> bool:
        """Return the snore mitigation state."""
        return self.base_data_for_side.get("inSnoreMitigation", False)

    @property
    def bed_presence(self) -> bool:
        """Return true/false for bed presence based on recent heart rate data."""
        timeseries = self._trend_timeseries()
        if not timeseries or "heartRate" not in timeseries:
            return False

        heart_rate_entry = timeseries["heartRate"][-1]
        _LOGGER.debug(f"Last heart rate: {heart_rate_entry} for {self.user_id}")
        heart_rate_time = datetime.fromisoformat(heart_rate_entry[0].replace('Z', '+00:00'))

        time_difference = datetime.now(timezone.utc) - heart_rate_time

        # Consider the person present if the last heart rate reading was within the last 10 minutes
        return time_difference.total_seconds() < 600

    @property
    def target_heating_level(self) -> int | None:
        """Return target heating/cooling level."""
        return self.device.device_data.get(f"{self.corrected_side_for_key}TargetHeatingLevel")

    @property
    def heating_level(self) -> int | None:
        """Return heating/cooling level."""
        key = f"{self.corrected_side_for_key}HeatingLevel"
        level = self.device.device_data.get(key)

        if level is not None:
            return level

        for data in self.device.device_data_history:
            level = data.get(key)
            if level is not None:
                return level

        return None

    @property
    def corrected_side_for_key(self) -> str:
        """Return corrected side key for API calls."""
        return "left" if self.side.lower() == "solo" else self.side

    def past_heating_level(self, num) -> int:
        """Return a heating level from the past."""
        if num > 9 or len(self.device.device_data_history) < num + 1:
            return 0

        return self.device.device_data_history[num].get(
            f"{self.corrected_side_for_key}HeatingLevel", 0
        )

    def _now_heating_or_cooling(self, target_heating_level_check: bool) -> bool | None:
        """Return true/false if heating or cooling is currently happening."""
        key = f"{self.corrected_side_for_key}NowHeating"
        target = self.device.device_data.get(key)
        
        if self.target_heating_level is None or target is None:
            return None
            
        return target and target_heating_level_check

    @property
    def now_heating(self) -> bool | None:
        """Return current heating state."""
        level = self.target_heating_level
        return self._now_heating_or_cooling(level is not None and level > 0)

    @property
    def now_cooling(self) -> bool | None:
        """Return current cooling state."""
        level = self.target_heating_level
        return self._now_heating_or_cooling(level is not None and level < 0)

    @property
    def heating_remaining(self) -> int | None:
        """Return seconds of heat/cool time remaining."""
        return self.device.device_data.get(f"{self.corrected_side_for_key}HeatingDuration")

    @property
    def last_seen(self) -> str | None:
        """Return mattress last seen time."""
        last_seen = self.device.device_data.get(f"{self.corrected_side_for_key}PresenceEnd")
        if not last_seen:
            return None
        return datetime.fromtimestamp(int(last_seen)).strftime(DATE_TIME_ISO_FORMAT)

    @property
    def heating_values(self) -> dict[str, Any]:
        """Return a dict of all the current heating values."""
        return {
            "level": self.heating_level,
            "target": self.target_heating_level,
            "active": self.now_heating,
            "remaining": self.heating_remaining,
            "last_seen": self.last_seen,
        }

    @property
    def current_session_date(self) -> datetime | None:
        """Return date/time for start of last session data."""
        return self._session_date(0)

    @property
    def current_session_processing(self) -> bool | None:
        """Return processing state of current session."""
        return self._session_processing(0)

    @property
    def current_sleep_stage(self) -> str | None:
        """Return sleep stage for in-progress session."""
        if not self.trends:
            return None

        current_trend = self.trends[-1]
        sessions = current_trend.get('sessions', [])

        if not sessions:
            return None

        current_session = sessions[-1]
        stages = current_session.get('stages', [])

        if not stages:
            return None

        # API always has an awake state last, so pull second to last while processing
        if self.current_session_processing:
            return stages[-2].get('stage') if len(stages) >= 2 else None
        return stages[-1].get('stage')

    @property
    def current_sleep_score(self) -> int | None:
        """Return sleep score for in-progress session."""
        return self._get_sleep_score(0)

    @property
    def current_sleep_fitness_score(self) -> int | None:
        """Return sleep fitness score for latest session."""
        return self._get_trend(0, "score")

    @property
    def current_sleep_quality_score(self) -> int | None:
        """Return sleep quality score for latest session."""
        return self._get_trend(0, ("sleepQualityScore", "total"))

    @property
    def current_sleep_routine_score(self) -> int | None:
        """Return sleep routine score for latest session."""
        return self._get_trend(0, ("sleepRoutineScore", "total"))

    @property
    def current_sleep_duration_score(self) -> int | None:
        """Return sleep duration score for latest session."""
        return self._get_quality_score(0, "sleepDurationSeconds")

    @property
    def current_latency_asleep_score(self) -> int | None:
        """Return latency asleep score for latest session."""
        return self._get_routine_score(0, "latencyAsleepSeconds")

    @property
    def time_slept(self) -> int | None:
        """Return time slept for current session."""
        return self._get_trend(0, "sleepDuration")

    @property
    def presence_start(self):
        """Return presence start time."""
        timestamp = self._get_trend(0, "presenceStart")
        if timestamp:
            return self.device.convert_string_to_datetime(timestamp)
        return None

    @property
    def presence_end(self):
        """Return presence end time."""
        timestamp = self._get_trend(0, "presenceEnd")
        if timestamp:
            return self.device.convert_string_to_datetime(timestamp)
        return None

    @property
    def current_latency_out_score(self) -> int | None:
        """Return latency out score for latest session."""
        return self._get_routine_score(0, "latencyOutSeconds")

    @property
    def current_hrv(self) -> float | None:
        """Return current HRV for latest session."""
        return self._get_trend(0, ("sleepQualityScore", "hrv", "current"))

    @property
    def current_breath_rate(self) -> float | None:
        """Return current breath rate for latest session."""
        return self._get_trend(0, ("sleepQualityScore", "respiratoryRate", "current"))

    @property
    def current_wakeup_consistency_score(self) -> int | None:
        """Return wakeup consistency score for latest session."""
        return self._get_routine_score(0, "wakeupConsistency")

    @property
    def current_fitness_session_date(self) -> str | None:
        """Return date/time for start of last session data."""
        return self._get_trend(0, "day")

    @property
    def current_sleep_breakdown(self) -> dict[str, Any] | None:
        """Return durations of sleep stages for in-progress session."""
        return self._sleep_breakdown(0)

    @property
    def current_bed_temp(self) -> int | float | None:
        """Return current bed temperature for in-progress session."""
        return self.current_side_temp

    @property
    def current_room_temp(self) -> int | float | None:
        """Return current room temperature for in-progress session."""
        timeseries = self._trend_timeseries()
        if timeseries and "tempRoomC" in timeseries:
            return timeseries["tempRoomC"][-1][1]
        return None

    @property
    def current_tnt(self) -> int | None:
        """Return current toss & turns for in-progress session."""
        return self._get_trend(0, "tnt")

    @property
    def current_resp_rate(self) -> int | float | None:
        """Return current respiratory rate for in-progress session."""
        return self._get_trend(0, ("sleepQualityScore", "respiratoryRate", "current"))

    @property
    def current_heart_rate(self) -> int | float | None:
        """Return current heart rate for in-progress session."""
        timeseries = self._trend_timeseries()
        if timeseries and "heartRate" in timeseries:
            return timeseries["heartRate"][-1][1]
        return None

    @property
    def current_values(self) -> dict[str, Any]:
        """Return a dict of all the 'current' parameters."""
        return {
            "date": self.current_session_date,
            "score": self.current_sleep_score,
            "stage": self.current_sleep_stage,
            "breakdown": self.current_sleep_breakdown,
            "tnt": self.current_tnt,
            "bed_temp": self.current_bed_temp,
            "room_temp": self.current_room_temp,
            "resp_rate": self.current_resp_rate,
            "heart_rate": self.current_heart_rate,
            "processing": self.current_session_processing,
        }

    @property
    def current_fitness_values(self) -> dict[str, Any]:
        """Return a dict of all the 'current' fitness score parameters."""
        return {
            "date": self.current_fitness_session_date,
            "score": self.current_sleep_fitness_score,
            "duration": self.current_sleep_duration_score,
            "asleep": self.current_latency_asleep_score,
            "out": self.current_latency_out_score,
            "wakeup": self.current_wakeup_consistency_score,
        }

    @property
    def last_session_date(self) -> datetime | None:
        """Return date/time for start of last session data."""
        return self._session_date(1)

    @property
    def last_session_processing(self) -> bool | None:
        """Return processing state of current session."""
        return self._session_processing(1)

    @property
    def last_sleep_score(self) -> int | None:
        """Return sleep score from last complete sleep session."""
        return self._get_sleep_score(1)

    @property
    def last_sleep_fitness_score(self) -> int | None:
        """Return sleep fitness score for previous sleep session."""
        return self._get_trend(1, ("sleepFitnessScore", "total"))

    @property
    def last_sleep_duration_score(self) -> int | None:
        """Return sleep duration score for previous session."""
        return self._get_quality_score(1, "sleepDurationSeconds")

    @property
    def last_latency_asleep_score(self) -> int | None:
        """Return latency asleep score for previous session."""
        return self._get_routine_score(1, "latencyAsleepSeconds")

    @property
    def last_latency_out_score(self) -> int | None:
        """Return latency out score for previous session."""
        return self._get_routine_score(1, "latencyOutSeconds")

    @property
    def last_wakeup_consistency_score(self) -> int | None:
        """Return wakeup consistency score for previous session."""
        return self._get_routine_score(1, "wakeupConsistency")

    @property
    def last_fitness_session_date(self) -> str | None:
        """Return date/time for start of previous session data."""
        return self._get_trend(1, "day")

    @property
    def last_sleep_breakdown(self) -> dict[str, Any] | None:
        """Return durations of sleep stages for last complete session."""
        return self._sleep_breakdown(1)

    @property
    def last_bed_temp(self) -> int | float | None:
        """Return avg bed temperature for last session."""
        return self._get_trend(1, ("sleepQualityScore", "tempBedC", "average"))

    @property
    def last_room_temp(self) -> int | float | None:
        """Return avg room temperature for last session."""
        return self._get_trend(1, ("sleepQualityScore", "tempRoomC", "average"))

    @property
    def last_tnt(self) -> int | None:
        """Return toss & turns for last session."""
        return self._get_trend(1, "tnt")

    @property
    def last_resp_rate(self) -> int | float | None:
        """Return avg respiratory rate for last session."""
        return self._get_trend(1, ("sleepQualityScore", "respiratoryRate", "average"))

    @property
    def last_heart_rate(self) -> int | float | None:
        """Return avg heart rate for last session."""
        return self._get_trend(1, ("sleepQualityScore", "heartRate", "average"))

    @property
    def last_values(self) -> dict[str, Any]:
        """Return a dict of all the 'last' parameters."""
        return {
            "date": self.last_session_date,
            "score": self.last_sleep_score,
            "breakdown": self.last_sleep_breakdown,
            "tnt": self.last_tnt,
            "bed_temp": self.last_bed_temp,
            "room_temp": self.last_room_temp,
            "resp_rate": self.last_resp_rate,
            "heart_rate": self.last_heart_rate,
            "processing": self.last_session_processing,
        }

    @property
    def last_fitness_values(self) -> dict[str, Any]:
        """Return a dict of all the 'last' fitness score parameters."""
        return {
            "date": self.last_fitness_session_date,
            "score": self.last_sleep_fitness_score,
            "duration": self.last_sleep_duration_score,
            "asleep": self.last_latency_asleep_score,
            "out": self.last_latency_out_score,
            "wakeup": self.last_wakeup_consistency_score,
        }

    def trend_sleep_score(self, date: str) -> int | None:
        """Return trend sleep score for specified date."""
        return next(
            (day.get("score") for day in self.trends if day.get("day") == date),
            None,
        )

    def sleep_fitness_score(self, date: str) -> int | None:
        """Return sleep fitness score for specified date."""
        return next(
            (
                day.get("sleepFitnessScore", {}).get("total")
                for day in self.trends
                if day.get("day") == date
            ),
            None,
        )

    async def get_user_side(self) -> str:
        """Returns the side that the current user is set to"""
        url = CLIENT_API_URL + f"/users/{self.user_id}/current-device"
        data = await self.device.api_request("GET", url, return_json=True)
        return data["side"]

    def heating_stats(self) -> None:
        """Calculate some heating data stats."""
        local_5 = []
        local_10 = []

        for i in range(0, 10):
            level = self.past_heating_level(i)
            if level is None:
                continue
            if level == 0:
                _LOGGER.debug("Cant calculate stats yet...")
                return
            if i < 5:
                local_5.append(level)
            local_10.append(level)

        _LOGGER.debug("%s Heating History: %s", self.side, local_10)

        try:
            # Average of 5min on the history dict.
            fiveminavg = statistics.mean(local_5)
            tenminavg = statistics.mean(local_10)
            _LOGGER.debug("%s Heating 5 min avg: %s", self.side, fiveminavg)
            _LOGGER.debug("%s Heating 10 min avg: %s", self.side, tenminavg)

            # Standard deviation
            fivestdev = statistics.stdev(local_5)
            tenstdev = statistics.stdev(local_10)
            _LOGGER.debug("%s Heating 5 min stdev: %s", self.side, fivestdev)
            _LOGGER.debug("%s Heating 10 min stdev: %s", self.side, tenstdev)

            # Variance
            fivevar = statistics.variance(local_5)
            tenvar = statistics.variance(local_10)
            _LOGGER.debug("%s Heating 5 min variance: %s", self.side, fivevar)
            _LOGGER.debug("%s Heating 10 min variance: %s", self.side, tenvar)
        except statistics.StatisticsError:
            _LOGGER.debug("Cant calculate stats yet...")

    async def update_user(self) -> None:
        """Update all user data."""
        self.side = await self.get_user_side()

        now = datetime.today()
        start = now - timedelta(days=1)
        end = now + timedelta(days=1)

        await self.update_trend_data(
            start.strftime(DATE_FORMAT), end.strftime(DATE_FORMAT)
        )
        await self.update_alarm_data()

        self.bed_state_type = await self.get_bed_state_type()

        current_side_temp_raw = await self.get_current_device_level()
        self.current_side_temp = heating_level_to_temp(current_side_temp_raw, "c")

        if self.target_heating_level is None:
            self.target_heating_temp = None
        else:
            self.target_heating_temp = heating_level_to_temp(
                self.target_heating_level, "c"
            )

    async def set_bed_side(self, side) -> None:
        """Set the bed side for this user."""
        side = str(side).lower()
        if side not in ["solo", "left", "right"]:
            raise Exception(f"Invalid side parameter passed in: {side}")
        url = CLIENT_API_URL + f"/users/{self.user_id}/current-device"
        data = {"id": str(self.device.device_id), "side": side}
        await self.device.api_request("PUT", url, data=data, return_json=False)

    async def get_bed_state_type(self) -> str:
        """Gets the bed state."""
        url = APP_API_URL + f"v1/users/{self.user_id}/temperature"
        data = await self.device.api_request("GET", url)
        return data["currentState"]["type"]

    async def set_heating_level(self, level: int, duration: int = 0) -> None:
        """Update heating data json."""
        url = APP_API_URL + f"v1/users/{self.user_id}/temperature"
        data_for_duration = {"timeBased": {"level": level, "durationSeconds": duration}}
        data_for_level = {"currentLevel": level}
        
        # Clamp level to valid range
        level = max(-100, min(100, level))

        await self.turn_on_side()  # Turn on side before setting temperature
        await self.device.api_request("PUT", url, data=data_for_level)
        await self.device.api_request("PUT", url, data=data_for_duration)

    async def set_smart_heating_level(self, level: int, sleep_stage: str) -> None:
        """Will set the temperature level at a smart sleep stage"""
        if sleep_stage not in POSSIBLE_SLEEP_STAGES:
            raise Exception(
                f"Invalid sleep stage {sleep_stage}. Should be one of {POSSIBLE_SLEEP_STAGES}"
            )
        url = APP_API_URL + f"v1/users/{self.user_id}/temperature"
        data = await self.device.api_request("GET", url)
        sleep_stages_levels = data["smart"]
        
        # Clamp level to valid range
        level = max(-100, min(100, level))
        sleep_stages_levels[sleep_stage] = level
        data = {"smart": sleep_stages_levels}
        await self.device.api_request("PUT", url, data=data)

    async def increment_heating_level(self, offset: int) -> None:
        """Increment heating level with offset"""
        url = APP_API_URL + f"v1/users/{self.user_id}/temperature"
        current_level = await self.get_current_heating_level()
        new_level = current_level + offset
        
        # Clamp level to valid range
        new_level = max(-100, min(100, new_level))

        data_for_level = {"currentLevel": new_level}
        await self.device.api_request("PUT", url, data=data_for_level)

    async def get_current_heating_level(self) -> int:
        """Get current heating level."""
        url = APP_API_URL + f"v1/users/{self.user_id}/temperature"
        resp = await self.device.api_request("GET", url)
        return int(resp["currentLevel"])

    async def get_current_device_level(self) -> int:
        """Get current device level."""
        url = APP_API_URL + f"v1/users/{self.user_id}/temperature"
        resp = await self.device.api_request("GET", url)
        return int(resp.get("currentDeviceLevel", 0))

    async def prime_pod(self):
        """Prime the pod."""
        url = APP_API_URL + f"v1/devices/{self.device.device_id}/priming/tasks"
        data_for_priming = {
            "notifications": {"users": [self.user_id], "meta": "rePriming"}
        }
        await self.device.api_request("POST", url, data=data_for_priming)

    async def turn_on_side(self):
        """Turns on the side of the user"""
        url = APP_API_URL + f"v1/users/{self.user_id}/temperature"
        data = {"currentState": {"type": "smart"}}
        await self.device.api_request("PUT", url, data=data)

    async def turn_off_side(self):
        """Turns off the side of the user"""
        url = APP_API_URL + f"v1/users/{self.user_id}/temperature"
        data = {"currentState": {"type": "off"}}
        await self.device.api_request("PUT", url, data=data)

    async def set_away_mode(self, action: str):
        """Sets the away mode. The action can either be 'start' or 'stop'"""
        url = APP_API_URL + f"v1/users/{self.user_id}/away-mode"
        # Setting time to UTC of 24 hours ago to get API to trigger immediately
        now = str(
            (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.%f")[
                :-3
            ]
            + "Z"
        )
        if action not in ["start", "end"]:
            raise Exception(f"Invalid action: {action}")
        data = {"awayPeriod": {action: now}}
        await self.device.api_request("PUT", url, data=data)

    # Legacy alarm methods (may need updating for new API)
    async def alarm_snooze(self, snooze_minutes: int):
        """Snoozes the user alarm for the specified minutes"""
        if not self.next_alarm_id:
            raise Exception(f"No next alarm ID set for {self.user_id}")
        url = APP_API_URL + f"v1/users/{self.user_id}/routines"
        data = {
            "alarm": {"alarmId": self.next_alarm_id, "snoozeForMinutes": snooze_minutes}
        }
        await self.device.api_request("PUT", url, data=data)

    async def alarm_stop(self):
        """Stops the next user alarm"""
        if not self.next_alarm_id:
            raise Exception(f"No next alarm ID set for {self.user_id}")
        url = APP_API_URL + f"v1/users/{self.user_id}/routines"
        data = {"alarm": {"alarmId": self.next_alarm_id, "stopped": True}}
        await self.device.api_request("PUT", url, data=data)

    async def alarm_dismiss(self):
        """Dismisses the next user alarm"""
        if not self.next_alarm_id:
            raise Exception(f"No next alarm ID set for {self.user_id}")
        url = APP_API_URL + f"v1/users/{self.user_id}/routines"
        data = {"alarm": {"alarmId": self.next_alarm_id, "dismissed": True}}
        await self.device.api_request("PUT", url, data=data)

    async def update_user_profile(self) -> None:
        """Update user profile data."""
        url = f"{CLIENT_API_URL}/users/{self.user_id}"
        profile_data = await self.device.api_request("get", url)
        if profile_data is None:
            _LOGGER.error("Unable to fetch user profile data for %s", self.user_id)
        else:
            self._user_profile = profile_data["user"]

    async def update_trend_data(self, start_date: str, end_date: str) -> None:
        """Update trends data json for specified time period."""
        url = f"{CLIENT_API_URL}/users/{self.user_id}/trends"
        params = {
            "tz": self.device.timezone,
            "from": start_date,
            "to": end_date,
            "include-main": "false",
            "include-all-sessions": "true",
            "model-version": "v2",
        }
        trend_data = await self.device.api_request("get", url, params=params)
        self.trends = trend_data.get("days", [])

    async def update_routines_data(self) -> None:
        """Legacy method - now redirects to update_alarm_data for compatibility."""
        await self.update_alarm_data()

    async def update_base_data(self):
        """Update the data about the bed base."""
        if self.device.has_base:
            url = f"{APP_API_URL}v1/users/{self.user_id}/base"
            self._base_data = await self.device.api_request("GET", url)

    async def set_base_angle(self, leg_angle: int, torso_angle: int) -> None:
        """Set the angles of the bed base."""
        if self.device.has_base:
            # Update the angles locally
            self.base_data_for_side["leg"]["currentAngle"] = leg_angle
            self.base_data_for_side["torso"]["currentAngle"] = torso_angle

            url = f"{APP_API_URL}v1/users/{self.user_id}/base/angle?ignoreDeviceErrors=false"
            payload = {
                "deviceId": self.device.device_id,
                "deviceOnline": True,
                "legAngle": leg_angle,
                "torsoAngle": torso_angle,
                "enableOfflineMode": False
            }
            await self.device.api_request("POST", url, data=payload, return_json=False)

    async def set_base_preset(self, preset: str) -> None:
        """Set the preset of the bed base."""
        if self.device.has_base:
            # Update the preset locally
            self.base_data_for_side.setdefault("preset", {})["name"] = preset

            url = f"{APP_API_URL}v1/users/{self.user_id}/base/angle?ignoreDeviceErrors=false"
            payload = {
                "deviceId": self.device.device_id,
                "deviceOnline": True,
                "preset": preset,
                "enableOfflineMode": False
            }
            await self.device.api_request("POST", url, data=payload, return_json=False)