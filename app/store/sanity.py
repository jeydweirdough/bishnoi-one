"""Sanity backend, over Sanity's HTTP API.

The token stays here, server-side. The browser never talks to Sanity, so the
scope rules in Records/Query can't be bypassed by querying Sanity directly,
provided the dataset is private (checked by `dataset_is_public` at startup).
"""

import logging
import time
from collections.abc import Callable, Sequence

import httpx

from app.store.query import Query
from app.store.records import ConflictError, Create, Delete, Mutation, Patch, StoreError

log = logging.getLogger("crm.sanity")

RATE_LIMIT_TRIES = 4
MAX_WAIT_SECONDS = 5.0


def retry_after(response: httpx.Response) -> float:
    """Sanity's Retry-After in seconds, within reason; a second when it doesn't say."""
    try:
        return min(max(float(response.headers.get("retry-after", "1")), 0.1), MAX_WAIT_SECONDS)
    except ValueError:
        return 1.0


class SanityBackend:
    kind = "sanity"

    def __init__(
        self,
        project_id: str,
        dataset: str,
        token: str,
        api_version: str,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._data_url = f"https://{project_id}.api.sanity.io/{api_version}/data"
        self._dataset = dataset
        self._client = client or httpx.Client(timeout=15.0)
        self._headers = {"Authorization": f"Bearer {token}"}
        self._sleep = sleep

    def _request(self, path: str, *, params: dict, body: dict) -> dict:
        url = f"{self._data_url}/{path}/{self._dataset}"
        for attempt in range(RATE_LIMIT_TRIES):
            try:
                response = self._client.post(url, params=params, json=body, headers=self._headers)
            except httpx.HTTPError as exc:
                log.error("sanity unreachable: %s", exc)
                raise StoreError("Sanity is unreachable") from exc
            # Over Sanity's rate limit: nothing was done, so wait as told and ask again.
            if response.status_code != 429 or attempt == RATE_LIMIT_TRIES - 1:
                break
            wait = retry_after(response)
            log.warning("sanity rate limit on %s; waiting %.1fs", path, wait)
            self._sleep(wait)
        if response.status_code == 409:
            raise ConflictError(_error_text(response))
        if response.status_code >= 400:
            log.error("sanity %s %s: %s", path, response.status_code, _error_text(response))
            raise StoreError(f"Sanity returned {response.status_code}")
        return response.json()

    def fetch(self, query: Query) -> list[dict]:
        text, params = query.groq()
        body = self._request("query", params={"perspective": "published"}, body={"query": text, "params": params})
        return body.get("result") or []

    def count(self, query: Query) -> int:
        text, params = query.groq_count()
        body = self._request("query", params={"perspective": "published"}, body={"query": text, "params": params})
        return int(body.get("result") or 0)

    def owners(self, ids: Sequence[str]) -> dict[str, str | None]:
        body = self._request(
            "query",
            params={"perspective": "published"},
            body={"query": "*[_id in $ids]{_id, orgId}", "params": {"ids": list(ids)}},
        )
        return {d["_id"]: d.get("orgId") for d in body.get("result") or []}

    def without_org(self, limit: int) -> list[str]:
        """Ids of records not yet stamped with a company (tools/restamp.py)."""
        body = self._request(
            "query",
            params={"perspective": "published"},
            body={"query": "*[defined(scopeKey) && !defined(orgId)][0...$n]._id", "params": {"n": limit}},
        )
        return list(body.get("result") or [])

    def commit(self, mutations: Sequence[Mutation]) -> None:
        body = {"mutations": [_encode(m) for m in mutations]}
        self._request("mutate", params={"visibility": "sync", "returnIds": "false"}, body=body)

    def dataset_is_public(self) -> bool | None:
        """True if anyone can read the dataset without a token; None if we can't tell."""
        url = f"{self._data_url}/query/{self._dataset}"
        try:
            response = httpx.get(url, params={"query": "count(*[0...1])"}, timeout=10.0)
        except httpx.HTTPError:
            return None
        if response.status_code == 200:
            return True
        if response.status_code in (401, 403):
            return False
        return None


def _encode(m: Mutation) -> dict:
    if isinstance(m, Create):
        return {"create": m.doc}
    if isinstance(m, Patch):
        patch: dict = {"id": m.id}
        if m.set:
            patch["set"] = m.set
        if m.unset:
            patch["unset"] = list(m.unset)
        if m.if_revision:
            patch["ifRevisionID"] = m.if_revision
        return {"patch": patch}
    if isinstance(m, Delete):
        return {"delete": {"id": m.id}}
    raise TypeError(m)


def _error_text(response: httpx.Response) -> str:
    try:
        error = response.json().get("error")
    except ValueError:
        return response.text[:300]
    if isinstance(error, dict):
        return str(error.get("description") or error.get("type") or error)[:300]
    return str(error)[:300]
