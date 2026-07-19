"""Pure, DB-free image processing for uploaded photos.

Given raw uploaded photo bytes, produce:
  (a) a metadata-stripped, fidelity-preserved original (privacy-safe but
      NOT degraded -- the ML-grade asset for future re-ID work),
  (b) a small thumbnail for the gallery,
  (c) dimensions plus a perceptual hash.

NOTE: final format/fidelity policy is pending GitHub issue #1 (vision-model
input requirements). The conservative default here re-encodes to
high-quality JPEG with no downscale; if that policy changes, only the
internals of process_photo should need to change.
"""

import io
from dataclasses import dataclass

import imagehash
from PIL import Image, ImageOps

THUMBNAIL_MAX = 512  # longest edge of the thumbnail, px


@dataclass
class ProcessedPhoto:
    original: bytes  # metadata-stripped, full-resolution JPEG (no downscale)
    thumbnail: bytes  # small JPEG for the gallery
    width: int  # of the original
    height: int
    phash: str  # perceptual hash hex (imagehash.phash)
    content_type: str  # "image/jpeg"


def process_photo(raw: bytes) -> ProcessedPhoto:
    img = Image.open(io.BytesIO(raw))

    # Apply EXIF orientation first so pixels are upright, then we discard
    # all metadata (including GPS) by simply never re-attaching it below.
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")

    width, height = img.size

    original_buf = io.BytesIO()
    img.save(original_buf, "JPEG", quality=95, optimize=True)
    original_bytes = original_buf.getvalue()

    thumb = img.copy()
    thumb.thumbnail((THUMBNAIL_MAX, THUMBNAIL_MAX))
    thumb_buf = io.BytesIO()
    thumb.save(thumb_buf, "JPEG", quality=80)
    thumbnail_bytes = thumb_buf.getvalue()

    phash = str(imagehash.phash(img))

    return ProcessedPhoto(
        original=original_bytes,
        thumbnail=thumbnail_bytes,
        width=width,
        height=height,
        phash=phash,
        content_type="image/jpeg",
    )
