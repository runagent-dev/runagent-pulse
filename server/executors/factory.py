"""
Executor Factory
Creates and manages agent executors
"""
import logging
from typing import Optional, Dict, Any

from server.executors.base import BaseExecutor
from server.executors.serverless import ServerlessExecutor
from server.executors.local import LocalExecutor
from server.settings import Settings

logger = logging.getLogger("runagent_pulse.executor.factory")


class ExecutorFactory:
    """Factory for creating agent executors"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._executors: Dict[str, BaseExecutor] = {}
        self._initialize_executors()
    
    def _initialize_executors(self):
        """Initialize available executors"""
        # Serverless executor
        if self.settings.enable_serverless_integration:
            serverless = ServerlessExecutor(api_key=self.settings.runagent_serverless_api_key)
            try:
                if serverless.is_available():
                    self._executors["serverless"] = serverless
                    logger.info("Serverless executor initialized")
                else:
                    logger.warning("Serverless executor not available (runagent package not installed)")
            except Exception as e:
                logger.warning(f"Serverless executor check failed: {e}, but continuing anyway")
                # Try to add it anyway - the import might have worked despite the error
                try:
                    from runagent import RunAgentClient
                    self._executors["serverless"] = serverless
                    logger.info("Serverless executor initialized (despite check error)")
                except:
                    logger.warning("Serverless executor not available")
        
        # Local executor
        local = LocalExecutor(agent_path=self.settings.local_agent_path)
        self._executors["local"] = local
        logger.info("Local executor initialized")
    
    def get_executor(self, executor_type: Optional[str] = None) -> BaseExecutor:
        """
        Get executor by type
        
        Args:
            executor_type: Executor type ("serverless", "local", or None for auto)
            
        Returns:
            Executor instance
            
        Raises:
            ValueError: If executor type is invalid or not available
        """
        if executor_type is None:
            # Auto-select: prefer serverless if available, otherwise local
            if "serverless" in self._executors:
                return self._executors["serverless"]
            return self._executors["local"]
        
        executor_type = executor_type.lower()
        
        if executor_type not in self._executors:
            available = ", ".join(self._executors.keys())
            raise ValueError(
                f"Executor type '{executor_type}' not available. "
                f"Available: {available}"
            )
        
        executor = self._executors[executor_type]
        if not executor.is_available():
            raise ValueError(f"Executor '{executor_type}' is not available")
        
        return executor
    
    def list_available(self) -> list[str]:
        """List available executor types"""
        return [
            name for name, executor in self._executors.items()
            if executor.is_available()
        ]

