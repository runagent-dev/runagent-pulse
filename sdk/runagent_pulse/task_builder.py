"""
Task Builder for fluent task creation
"""
from typing import Optional, Dict, Any, List
from runagent_pulse.client import PulseClient, PulseTask

class TaskBuilder:
    """Fluent interface for building tasks"""
    
    def __init__(self, client: PulseClient):
        self.client = client
        self.schedule_type: Optional[str] = None
        self.when: Optional[Dict[str, Any]] = None
        self.payload: Dict[str, Any] = {}
        self.repeat: Optional[Dict[str, Any]] = None
        self.metadata: Dict[str, Any] = {}
    
    def type(self, schedule_type: str) -> 'TaskBuilder':
        """Set schedule type"""
        self.schedule_type = schedule_type
        return self
    
    def in_(self, time_spec: str) -> 'TaskBuilder':
        """Set execution time (natural language or ISO)"""
        self.when = self.client._normalize_when(time_spec)
        return self
    
    def at(self, time_spec: str) -> 'TaskBuilder':
        """Alias for in_"""
        return self.in_(time_spec)
    
    def with_payload(self, **kwargs) -> 'TaskBuilder':
        """Set payload fields"""
        self.payload.update(kwargs)
        return self
    
    def repeat(self, times: Optional[int] = None, every: str = "1d") -> 'TaskBuilder':
        """Set repeat configuration"""
        self.repeat = {
            "times": times,
            "interval": every
        }
        return self
    
    def tag(self, *tags: str) -> 'TaskBuilder':
        """Add tags to metadata"""
        if "tags" not in self.metadata:
            self.metadata["tags"] = []
        self.metadata["tags"].extend(tags)
        return self
    
    def with_metadata(self, **kwargs) -> 'TaskBuilder':
        """Add metadata fields"""
        self.metadata.update(kwargs)
        return self
    
    def build(self) -> PulseTask:
        """Build and schedule the task"""
        if not self.schedule_type:
            raise ValueError("Schedule type is required")
        if not self.when:
            raise ValueError("Execution time is required")
        
        return self.client.schedule(
            schedule_type=self.schedule_type,
            when=self.when,
            payload=self.payload,
            repeat=self.repeat,
            metadata=self.metadata if self.metadata else None
        )


