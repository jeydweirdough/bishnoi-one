"""Uploaded files, in S3-compatible storage (Neon's), when it's set up.

An order link's prescriptions, guarantee letters and documents go straight
from the customer's browser to the bucket: the API hands out a signed upload
form (presign_upload) that's good for a few minutes, for one name under the
link's own folder, for one kind of file, and up to a size the storage itself
enforces. So a file never passes through the screens' server, whose requests
are capped at 4.5 MB (Vercel's too).

Nothing in the bucket is public. A file is read back only through the API,
which checks first that the person may see the quote it belongs to (read).

Without the settings (AWS_ENDPOINT_URL_S3, AWS_ACCESS_KEY_ID,
AWS_SECRET_ACCESS_KEY), configured() is False and files are kept in the
database as before (StoredFile).
"""

import logging
import threading
from functools import lru_cache
from urllib.parse import urlsplit

from app.config import Settings

log = logging.getLogger(__name__)

# What a file may be, told by its first bytes rather than by what the browser claims.
KINDS = {b"%PDF-": ("application/pdf", ".pdf"), b"\x89PNG\r\n\x1a\n": ("image/png", ".png"), b"\xff\xd8\xff": ("image/jpeg", ".jpg")}
CONTENT_TYPES = {ct: ext for ct, ext in KINDS.values()}
MAX_BYTES = 10 * 1024 * 1024
UPLOAD_SECONDS = 600  # how long a signed upload form works

_cors_done: set[str] = set()
_lock = threading.Lock()


def configured(settings: Settings) -> bool:
    return bool(settings.aws_endpoint_url_s3 and settings.aws_access_key_id and settings.aws_secret_access_key)


@lru_cache(maxsize=4)
def _client(endpoint: str, key_id: str, secret: str, region: str):
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        region_name=region,
        config=Config(s3={"addressing_style": "path"}, signature_version="s3v4", connect_timeout=5, read_timeout=20, retries={"max_attempts": 2}),
    )


def client(settings: Settings):
    return _client(settings.aws_endpoint_url_s3, settings.aws_access_key_id, settings.aws_secret_access_key.get_secret_value(), settings.aws_region)


def _browsers_allowed(settings: Settings) -> None:
    """The bucket takes uploads from the screens' own address, nobody else's (set once per process)."""
    # The screens' own address (CRM_APP_URL: the one app online) is always one of them, so a
    # customer's order link can upload wherever the screens are served.
    own = urlsplit(settings.crm_app_url) if settings.crm_app_url else None
    here = [f"{own.scheme}://{own.netloc}"] if own and own.scheme and own.netloc else []
    origins = sorted({o.rstrip("/") for o in [*settings.s3_browser_origins, *settings.cors_origins, *here] if o})
    marker = f"{settings.s3_bucket}|{'|'.join(origins)}"
    with _lock:
        if marker in _cors_done:
            return
    try:
        client(settings).put_bucket_cors(
            Bucket=settings.s3_bucket,
            CORSConfiguration={"CORSRules": [{"AllowedOrigins": origins, "AllowedMethods": ["POST"], "AllowedHeaders": ["*"], "MaxAgeSeconds": 3600}]},
        )
        with _lock:
            _cors_done.add(marker)
    except Exception:  # noqa: BLE001 (the upload then fails in the browser, and says so)
        log.exception("Storage: couldn't set the bucket's browser rule.")


def presign_upload(settings: Settings, key: str, content_type: str, max_bytes: int = MAX_BYTES) -> dict:
    """A form the browser posts the file to: this name, this kind, up to max_bytes, for a few minutes."""
    _browsers_allowed(settings)
    form = client(settings).generate_presigned_post(
        settings.s3_bucket,
        key,
        Fields={"Content-Type": content_type},
        Conditions=[{"Content-Type": content_type}, ["content-length-range", 1, max_bytes]],
        ExpiresIn=UPLOAD_SECONDS,
    )
    return {"url": form["url"], "fields": form["fields"], "key": key}


def check(settings: Settings, key: str) -> tuple[str, int]:
    """What's at key: its kind (told by its first bytes) and size. ValueError when it's missing, too big, or not a photo or a PDF."""
    s3 = client(settings)
    try:
        head = s3.head_object(Bucket=settings.s3_bucket, Key=key)
    except Exception as e:  # noqa: BLE001
        raise ValueError("missing") from e
    size = int(head.get("ContentLength") or 0)
    if not 0 < size <= MAX_BYTES:
        raise ValueError("size")
    first = s3.get_object(Bucket=settings.s3_bucket, Key=key, Range="bytes=0-15")["Body"].read()
    kind = next((ct for magic, (ct, _) in KINDS.items() if first.startswith(magic)), None)
    if kind is None:
        raise ValueError("kind")
    return kind, size


def read(settings: Settings, key: str) -> bytes:
    return client(settings).get_object(Bucket=settings.s3_bucket, Key=key)["Body"].read()


def remove(settings: Settings, key: str) -> None:
    try:
        client(settings).delete_object(Bucket=settings.s3_bucket, Key=key)
    except Exception:  # noqa: BLE001
        log.warning("Storage: couldn't remove %s.", key)
