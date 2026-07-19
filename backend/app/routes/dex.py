from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth.deps import require_observer
from app.deps import get_conn, get_storage
from app.storage.s3 import S3Storage

router = APIRouter()


@router.get("/dex")
async def get_dex(
    observer_id: UUID = Depends(require_observer),
    conn=Depends(get_conn),
    storage: S3Storage = Depends(get_storage),
):
    rows = await conn.fetch(
        """
        SELECT
            s.id AS sighting_id,
            s.captured_at,
            ST_Y(s.geog::geometry) AS lat,
            ST_X(s.geog::geometry) AS lng,
            s.geo_accuracy_m,
            p.id AS photo_id,
            p.s3_key
        FROM sightings s
        LEFT JOIN photos p ON p.sighting_id = s.id
        WHERE s.observer_id = $1
        ORDER BY s.captured_at DESC, p.created_at ASC
        """,
        observer_id,
    )

    sightings: dict[str, dict] = {}
    order: list[str] = []
    for row in rows:
        sid = str(row["sighting_id"])
        if sid not in sightings:
            sightings[sid] = {
                "id": sid,
                "captured_at": row["captured_at"],
                "lat": row["lat"],
                "lng": row["lng"],
                "geo_accuracy_m": row["geo_accuracy_m"],
                "photos": [],
            }
            order.append(sid)
        if row["photo_id"] is not None:
            s3_key = row["s3_key"]
            url = await storage.url(s3_key)
            thumb_url = await storage.url(s3_key.replace(".jpg", "_thumb.jpg"))
            sightings[sid]["photos"].append({"url": url, "thumb_url": thumb_url})

    return {"sightings": [sightings[sid] for sid in order]}
