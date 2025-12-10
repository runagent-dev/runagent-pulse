"""Helper for constructing tool context."""
from server.tools.catalog import ToolContext
from server.services import TaskService
from server.database import Database
from server.scheduler import Scheduler
from server.settings import Settings


def build_tool_context(
    task_service: TaskService,
    db: Database,
    scheduler: Scheduler,
    settings: Settings,
) -> ToolContext:
    return ToolContext(
        task_service=task_service,
        db=db,
        scheduler=scheduler,
        settings=settings,
    )

