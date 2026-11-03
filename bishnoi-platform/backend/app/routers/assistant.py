"""Authenticated company assistant, streamed through the one app, never a public Ollama proxy."""
import asyncio
import json
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app import assistant
from app.audit import audit
from app.deps import DB, SettingsDep
from app.routers.identity import Signed

router = APIRouter(prefix="/identity/assistant", tags=["company assistant"])


def event(kind, **values):
    return "data: " + json.dumps({"type": kind, **values}, ensure_ascii=True) + "\n\n"


@router.post("/chat")
def chat(body: assistant.ChatIn, request: Request, signed: Signed, db: DB, settings: SettingsDep):
    token = request.headers.get("authorization", "").partition(" ")[2]
    person, company = assistant.member(db, token, settings, body.companyId)
    if not settings.ollama_base_url:
        raise HTTPException(503, "The assistant is not configured. Ask your administrator to set the Platform's OLLAMA_BASE_URL.")
    key = (person.id, company.id)
    assistant.enter(key)
    sessions = request.app.state.sessions
    actor, company_id = person.email, company.id
    today = datetime.now(ZoneInfo(company.timezone)).date().isoformat()

    async def stream():
        outcome, tool = "failed", "intent"
        try:
            yield event("status", message="Understanding your read-only request...")
            async with asyncio.timeout(assistant.TOTAL_TIMEOUT):
                selected = await assistant.plan(body, settings, today)
                tool = selected.tool
                yield event("status", message="Checking access and reading authorized sources...")
                result = await assistant.answer(selected, sessions, token, settings, company_id)
                yield event("sources", items=result.get("sources", []), dateRange=result.get("range"),
                            definitions=result.get("definitions"), retrievedAt=datetime.now(UTC).isoformat())
                # Stream verified template text. Raw model output and reasoning are never sent.
                for line in result["answer"].splitlines(keepends=True):
                    if await request.is_disconnected():
                        outcome = "cancelled"
                        return
                    yield event("text", text=line)
                    await asyncio.sleep(0)
                outcome = "completed"
                yield event("done")
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        except (TimeoutError, httpx.TimeoutException):
            yield event("error", message="The assistant timed out. Try a shorter question in a moment.")
        except HTTPException as error:
            outcome = "denied" if error.status_code in (401, 403, 409) else "failed"
            yield event("error", message=str(error.detail))
        except (httpx.HTTPError, ValueError, TypeError):
            yield event("error", message="The assistant could not reach a valid data source. No answer can be confirmed.")
        except Exception:
            # Never expose upstream responses, credentials, prompts or stack traces.
            yield event("error", message="The assistant could not complete this request. Try again later.")
        finally:
            assistant.leave(key)
            with sessions() as log_db:
                audit(log_db, actor, f"assistant.{outcome}", category="security", company_id=company_id, target=tool,
                      fields=["read-only lookup"])
                log_db.commit()

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
