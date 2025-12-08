"""Dashboard routing."""
from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter(tags=["dashboard"])


@router.get("/")
async def root():
    """Redirect to dashboard UI."""
    return RedirectResponse(url="/dashboard")

