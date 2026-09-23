"""Profile pictures: small, square, and stripped of everything but the picture.

Whatever someone uploads (a phone photo, a screenshot) is cropped to a square,
scaled to 256px and re-encoded as WebP. Re-encoding drops the camera's EXIF
data with it, so a picture can't carry a location or a device id into the
database. A person without a picture gets their initials instead, drawn by the
web app (components/ui/avatar.tsx) rather than stored here.
"""

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

# What a browser may send us, before resizing.
MAX_UPLOAD_BYTES = 6 * 1024 * 1024
SIZE = 256
CONTENT_TYPE = "image/webp"
# Faces sit above the middle of a photo, so crop a little high.
CENTRE = (0.5, 0.4)


class PhotoError(ValueError):
    """The upload isn't a picture we can use."""


def square_photo(data: bytes) -> bytes:
    """A 256px square WebP, or PhotoError. Raises before decoding anything huge."""
    if not data:
        raise PhotoError("Pick a picture to upload.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise PhotoError(f"That picture is over {MAX_UPLOAD_BYTES // (1024 * 1024)}MB. Try a smaller one.")
    try:
        with Image.open(BytesIO(data)) as image:
            # An animation's first frame is enough; a photo has only one.
            image.seek(0)
            upright = ImageOps.exif_transpose(image).convert("RGB")
            square = ImageOps.fit(upright, (SIZE, SIZE), Image.LANCZOS, centering=CENTRE)
            out = BytesIO()
            square.save(out, "WEBP", quality=82, method=4)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise PhotoError("That file isn't a picture Orbit can read. Use a JPEG, PNG or WebP.") from exc
    return out.getvalue()
