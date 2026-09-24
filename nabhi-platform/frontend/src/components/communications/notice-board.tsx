"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Choice, Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { Empty, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { addNotice, deleteNotice, updateNotice, type NoticeInput } from "../../actions/platform";
import { NOTICE_KINDS } from "../../lib/words";
import type { Notice, NoticeKind, NoticeLevel, Options } from "../../lib/types";
import { NOTICE_LEVELS, NoticeLevelMark, NoticeStateMark, audience, noticeWindow } from "./notice-words";

// One kind of notice: the list, and for a Platform Admin, writing one and
// publishing, withdrawing, changing or deleting each, on its own row.

type Pickers = { companies: Options["companies"]; applications: Options["applications"] };

const EMPTY_WORDS: Record<NoticeKind, string> = {
  announcement: "News for the people using the applications: a new feature, a change in how something works.",
  notification: "Something the platform itself needs people to know: a problem being worked on, a change they must make.",
  maintenance: "When an application will be down or slow for planned work, say so here ahead of time, with the window.",
};

/** "2026-09-24T10:00" in the browser's zone, for a datetime-local input. */
function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** A datetime-local value as ISO with the browser's offset: "2026-09-24T10:00:00+08:00". */
function toIso(local: string): string | null {
  if (!local) return null;
  const d = new Date(local);
  if (Number.isNaN(d.getTime())) return null;
  const offset = -d.getTimezoneOffset();
  const pad = (n: number) => String(Math.floor(Math.abs(n))).padStart(2, "0");
  return `${local.length === 16 ? `${local}:00` : local}${offset >= 0 ? "+" : "-"}${pad(offset / 60)}:${pad(offset % 60)}`;
}

export function NoticeBoard({
  kind,
  notices,
  companies,
  applications,
  canAdminister,
}: { kind: NoticeKind; notices: Notice[]; canAdminister: boolean } & Pickers) {
  const [writing, setWriting] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const words = NOTICE_KINDS[kind];

  return (
    <>
      {canAdminister ? (
        !writing && (
          <div className="mb-4">
            <Button variant="primary" onClick={() => setWriting(true)}>
              Write a {words.one.toLowerCase()}
            </Button>
          </div>
        )
      ) : (
        <p className="mb-4 text-meta text-ink-3">Only a Platform Admin writes, publishes and withdraws notices. You can read them all here.</p>
      )}

      {writing && (
        <Sheet className="mb-5 px-5 pt-4 pb-5">
          <SectionTitle icon="communications">Write a notice</SectionTitle>
          <NoticeForm kind={kind} companies={companies} applications={applications} onDone={() => setWriting(false)} />
        </Sheet>
      )}

      <Sheet className="px-5 pt-2 pb-2">
        {notices.length === 0 ? (
          <Empty title={`No ${words.many.toLowerCase()} yet`} icon="communications">
            {EMPTY_WORDS[kind]} {canAdminister ? `Use “Write a ${words.one.toLowerCase()}” above.` : "A Platform Admin writes them."}
          </Empty>
        ) : (
          <ul className="divide-y divide-rule" role="list">
            {notices.map((n) =>
              editing === n.id ? (
                <li key={n.id} className="py-4">
                  <p className="mb-2 text-sm font-semibold text-ink">Changing “{n.title}”</p>
                  <NoticeForm
                    kind={n.kind}
                    notice={n}
                    companies={companies}
                    applications={applications}
                    onDone={() => setEditing(null)}
                  />
                </li>
              ) : (
                <NoticeRow key={n.id} notice={n} canAdminister={canAdminister} onEdit={() => setEditing(n.id)} />
              ),
            )}
          </ul>
        )}
      </Sheet>
    </>
  );
}

