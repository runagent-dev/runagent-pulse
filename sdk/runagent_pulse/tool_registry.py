"""
Tool registry that automatically extracts schemas from Pydantic models
"""
from typing import Dict, Any, Optional, Callable, Type, List, Union
from pydantic import BaseModel
import json
import inspect

class ToolDefinition:
    """Tool definition with model-driven schema"""

    def __init__(self, name: str, description: str, param_model: Type[BaseModel], implementation: Callable):
        self.name = name
        self.description = description
        self.param_model = param_model
        self.implementation = implementation
        self._extract_schema()

    def _extract_schema(self):
        """Extract JSON schema from Pydantic model"""
        self.schema = self.param_model.model_json_schema()

        # Extract parameter information for compatibility
        self.parameters = {}
        for field_name, field_info in self.param_model.model_fields.items():
            self.parameters[field_name] = {
                "name": field_name,
                "type": self._get_field_type(field_info),
                "description": field_info.description or "",
                "required": field_info.is_required(),
                "examples": getattr(field_info, 'examples', None)
            }

    def _get_field_type(self, field_info) -> str:
        """Convert Pydantic field type to simple string type"""
        annotation = field_info.annotation

        # Handle Optional types
        if hasattr(annotation, '__origin__') and annotation.__origin__ is Union:
            # Get the non-None type from Optional[T]
            non_none_types = [t for t in annotation.__args__ if t is not type(None)]
            if non_none_types:
                annotation = non_none_types[0]

        # Map common types
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            dict: "object",
            list: "array",
        }

        # Handle Dict and List generics
        if hasattr(annotation, '__origin__'):
            if annotation.__origin__ is dict:
                return "object"
            elif annotation.__origin__ is list:
                return "array"

        return type_mapping.get(annotation, "string")

    def validate_params(self, **kwargs) -> Dict[str, Any]:
        """Validate parameters using Pydantic model"""
        return self.param_model(**kwargs).model_dump()

class ToolRegistry:
    """Registry for individual tools with model-driven schemas"""

    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        param_model: Type[BaseModel],
        implementation: Callable
    ) -> None:
        """Register a tool with its Pydantic parameter model"""
        tool_def = ToolDefinition(name, description, param_model, implementation)
        self.tools[name] = tool_def

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get tool definition by name"""
        return self.tools.get(name)

    def list_tools(self) -> List[ToolDefinition]:
        """List all registered tools"""
        return list(self.tools.values())

    def execute_tool(self, name: str, **kwargs) -> Any:
        """Execute a tool with validated parameters"""
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")

        # Validate parameters
        validated_params = tool.validate_params(**kwargs)

        # Execute
        return tool.implementation(**validated_params)

# Legacy global registry (prefer create_registry for per-app isolation)
default_registry = ToolRegistry()
registry = default_registry


def create_registry() -> ToolRegistry:
    """Factory for a new registry instance."""
    return ToolRegistry()
