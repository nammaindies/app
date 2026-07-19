import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.responses import JSONResponse

from app.auth.deps import require_observer
from app.deps import get_conn, get_storage
from app.ids import uuid7
from app.photos import process_photo, ProcessedPhoto
from app.storage.s3 import S3Storage
from app.video import extract_diverse_frames

router = APIRouter()


@router.post("/sighting")
async def create_sighting(
    photos: list[UploadFile] | None = File(None),
    video: UploadFile | None = File(None),
    lat: float | None = Form(None),
    lng: float | None = Form(None),
    geo_accuracy_m: float | None = Form(None),
    geo_source: Literal["device_gps", "pin", "none"] = Form(...),
    captured_at: datetime = Form(...),
    reported_at: datetime | None = Form(None),
    note: str | None = Form(None),
    sex: Literal["male", "female", "unsure"] | None = Form(None),
    ear_notch: Literal["none", "left", "right", "unsure"] | None = Form(None),
    condition: Literal["healthy", "injured", "unsure"] | None = Form(None),
    observer_id: UUID = Depends(require_observer),
    conn=Depends(get_conn),
    storage: S3Storage = Depends(get_storage),
):
    if not photos and video is None:
        raise HTTPException(
            status_code=422, detail="at least one photo or a video is required"
        )

    sighting_id = uuid7()
    from_video = video is not None

    processed_frames: list[ProcessedPhoto]
    if from_video:
        raw_video = await video.read()
        try:
            processed_frames = extract_diverse_frames(raw_video)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        # raw video bytes are never persisted -- discarded here.
    else:
        processed_frames = [process_photo(await f.read()) for f in photos]

    photo_rows = []
    first_phash: str | None = None
    for p in processed_frames:
        photo_id = uuid7()
        if first_phash is None:
            first_phash = p.phash
        orig_key = f"sightings/{sighting_id}/{photo_id}.jpg"
        thumb_key = f"sightings/{sighting_id}/{photo_id}_thumb.jpg"
        await storage.put(orig_key, p.original, "image/jpeg")
        await storage.put(thumb_key, p.thumbnail, "image/jpeg")
        photo_rows.append(
            {
                "id": photo_id,
                "s3_key": orig_key,
                "width": p.width,
                "height": p.height,
                "phash": p.phash,
            }
        )

    geog_present = geo_source != "none" and lat is not None and lng is not None
    attrs = {
        k: v
        for k, v in {
            "note": note,
            "sex": sex,
            "ear_notch": ear_notch,
            "condition": condition,
        }.items()
        if v
    }
    if from_video:
        attrs["source"] = "video"

    async with conn.transaction():
        if geog_present:
            await conn.execute(
                """
                INSERT INTO sightings
                    (id, observer_id, captured_at, reported_at, geog, geo_source,
                     geo_accuracy_m, individual_id, match_status, review_status,
                     phash, attrs)
                VALUES
                    ($1, $2, $3, $4,
                     ST_SetSRID(ST_MakePoint($5, $6), 4326)::geography,
                     $7, $8, NULL, 'unmatched', 'valid', $9, $10::jsonb)
                """,
                sighting_id,
                observer_id,
                captured_at,
                reported_at,
                lng,
                lat,
                geo_source,
                geo_accuracy_m,
                first_phash,
                json.dumps(attrs),
            )
        else:
            await conn.execute(
                """
                INSERT INTO sightings
                    (id, observer_id, captured_at, reported_at, geog, geo_source,
                     geo_accuracy_m, individual_id, match_status, review_status,
                     phash, attrs)
                VALUES
                    ($1, $2, $3, $4, NULL, $5, $6, NULL, 'unmatched', 'valid', $7, $8::jsonb)
                """,
                sighting_id,
                observer_id,
                captured_at,
                reported_at,
                geo_source,
                geo_accuracy_m,
                first_phash,
                json.dumps(attrs),
            )

        for row in photo_rows:
            await conn.execute(
                """
                INSERT INTO photos (id, sighting_id, s3_key, width, height, phash)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                row["id"],
                sighting_id,
                row["s3_key"],
                row["width"],
                row["height"],
                row["phash"],
            )

    return JSONResponse(
        status_code=201,
        content={
            "sighting_id": str(sighting_id),
            "photo_ids": [str(r["id"]) for r in photo_rows],
        },
    )
