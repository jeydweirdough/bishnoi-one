"""Errors worded for people, in the shapes the web app turns into form messages
(see orbit-frontend/lib/result.ts): a plain sentence, or a list of
{loc, msg} items that land on the fields they name."""

from fastapi import HTTPException, status

Loc = tuple[str | int, ...]


def invalid(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


def conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def field_errors(errors: list[tuple[Loc, str]]) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        [{"type": "value_error", "loc": ["body", *loc], "msg": message} for loc, message in errors],
    )
