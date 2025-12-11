"""
Base Executor Interface
All agent executors must implement this interface
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

logger = logging.getLogger("runagent_pulse.executor.base")


class BaseExecutor(ABC):
    """Base class for all agent executors"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"runagent_pulse.executor.{name}")
    
    @abstractmethod
    async def execute(
        self,
        agent_id: str,
        entrypoint_tag: str,
        params: Dict[str, Any],
        user_id: Optional[str] = None,
        persistent_memory: bool = False,
        **kwargs
    ) -> Any:
        """
        Execute an agent
        
        Args:
            agent_id: Agent ID
            entrypoint_tag: Entrypoint to execute
            params: Parameters to pass to agent
            user_id: Optional user ID for persistent memory
            persistent_memory: Enable persistent memory
            **kwargs: Additional executor-specific parameters
            
        Returns:
            Execution result
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if executor is available/configured
        
        Returns:
            True if executor can be used
        """
        pass
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Validate execution parameters
        
        Args:
            params: Parameters to validate
            
        Returns:
            True if valid
        """
        return True