function NoticeRow({ notice: n, canAdminister, onEdit }: { notice: Notice; canAdminister: boolean; onEdit: () => void }) {
  const [pending, start] = useTransition();
  const published = n.publishedAt !== null;

  function togglePublished() {
    start(async () => {
      const r = await updateNotice(n.id, { publish: !published });
      if (!r.ok) return void toast.error(r.error);
      toast.success(published ? "Withdrawn" : "Published", {
        description: published ? "It's a draft again; the applications stop showing it." : "The applications show it from its start.",
      });
    });
  }

  return (
    <li className="py-3.5">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <NoticeStateMark state={n.state} />
            <NoticeLevelMark level={n.level} />
          </p>
          <h3 className="mt-1 text-sm font-semibold text-ink">{n.title}</h3>
          {n.body && <p className="mt-0.5 line-clamp-3 text-sm whitespace-pre-line text-ink-2">{n.body}</p>}
          <p className="mt-1 text-meta text-ink-3">
            For {audience(n).replace(/^Everyone/, "everyone")} · {noticeWindow(n)} · written by {n.createdBy}
          </p>
        </div>
        {canAdminister && (
          <div className="flex flex-wrap items-center gap-1">
            {n.state !== "ended" && (
              <Button size="sm" variant={published ? "default" : "primary"} loading={pending} onClick={togglePublished}>
                {published ? "Withdraw this notice" : "Publish this notice"}
              </Button>
            )}
            <Button size="sm" variant="quiet" onClick={onEdit}>
              Edit this notice
            </Button>
            <ConfirmButton
              label="Delete this notice"
              triggerVariant="quiet"
              triggerSize="sm"
              title={`Delete “${n.title}”?`}
              body={
                n.state === "showing"
                  ? "It's showing now: the applications stop showing it straight away, and it can't be brought back. To take it down for now, withdraw it instead."
                  : "It's gone for good and can't be brought back. The activity log keeps a line saying you deleted it."
              }
              confirmLabel="Delete it"
              onConfirm={async () => {
                const r = await deleteNotice(n.id);
                if (!r.ok) {
                  toast.error(r.error);
                  return false;
                }
                toast.success("Notice deleted");
              }}
            />
          </div>
        )}
      </div>
    </li>
  );
}

