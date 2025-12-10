"""Auto-generated tool endpoints from catalog."""
from fastapi import APIRouter, Depends
from fastapi import HTTPException
from pydantic import ValidationError

from server.dependencies import (
    get_task_service,
    get_db,
    get_scheduler,
    get_settings,
    verify_api_key,
)
from server.tools import list_tools_for, build_tool_context


router = APIRouter(prefix="/tools", tags=["tools"])


def _register_tool_endpoint(tool_def):
    request_model = tool_def.request_model
    response_model = tool_def.response_model

    async def endpoint(
        payload: request_model,  # type: ignore
        task_service=Depends(get_task_service),
        db=Depends(get_db),
        scheduler=Depends(get_scheduler),
        settings=Depends(get_settings),
        _: bool = Depends(verify_api_key),
    ):
        try:
            ctx = build_tool_context(
                task_service=task_service,
                db=db,
                scheduler=scheduler,
                settings=settings,
            )
            return await tool_def.impl(ctx, payload)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    endpoint.__name__ = f"tool_{tool_def.name}"
    router.post(
        f"/{tool_def.name}",
        response_model=response_model,
        name=tool_def.name,
    )(endpoint)


for tool in list_tools_for("http"):
    _register_tool_endpoint(tool)

