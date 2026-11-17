"""A signature image sent from a screen (feature plan step 10): a PNG, black ink on transparent,
cleaned in the browser by the shared signature pad. The same checks as the Platform's and Finance's."""

import base64
import struct

PNG = b"\x89PNG\r\n\x1a\n"
MAX_BYTES = 300_000
MAX_WIDTH, MAX_HEIGHT = 1200, 600


class BadImage(ValueError):
    """What's wrong with an image sent as a signature, in plain words."""


def checked_png(data_url_or_base64: str) -> bytes:
    raw = data_url_or_base64.split(",", 1)[1] if data_url_or_base64.startswith("data:") else data_url_or_base64
    try:
        image = base64.b64decode(raw, validate=True)
    except ValueError:
        raise BadImage("That isn't an image.") from None
    if len(image) > MAX_BYTES:
        raise BadImage("The signature is too large. Ask them to sign again.")
    if not image.startswith(PNG) or image[12:16] != b"IHDR":
        raise BadImage("The signature must be a PNG image.")
    width, height = struct.unpack(">II", image[16:24])
    if not (10 <= width <= MAX_WIDTH and 10 <= height <= MAX_HEIGHT):
        raise BadImage("The signature's size doesn't look right. Ask them to sign again.")
    return image
