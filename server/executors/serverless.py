"""
Serverless Executor
Executes agents via RunAgent Serverless SDK
"""
import asyncio
import logging
from typing import Dict, Any, Optional

from server.executors.base import BaseExecutor

logger = logging.getLogger("runagent_pulse.executor.serverless")


class ServerlessExecutor(BaseExecutor):
    """Executor for RunAgent Serverless"""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__("serverless")
        self.api_key = api_key
    
    def is_available(self) -> bool:
        """Check if RunAgent Serverless SDK is available"""
        try:
            from runagent import RunAgentClient
            return True
        except ImportError:
            return False
    
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
        Execute agent via RunAgent Serverless
        
        Args:
            agent_id: Agent ID
            entrypoint_tag: Entrypoint to execute
            params: Parameters to pass to agent
            user_id: Optional user ID for persistent memory
            persistent_memory: Enable persistent memory
            
        Returns:
            Execution result
        """
        try:
            from runagent import RunAgentClient
        except ImportError:
            raise ImportError(
                "runagent package not installed. Install with: pip install runagent"
            )
        
        self.logger.info(
            f"Executing agent via Serverless: agent_id={agent_id}, "
            f"entrypoint_tag={entrypoint_tag}"
        )
        
        # Set API key and base URL in environment if provided
        # RunAgentClient reads from RUNAGENT_API_KEY and RUNAGENT_BASE_URL
        # This MUST be set before creating RunAgentClient, as the SDK reads it during initialization
        import os
        original_api_key = os.environ.get("RUNAGENT_API_KEY")
        original_base_url = os.environ.get("RUNAGENT_BASE_URL")
        
        if self.api_key:
            os.environ["RUNAGENT_API_KEY"] = self.api_key
            self.logger.debug(f"Set RUNAGENT_API_KEY for serverless execution")
        else:
            self.logger.warning("No API key provided - serverless execution may fail")
        
        # Base URL should already be set in docker-compose.yml, but log it for debugging
        current_base_url = os.environ.get("RUNAGENT_BASE_URL")
        if current_base_url:
            self.logger.info(f"Using RunAgent base URL: {current_base_url}")
        else:
            self.logger.warning("No RUNAGENT_BASE_URL set - using default (https://backend.run-agent.ai/)")
        
        try:
            client = RunAgentClient(
                agent_id=agent_id,
                entrypoint_tag=entrypoint_tag,
                local=False,  # Always use serverless - this is critical!
                user_id=user_id,
                persistent_memory=persistent_memory,
            )
            
            # Verify that client is configured for serverless (not local)
            if client.local:
                raise ValueError(
                    "RunAgentClient was initialized in local mode, but serverless mode was requested. "
                    "Check that local=False is being respected."
                )
            
            self.logger.debug(f"RunAgentClient created: local={client.local}, agent_id={agent_id}")
        finally:
            # Restore original environment variables if we changed them
            if original_api_key is not None:
                os.environ["RUNAGENT_API_KEY"] = original_api_key
            elif "RUNAGENT_API_KEY" in os.environ and self.api_key:
                del os.environ["RUNAGENT_API_KEY"]
            
            if original_base_url is not None:
                os.environ["RUNAGENT_BASE_URL"] = original_base_url
            elif "RUNAGENT_BASE_URL" in os.environ and original_base_url is None:
                # Don't delete if it was set in docker-compose.yml
                pass
        
        # RunAgentClient.run() is synchronous, so we run it in a thread
        def run_agent():
            # Log detailed information about the client configuration
            self.logger.info(f"Calling client.run() with params: {params}")
            self.logger.info(f"Client config: local={client.local}, agent_id={client.agent_id}, entrypoint={client.entrypoint_tag}")
            
            # Check RestClient configuration
            if hasattr(client, 'rest_client'):
                rest_client = client.rest_client
                base_url = getattr(rest_client, 'base_url', 'N/A')
                api_key_set = bool(getattr(rest_client, 'api_key', None))
                self.logger.info(f"RestClient base_url: {base_url}")
                self.logger.info(f"RestClient api_key set: {api_key_set}")
                
                # Check HTTP handler
                if hasattr(rest_client, 'http'):
                    http_handler = rest_client.http
                    http_base_url = getattr(http_handler, 'base_url', 'N/A')
                    http_api_key = bool(getattr(http_handler, 'api_key', None))
                    self.logger.info(f"HttpHandler base_url: {http_base_url}")
                    self.logger.info(f"HttpHandler api_key set: {http_api_key}")
            
            result = client.run(**params)
            self.logger.info(f"Agent execution completed, result type: {type(result)}")
            return result
        
        # Execute with timeout (10 minutes max)
        result = await asyncio.wait_for(
            asyncio.to_thread(run_agent),
            timeout=600.0,
        )
        
        self.logger.info(f"Agent execution completed: agent_id={agent_id}")
        return result

