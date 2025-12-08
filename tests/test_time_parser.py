import time
from runagent_pulse.time import TimeParser


def test_parse_once_delay_returns_future_timestamp():
    parser = TimeParser()
    ts, recurrence = parser.parse({"type": "once", "delay": "2s"})
    assert recurrence is None
    # Allow small timing drift
    assert ts - int(time.time()) in {1, 2, 3}


def test_calculate_next_execution_recurring():
    parser = TimeParser()
    first, recurrence = parser.parse({"type": "recurring", "repeat": {"interval": "1m"}})
    config = {"when": {"type": "recurring"}, "repeat": recurrence, "scheduled_time": first}
    next_exec = parser.calculate_next_execution(config, current_time=first)
    assert next_exec == first + recurrence["interval_seconds"]

