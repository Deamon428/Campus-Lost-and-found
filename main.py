from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
import logging
import os
from pathlib import Path
import re
import secrets
import sqlite3
from typing import Annotated, Optional
from uuid import uuid4

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
    status as http_status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from models import (
    VALID_CATEGORIES,
    VALID_LOCATIONS,
    VALID_TYPES,
    get_db,
    init_db,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = STATIC_DIR / "uploads"

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
UPLOAD_CHUNK_SIZE = 64 * 1024  # 64 KiB
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize required directories and database schema on startup."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    init_db()
    yield


app = FastAPI(title="Campus Lost & Found API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def serve_frontend() -> FileResponse:
    """Serve the Campus Lost & Found single-page web UI."""
    return FileResponse(STATIC_DIR / "index.html")


def _validate_choice(
    value: str,
    allowed: tuple[str, ...],
    field_name: str,
    *,
    lowercase: bool = False,
) -> str:
    """Normalize a string field and verify it matches one of the allowed values."""
    normalized = value.strip()
    if lowercase:
        normalized = normalized.lower()
    if normalized not in allowed:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}. Must be one of: {', '.join(allowed)}.",
        )
    return normalized


def _validate_title(value: str) -> str:
    """Trim whitespace and enforce minimum title length."""
    cleaned = value.strip()
    if len(cleaned) < 3:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Title must be at least 3 characters long.",
        )
    return cleaned


def _validate_date_reported(value: str) -> str:
    """Ensure date_reported is a valid calendar date in YYYY-MM-DD format."""
    cleaned = value.strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", cleaned):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="date_reported must be in YYYY-MM-DD format.",
        )
    try:
        date.fromisoformat(cleaned)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="date_reported is not a valid calendar date.",
        ) from exc
    return cleaned


def _validate_contact_phone(value: str) -> str:
    """Strip non-digits and validate a 10-digit mobile number starting with 6-9."""
    digits = re.sub(r"\D", "", value)
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="contact_phone must contain 10 digits starting with 6-9.",
        )
    return digits


async def _save_upload_image(image: UploadFile) -> str:
    """Validate extension and stream an uploaded image to static/uploads."""
    ext = Path(image.filename or "").suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        await image.close()
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid image extension. Allowed: .jpg, .jpeg, .png, .webp.",
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"{uuid4().hex}{ext}"
    destination = UPLOAD_DIR / filename

    try:
        with open(destination, "wb") as out_file:
            while chunk := await image.read(UPLOAD_CHUNK_SIZE):
                out_file.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await image.close()

    return filename


