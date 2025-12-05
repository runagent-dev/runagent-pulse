"""
Tests for time parser
"""
import pytest
from datetime import datetime
import pytz
from server.time_parser import TimeParser

def test_parse_iso_8601():
    """Test ISO 8601 parsing"""
    parser = TimeParser()
    when = {"type": "once", "time": "2024-12-05T14:30:00Z"}
    timestamp, recurrence = parser.parse(when)
    assert recurrence is None
    assert timestamp > 0

def test_parse_delay():
    """Test relative delay parsing"""
    parser = TimeParser()
    when = {"type": "once", "delay": "5m"}
    timestamp, recurrence = parser.parse(when)
    assert recurrence is None
    assert timestamp > 0

def test_parse_delay_formats():
    """Test various delay formats"""
    parser = TimeParser()
    
    formats = ["5s", "10m", "2h", "1d", "1w"]
    for delay in formats:
        when = {"type": "once", "delay": delay}
        timestamp, _ = parser.parse(when)
        assert timestamp > 0

def test_parse_recurring():
    """Test recurring task parsing"""
    parser = TimeParser()
    when = {
        "type": "recurring",
        "delay": "5m",
        "repeat": {"interval": "1h", "times": 5}
    }
    timestamp, recurrence = parser.parse(when)
    assert recurrence is not None
    assert "interval_seconds" in recurrence

def test_parse_cron():
    """Test cron expression parsing"""
    parser = TimeParser()
    when = {"type": "cron", "cron": "0 9 * * *"}
    timestamp, recurrence = parser.parse(when)
    assert recurrence is not None
    assert "cron" in recurrence

def test_parse_natural_language():
    """Test natural language parsing"""
    parser = TimeParser()
    when = {"type": "once", "natural": "in 5 minutes"}
    timestamp, recurrence = parser.parse(when)
    assert recurrence is None
    assert timestamp > 0

def test_calculate_next_execution():
    """Test next execution calculation"""
    parser = TimeParser()
    current_time = int(datetime.now(pytz.UTC).timestamp())
    
    # One-time task
    schedule_config = {
        "when": {"type": "once", "time": "2024-12-05T14:30:00Z"}
    }
    next_exec = parser.calculate_next_execution(schedule_config, current_time)
    assert next_exec is not None or current_time > int(datetime(2024, 12, 5, 14, 30, 0).timestamp())
    
    # Recurring task
    schedule_config = {
        "when": {"type": "recurring"},
        "repeat": {"interval_seconds": 3600, "times": None, "execution_count": 0},
        "last_execution": current_time - 1800
    }
    next_exec = parser.calculate_next_execution(schedule_config, current_time)
    assert next_exec is not None
    assert next_exec > current_time


