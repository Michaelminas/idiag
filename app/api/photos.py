"""Photo upload/list/delete API routes."""

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.inventory import get_db
from app.models.sales import PhotoLabel, PhotoRecord
from app.services.photo_manager import PhotoManager

router = APIRouter(prefix="/api/photos", tags=["photos"])
_pm = PhotoManager()


@router.post("/upload/{device_id}")
async def upload_photo(device_id: int, file: UploadFile, label: PhotoLabel = "other") -> dict:
    device = get_db().get_device_by_id(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    data = await file.read()
    ext = "." + (file.filename or "photo.jpg").rsplit(".", 1)[-1]
    filename, relpath = _pm.save(device.udid, data, label=label, extension=ext)

    photo_id = get_db().save_photo(PhotoRecord(
        device_id=device_id, filename=filename, filepath=relpath, label=label,
    ))
    return {"id": photo_id, "filename": filename, "filepath": relpath}


@router.get("/device/{device_id}")
def list_photos(device_id: int) -> list[PhotoRecord]:
    return get_db().list_photos(device_id)


@router.get("/file/{photo_id}")
def get_photo_file(photo_id: int):
    db = get_db()
    with db._lock:
        row = db.conn.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Photo not found")

    path = _pm.get_path(row["filepath"])
    if not path:
        raise HTTPException(status_code=404, detail="Photo file missing")
    return FileResponse(path)


@router.delete("/{photo_id}")
def delete_photo(photo_id: int) -> dict:
    db = get_db()
    with db._lock:
        row = db.conn.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Photo not found")

    _pm.delete(row["filepath"])
    db.delete_photo(photo_id)
    return {"deleted": True}