def _escape_like_term(term: str) -> str:
    """Escape SQL LIKE wildcard characters so search behaves as a literal substring."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@app.post("/api/items", status_code=http_status.HTTP_201_CREATED)
async def create_item(
    type: Annotated[str, Form(...)],
    title: Annotated[str, Form(...)],
    category: Annotated[str, Form(...)],
    location: Annotated[str, Form(...)],
    date_reported: Annotated[str, Form(...)],
    contact_phone: Annotated[str, Form(...)],
    description: Annotated[Optional[str], Form()] = None,
    image: Optional[UploadFile] = File(default=None),
    db: sqlite3.Connection = Depends(get_db),
) -> dict[str, object]:
    """Validate and store a new lost or found item report."""
    clean_type = _validate_choice(type, VALID_TYPES, "type", lowercase=True)
    clean_title = _validate_title(title)
    clean_category = _validate_choice(category, VALID_CATEGORIES, "category")
    clean_location = _validate_choice(location, VALID_LOCATIONS, "location")
    clean_date = _validate_date_reported(date_reported)
    clean_phone = _validate_contact_phone(contact_phone)
    clean_description = description.strip() or None if description is not None else None

    image_filename: Optional[str] = None
    if image is not None:
        if image.filename:
            image_filename = await _save_upload_image(image)
        else:
            await image.close()

    manage_token = secrets.token_hex(6)

    try:
        cursor = db.execute(
            """
            INSERT INTO items (
                type,
                title,
                category,
                location,
                date_reported,
                description,
                image_filename,
                contact_phone,
                status,
                manage_token
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)
            """,
            (
                clean_type,
                clean_title,
                clean_category,
                clean_location,
                clean_date,
                clean_description,
                image_filename,
                clean_phone,
                manage_token,
            ),
        )
        db.commit()
    except Exception:
        if image_filename is not None:
            (UPLOAD_DIR / image_filename).unlink(missing_ok=True)
        raise

    return {
        "status": "success",
        "item_id": cursor.lastrowid,
        "manage_token": manage_token,
    }


@app.get("/api/items")
def list_items(
    type: Annotated[Optional[str], Query()] = None,
    category: Annotated[Optional[str], Query()] = None,
    location: Annotated[Optional[str], Query()] = None,
    status: Annotated[str, Query()] = "open",
    search: Annotated[Optional[str], Query()] = None,
    db: sqlite3.Connection = Depends(get_db),
) -> list[dict[str, object]]:
    """Return filtered lost/found items ordered newest-first without manage_token."""
    conditions: list[str] = []
    params: list[str] = []

    if type and type.strip():
        conditions.append("type = ?")
        params.append(type.strip().lower())

    if category and category.strip():
        conditions.append("category = ?")
        params.append(category.strip())

    if location and location.strip():
        conditions.append("location = ?")
        params.append(location.strip())

    clean_status = status.strip().lower() if status else "open"
    if clean_status and clean_status != "all":
        conditions.append("status = ?")
        params.append(clean_status)

    if search and search.strip():
        pattern = f"%{_escape_like_term(search.strip())}%"
        conditions.append(
            "(LOWER(title) LIKE LOWER(?) ESCAPE '\\' "
            "OR LOWER(COALESCE(description, '')) LIKE LOWER(?) ESCAPE '\\')"
        )
        params.extend([pattern, pattern])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT
            id,
            type,
            title,
            category,
            location,
            date_reported,
            description,
            image_filename,
            contact_phone,
            status,
            created_at
        FROM items
        {where_clause}
        ORDER BY id DESC
    """

    rows = db.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def _get_authorized_item(
    db: sqlite3.Connection,
    item_id: int,
    x_manage_token: Optional[str],
    token: Optional[str],
) -> sqlite3.Row:
    """Fetch an item by ID and verify the provided manage token."""
    item = db.execute(
        "SELECT id, status, image_filename, manage_token FROM items WHERE id = ?",
        (item_id,),
    ).fetchone()
    if item is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    provided_token = (x_manage_token or "").strip() or (token or "").strip()
    if not provided_token or not secrets.compare_digest(
        provided_token, item["manage_token"]
    ):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid manage token",
        )
    return item


@app.patch("/api/items/{item_id}/resolve")
def resolve_item(
    item_id: int,
    x_manage_token: Annotated[Optional[str], Header(alias="X-Manage-Token")] = None,
    token: Annotated[Optional[str], Query()] = None,
    db: sqlite3.Connection = Depends(get_db),
) -> dict[str, str]:
    """Mark an item as resolved after authenticating with manage_token."""
    _get_authorized_item(db, item_id, x_manage_token, token)
    db.execute("UPDATE items SET status = 'resolved' WHERE id = ?", (item_id,))
    db.commit()
    return {"status": "success", "message": "Item marked as resolved"}


@app.delete("/api/items/{item_id}")
def delete_item(
    item_id: int,
    x_manage_token: Annotated[Optional[str], Header(alias="X-Manage-Token")] = None,
    token: Annotated[Optional[str], Query()] = None,
    db: sqlite3.Connection = Depends(get_db),
) -> dict[str, str]:
    """Delete an item and any associated uploaded image after verifying manage_token."""
    item = _get_authorized_item(db, item_id, x_manage_token, token)

    image_filename = item["image_filename"]
    if image_filename:
        image_path = UPLOAD_DIR / Path(image_filename).name
        if image_path.is_file():
            try:
                os.remove(image_path)
            except OSError as exc:
                logger.warning("Failed to remove upload %s: %s", image_path, exc)

    db.execute("DELETE FROM items WHERE id = ?", (item_id,))
    db.commit()
    return {"status": "success", "message": "Item deleted successfully"}