function NoticeForm({ kind: initialKind, notice, companies, applications, onDone }: { kind: NoticeKind; notice?: Notice; onDone: () => void } & Pickers) {
  const [pending, start] = useTransition();
  const [kind, setKind] = useState<NoticeKind>(initialKind);
  const [level, setLevel] = useState<NoticeLevel>(notice?.level ?? (initialKind === "maintenance" ? "warning" : "info"));
  const [v, setV] = useState({
    title: notice?.title ?? "",
    body: notice?.body ?? "",
    companyId: notice?.company?.id ?? "",
    applicationId: notice?.application?.id ?? "",
    startsAt: toLocalInput(notice?.startsAt ?? null),
    endsAt: toLocalInput(notice?.endsAt ?? null),
  });
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value });
  const maintenance = kind === "maintenance";

  function save(publish?: boolean) {
    const problems: Record<string, string> = {};
    if (v.title.trim().length < 3) problems.title = "Give it a title of at least 3 characters.";
    if (maintenance && !v.startsAt) problems.startsAt = "A maintenance notice needs its start.";
    if (maintenance && !v.endsAt) problems.endsAt = "A maintenance notice needs its end.";
    if (v.startsAt && v.endsAt && v.endsAt <= v.startsAt) problems.endsAt = "It has to end after it starts.";
    if (Object.keys(problems).length) {
      setError(null);
      return setFields(problems);
    }
    const common = {
      level,
      title: v.title.trim(),
      body: v.body.trim() || null,
      companyId: v.companyId || null,
      applicationId: v.applicationId || null,
      endsAt: toIso(v.endsAt),
    };
    start(async () => {
      const r = notice
        ? // A start left blank keeps the one it has; the API won't take an empty one.
          await updateNotice(notice.id, { ...common, ...(v.startsAt ? { startsAt: toIso(v.startsAt) } : {}) })
        : await addNotice({ ...common, kind, startsAt: toIso(v.startsAt), publish: publish ?? false } satisfies NoticeInput);
      if (!r.ok) {
        setError(r.fields && Object.keys(r.fields).length ? null : r.error);
        setFields(r.fields ?? {});
        return;
      }
      const elsewhere = !notice && kind !== initialKind ? ` It's under ${NOTICE_KINDS[kind].many}.` : "";
      toast.success(notice ? "Notice saved" : publish ? "Published" : "Saved as a draft", {
        description: notice
          ? undefined
          : (publish ? "The applications show it from its start." : "Nobody sees it until you publish it.") + elsewhere,
      });
      onDone();
    });
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        save(notice ? undefined : true);
      }}
      className="mt-3 grid gap-5 sm:grid-cols-2"
    >
      {!notice && (
        <div className="sm:col-span-2">
          <Choice
            name="kind"
            legend="Kind"
            value={kind}
            onChange={setKind}
            options={(Object.keys(NOTICE_KINDS) as NoticeKind[]).map((k) => ({ value: k, label: NOTICE_KINDS[k].one }))}
          />
        </div>
      )}
      <div className="sm:col-span-2">
        <Choice
          name="level"
          legend="How serious"
          value={level}
          onChange={setLevel}
          options={(Object.keys(NOTICE_LEVELS) as NoticeLevel[]).map((l) => ({ value: l, label: NOTICE_LEVELS[l] }))}
        />
        {fields.level && <p className="mt-1 text-meta text-danger">{fields.level}</p>}
      </div>
      <Field label="Title" error={fields.title} className="sm:col-span-2">
        {(p) => <Input {...p} value={v.title} onChange={set("title")} maxLength={200} />}
      </Field>
      <Field label="What it says" optional error={fields.body} className="sm:col-span-2" hint="Plain words: what's happening, who it affects, what to do.">
        {(p) => <Textarea {...p} rows={4} value={v.body} onChange={set("body")} maxLength={10000} />}
      </Field>
      <Field label="Company" error={fields.companyId} hint="Leave it on every company to tell everyone.">
        {(p) => (
          <Select {...p} value={v.companyId} onChange={set("companyId")}>
            <option value="">Every company</option>
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {c.status === "suspended" ? " (suspended)" : ""}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field label="Application" error={fields.applicationId} hint="Only that application's users see it.">
        {(p) => (
          <Select {...p} value={v.applicationId} onChange={set("applicationId")}>
            <option value="">Every application</option>
            {applications.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field
        label="Starts"
        optional={!maintenance}
        error={fields.startsAt}
        hint={maintenance ? "When the work begins. Your computer's time zone." : notice ? "Your computer's time zone." : "Blank: as soon as it's published. Your computer's time zone."}
      >
        {(p) => <Input {...p} type="datetime-local" value={v.startsAt} onChange={set("startsAt")} />}
      </Field>
      <Field
        label="Ends"
        optional={!maintenance}
        error={fields.endsAt}
        hint={maintenance ? "When the work should be over." : "Blank: it shows until it's withdrawn."}
      >
        {(p) => <Input {...p} type="datetime-local" value={v.endsAt} onChange={set("endsAt")} />}
      </Field>

      <div className="sm:col-span-2">
        <FormError message={error} />
        <div className="mt-2 flex flex-wrap gap-2">
          {notice ? (
            <Button type="submit" variant="primary" loading={pending}>
              Save changes
            </Button>
          ) : (
            <>
              <Button type="submit" variant="primary" loading={pending}>
                Publish now
              </Button>
              <Button onClick={() => save(false)} disabled={pending}>
                Save as draft
              </Button>
            </>
          )}
          <Button variant="quiet" onClick={onDone} disabled={pending}>
            Cancel
          </Button>
        </div>
      </div>
    </form>
  );
}
