"""
Time parser for SDK (simplified version)
"""
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import pytz
import re

class TimeParser:
    """Time parser for client-side time normalization"""
    
    def __init__(self, timezone: str = "UTC"):
        self.timezone = pytz.timezone(timezone)
        self.utc = pytz.UTC
    
    def parse_delay(self, delay_str: str) -> int:
        """Parse delay string like '5m', '2h', '1d'"""
        delay_str = delay_str.strip().lower()
        pattern = r'^(\d+)([smhdw])$'
        match = re.match(pattern, delay_str)
        
        if not match:
            raise ValueError(f"Invalid delay format: {delay_str}")
        
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


