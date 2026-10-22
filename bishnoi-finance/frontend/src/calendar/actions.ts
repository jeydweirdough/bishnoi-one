"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { CalEvent, CalItem, EventInput } from "./types";

// The calendar's changes (app/routers/calendar.py). The API checks that only the
// owner changes an event, and that it's shared only with people who have a calendar.

export async function saveEvent(id: string | null, input: EventInput): Promise<Result<CalEvent>> {
  return attempt(async () => {
    const saved = id
      ? await api.put<CalEvent>(`/finance/calendar/events/${enc(id)}`, input)
      : await api.post<CalEvent>("/finance/calendar/events", input);
    refresh();
    return saved;
  });
}

export async function deleteEvent(id: string): Promise<Result<null>> {
  return attempt(async () => {
    await api.del(`/finance/calendar/events/${enc(id)}`);
    refresh();
    return null;
  });
}

/** Done (or not) for that date: it stops (or starts again) reminding everyone who sees it. */
export async function setDone(id: string, on: string, done: boolean): Promise<Result<CalItem | null>> {
  return attempt(async () => {
    const out = done
      ? await api.post<CalItem>(`/finance/calendar/events/${enc(id)}/done`, { on })
      : (await api.del(`/finance/calendar/events/${enc(id)}/done?on=${enc(on)}`), null);
    refresh();
    return out;
  });
}
