"""A trail's points, packed small: one text value for a whole batch.

Each point is four whole numbers: latitude and longitude in hundred-
thousandths of a degree (about 1.1 m), accuracy in metres (capped at 65,535),
and seconds since the batch started. The first point is kept whole; every
point after it only by how much each number changed, which is small because
consecutive points are close together. Each number is zigzag-encoded (so a
small negative is a small positive), written 7 bits a byte (varint), and the
bytes are base64url text. A point costs about 4-6 bytes instead of about 80
as JSON.

Also the distance between points (haversine), for the day's total and for how
far a visit was from its clinic.
"""

import base64
import math
from dataclasses import dataclass
from datetime import datetime, timedelta

SCALE = 100_000
EARTH_M = 6_371_000


@dataclass(frozen=True)
class Point:
    lat: float
    lng: float
    accuracy_m: int
    at: datetime


def _zigzag(n: int) -> int:
    return (n << 1) ^ (n >> 63) if n < 0 else n << 1


def _unzigzag(n: int) -> int:
    return (n >> 1) ^ -(n & 1)


def _varint(n: int, out: bytearray) -> None:
    while n >= 0x80:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)


def encode(points: list[Point], started_at: datetime) -> str:
    """The points, in order, as one short text value."""
    out = bytearray()
    prev = (0, 0, 0, 0)
    for p in points:
        now = (round(p.lat * SCALE), round(p.lng * SCALE), min(max(p.accuracy_m, 0), 65_535), max(0, round((p.at - started_at).total_seconds())))
        for a, b in zip(now, prev, strict=True):
            _varint(_zigzag(a - b), out)
        prev = now
    return base64.urlsafe_b64encode(bytes(out)).decode().rstrip("=")


def decode(text: str, started_at: datetime) -> list[Point]:
    data = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    numbers: list[int] = []
    n = shift = 0
    for byte in data:
        n |= (byte & 0x7F) << shift
        if byte & 0x80:
            shift += 7
            continue
        numbers.append(_unzigzag(n))
        n = shift = 0
    points, now = [], [0, 0, 0, 0]
    for i in range(0, len(numbers) - len(numbers) % 4, 4):
        now = [a + b for a, b in zip(now, numbers[i : i + 4], strict=True)]
        points.append(Point(now[0] / SCALE, now[1] / SCALE, now[2], started_at + timedelta(seconds=now[3])))
    return points


def metres(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """How far apart two places are, along the ground."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_M * math.asin(math.sqrt(h))


def path_metres(points: list[Point]) -> float:
    return sum(metres(a.lat, a.lng, b.lat, b.lng) for a, b in zip(points, points[1:]))
