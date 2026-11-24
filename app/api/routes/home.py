from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()
HOME_PAGE = (
    Path(__file__).resolve().parent.parent.parent
    / "static"
    / "index.html"
)

# keeping this route at root so it wont be added to swagger docs
@router.get("/", include_in_schema=False)
def home_page():
    return FileResponse(HOME_PAGE)
