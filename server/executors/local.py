"""
Local Executor
Executes agents locally (not via RunAgent Serverless)
"""
import asyncio
import logging
import importlib
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from server.executors.base import BaseExecutor

logger = logging.getLogger("runagent_pulse.executor.local")


class LocalExecutor(BaseExecutor):
    """Executor for local agent execution"""
    
    def __init__(self, agent_path: Optional[str] = None):
        super().__init__("local")
        self.agent_path = agent_path
        self._agent_modules = {}
    
    def is_available(self) -> bool:
        """Check if local execution is configured"""
        return True  # Always available, but may fail if agent not found
    
    def _load_agent_module(self, agent_id: str, entrypoint_tag: str):
        """
        Load agent module dynamically
        
        Args:
            agent_id: Agent ID (used as module identifier)
            entrypoint_tag: Entrypoint tag (function name)
        """
        cache_key = f"{agent_id}:{entrypoint_tag}"
        
        if cache_key in self._agent_modules:
            return self._agent_modules[cache_key]
        
        # Try to load from agent_path if provided
        if self.agent_path:
            agent_dir = Path(self.agent_path) / agent_id
            if agent_dir.exists():
                sys.path.insert(0, str(agent_dir.parent))
                try:
                    module = importlib.import_module(agent_id)
                    self._agent_modules[cache_key] = module
                    return module
                except ImportError as e:
                    self.logger.warning(f"Failed to import agent module {agent_id}: {e}")
        
        # Try to import as a regular module
        try:
            module = importlib.import_module(agent_id)
            self._agent_modules[cache_key] = module
            return module
        except ImportError:
            raise ImportError(
                f"Could not import agent module '{agent_id}'. "
                f"Make sure the agent is installed or set LOCAL_AGENT_PATH."
            )
    
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
        Execute agent locally
        
        Args:
            agent_id: Agent ID (module name or path)
            entrypoint_tag: Entrypoint function name
            params: Parameters to pass to agent
            user_id: Optional user ID (may be used for state management)
            persistent_memory: Enable persistent memory (if supported)
            
        Returns:
            Execution result
        """
        self.logger.info(
            f"Executing agent locally: agent_id={agent_id}, "
            f"entrypoint_tag={entrypoint_tag}"
        )
        
        # Load agent module
        module = self._load_agent_module(agent_id, entrypoint_tag)
        
        # Get entrypoint function
        if not hasattr(module, entrypoint_tag):
            raise AttributeError(
                f"Entrypoint '{entrypoint_tag}' not found in agent module '{agent_id}'"
            )
        
        entrypoint_func = getattr(module, entrypoint_tag)
        
        # Execute in thread pool (in case it's blocking)
        if asyncio.iscoroutinefunction(entrypoint_func):
            result = await asyncio.wait_for(
                entrypoint_func(**params),
                timeout=600.0,
            )
        else:
            def run_local_agent():
                return entrypoint_func(**params)
            
            result = await asyncio.wait_for(
                asyncio.to_thread(run_local_agent),
                timeout=600.0,
            )
        
        self.logger.info(f"Local agent execution completed: agent_id={agent_id}")
        return result

