"""
Time parsing for RunAgent Pulse
Supports ISO 8601, relative times, cron expressions, and natural language
"""
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta
from croniter import croniter
import pytz
import re
import time
import logging
import os
from typing import Optional

DEBUG = os.getenv("PULSE_DEBUG", "false").lower() == "true"
logger = logging.getLogger("runagent_pulse.time_parser")

class TimeParser:
    def __init__(self, timezone: str = "UTC"):
        self.timezone = pytz.timezone(timezone)
        self.utc = pytz.UTC
        
    def parse(self, when: dict) -> tuple[int, Optional[dict]]:
        """
        Parse time specification and return (timestamp, recurrence_rule)
        
        Args:
            when: Dict with 'type' and time specification
            
        Returns:
            (next_execution_timestamp, recurrence_rule or None)
        """
        when_type = when.get("type", "once")
        
        if DEBUG:
            logger.debug(f"Parsing when dict: {when}, type={when_type}")
        
        try:
            if when_type == "once":
                result = self._parse_once(when)
                if DEBUG:
                    logger.debug(f"Parsed once: {result}")
                return result
            elif when_type == "recurring":
                result = self._parse_recurring(when)
                if DEBUG:
                    logger.debug(f"Parsed recurring: {result}")
                return result
            elif when_type == "cron":
                result = self._parse_cron(when)
                if DEBUG:
                    logger.debug(f"Parsed cron: {result}")
                return result
            else:
                raise ValueError(f"Unknown schedule type: {when_type}")
        except Exception as e:
            if DEBUG:
                logger.debug(f"Error parsing when={when}: {str(e)}", exc_info=True)
            raise
    
    def _parse_once(self, when: dict) -> tuple[int, None]:
        """Parse one-time execution"""
        if "time" in when:
            # ISO 8601 timestamp
            dt = date_parser.parse(when["time"])
            if dt.tzinfo is None:
                dt = self.timezone.localize(dt)
            dt = dt.astimezone(self.utc)
            return int(dt.timestamp()), None
            
        elif "delay" in when:
            # Relative delay (e.g., "5m", "2h", "1d")
            delay_seconds = self._parse_delay(when["delay"])
            next_time = datetime.now(self.utc) + timedelta(seconds=delay_seconds)
            return int(next_time.timestamp()), None
            
        elif "natural" in when:
            # Natural language (e.g., "tomorrow at 2pm", "in 5 minutes")
            timestamp = self._parse_natural_language(when["natural"])
            return timestamp, None
        else:
            raise ValueError("Invalid 'once' schedule: must specify 'time', 'delay', or 'natural'")
    
    def _parse_recurring(self, when: dict) -> tuple[int, dict]:
        """Parse recurring task"""
        repeat = when.get("repeat", {})
        interval = repeat.get("interval", "1d")
        times = repeat.get("times")  # None = infinite
        
        if DEBUG:
            logger.debug(f"Parsing recurring task: repeat={repeat}, interval={interval}, times={times}")
        
        # Calculate first execution
        if "time" in when:
            dt = date_parser.parse(when["time"])
            if dt.tzinfo is None:
                dt = self.timezone.localize(dt)
            dt = dt.astimezone(self.utc)
            first_execution = int(dt.timestamp())
            if DEBUG:
                logger.debug(f"First execution from time: {first_execution}")
        elif "delay" in when:
            delay_seconds = self._parse_delay(when["delay"])
            next_time = datetime.now(self.utc) + timedelta(seconds=delay_seconds)
            first_execution = int(next_time.timestamp())
            if DEBUG:
                logger.debug(f"First execution from delay: {first_execution} (delay={when['delay']})")
        else:
            # Start immediately
            first_execution = int(time.time())
            if DEBUG:
                logger.debug(f"First execution immediately: {first_execution}")
        
        # Calculate interval in seconds
        interval_seconds = self._parse_interval(interval)
        
        if DEBUG:
            logger.debug(f"Interval parsed: {interval} -> {interval_seconds} seconds")
        
        recurrence = {
            "interval_seconds": interval_seconds,
            "times": times,
            "execution_count": 0
        }
        
        if DEBUG:
            logger.debug(f"Recurrence config: {recurrence}")
        
        return first_execution, recurrence
    
    def _parse_cron(self, when: dict) -> tuple[int, dict]:
        """Parse cron expression"""
        cron_expr = when.get("cron")
        if not cron_expr:
            raise ValueError("Cron schedule requires 'cron' field")
        
        # Validate cron expression
        try:
            # Use current time in UTC
            base_time = datetime.now(self.utc)
            iter = croniter(cron_expr, base_time)
            next_time = iter.get_next()
            return int(next_time), {"cron": cron_expr}
        except Exception as e:
            raise ValueError(f"Invalid cron expression: {e}")
    
    def _parse_delay(self, delay_str: str) -> int:
        """Parse delay string like '5m', '2h', '1d'"""
        # Remove whitespace and convert to lowercase
        delay_str = delay_str.strip().lower()
        
        # Pattern: number followed by unit
        pattern = r'^(\d+)([smhdw])$'
        match = re.match(pattern, delay_str)
        
        if not match:
            raise ValueError(f"Invalid delay format: {delay_str}. Use format like '5m', '2h', '1d'")
        
        value = int(match.group(1))
        unit = match.group(2)
        
        unit_multipliers = {
            's': 1,
            'm': 60,
            'h': 3600,
            'd': 86400,
            'w': 604800
        }
        
        return value * unit_multipliers[unit]
    
    def _parse_interval(self, interval_str: str) -> int:
        """Parse interval string (same format as delay)"""
        return self._parse_delay(interval_str)
    
    def _parse_natural_language(self, natural_str: str) -> int:
        """
        Parse natural language time expressions
        Examples: "tomorrow at 2pm", "in 5 minutes", "next Monday at 9am", "now"
        """
        natural_str = natural_str.strip().lower()
        # Use server timezone for natural language interpretation
        now = datetime.now(self.timezone)
        
        # Handle "now" - return current time immediately
        if natural_str == "now":
            return int(now.astimezone(self.utc).timestamp())
        
        # "in X minutes/hours/days"
        in_match = re.match(r'^in\s+(\d+)\s+(minute|minutes|hour|hours|day|days|second|seconds)s?$', natural_str)
        if in_match:
            value = int(in_match.group(1))
            unit = in_match.group(2).rstrip('s')
            
            if unit in ['second', 'seconds']:
                delta = timedelta(seconds=value)
            elif unit in ['minute', 'minutes']:
                delta = timedelta(minutes=value)
            elif unit in ['hour', 'hours']:
                delta = timedelta(hours=value)
            elif unit in ['day', 'days']:
                delta = timedelta(days=value)
            else:
                raise ValueError(f"Unknown time unit: {unit}")
            
            result = (now + delta).astimezone(self.utc)
            return int(result.timestamp())
        
        # "tomorrow at X" or "tomorrow"
        if natural_str.startswith("tomorrow"):
            tomorrow = now + timedelta(days=1)
            if "at" in natural_str:
                time_match = re.search(r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', natural_str)
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2)) if time_match.group(2) else 0
                    ampm = time_match.group(3)
                    
                    if ampm:
                        if ampm == "pm" and hour != 12:
                            hour += 12
                        elif ampm == "am" and hour == 12:
                            hour = 0
                    
                    tomorrow = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            result = tomorrow.astimezone(self.utc)
            return int(result.timestamp())
        
        # Try dateutil parser as fallback
        try:
            dt = date_parser.parse(natural_str, default=now)
            if dt.tzinfo is None:
                dt = self.timezone.localize(dt)
            dt = dt.astimezone(self.utc)
            return int(dt.timestamp())
        except Exception as e:
            raise ValueError(f"Could not parse natural language time: {natural_str}. Error: {e}")
    
    def calculate_next_execution(self, schedule_config: dict, current_time: int) -> Optional[int]:
        """
        Calculate next execution time based on schedule config and current time
        
        Args:
            schedule_config: Schedule configuration dict
            current_time: Current Unix timestamp
            
        Returns:
            Next execution timestamp or None if no more executions
        """
        when = schedule_config.get("when", {})
        when_type = when.get("type", "once")
        
        if when_type == "once":
            # One-time task, check if already executed
            if "time" in when:
                dt = date_parser.parse(when["time"])
                if dt.tzinfo is None:
                    dt = self.timezone.localize(dt)
                dt = dt.astimezone(self.utc)
                exec_time = int(dt.timestamp())
                return exec_time if exec_time > current_time else None
            return None
            
        elif when_type == "recurring":
            repeat = schedule_config.get("repeat", {})
            interval_seconds = repeat.get("interval_seconds", 86400)
            times = repeat.get("times")  # None = infinite
            execution_count = repeat.get("execution_count", 0)
            
            if times is not None and execution_count >= times:
                return None  # No more executions
            
            # Calculate next execution from scheduled time, not completion time
            # Use the scheduled time from the task's next_execution field
            scheduled_time = schedule_config.get("scheduled_time", current_time)
            next_execution = scheduled_time + interval_seconds
            
            # Ensure it's in the future
            if next_execution <= current_time:
                # Calculate how many intervals have passed
                intervals_passed = (current_time - scheduled_time) // interval_seconds + 1
                next_execution = scheduled_time + (intervals_passed * interval_seconds)
            
            return next_execution
            
        elif when_type == "cron":
            cron_expr = when.get("cron")
            if not cron_expr:
                return None
            
            try:
                base_time = datetime.fromtimestamp(current_time, tz=self.utc)
                iter = croniter(cron_expr, base_time)
                next_time = iter.get_next()
                return int(next_time)
            except Exception as e:
                return None
        
        return None



