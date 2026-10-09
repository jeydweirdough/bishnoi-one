"use client";

import { CustomerSharingButton } from "../crm/customer-sharing";
import { Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { Empty, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { createTeam, deleteTeam, updateTeam } from "../../actions/admin";
import type { TeamRow } from "@/src/platform/lib/types";
import { Chip, ChipsInput } from "./chips-input";
import { OffTag } from "./words";

/** Who can be a team's manager: people whose role manages teams. */
export type ManagerOption = { id: string; name: string };

/** Teams: add one, change its name, description, manager or headquarters, switch it off, or delete it while nobody's in it. */
export function TeamsEditor({ teams, managers = [] }: { teams: TeamRow[]; managers?: ManagerOption[] }) {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <AddTeam />
        <CustomerSharingButton />
      </div>
      <Sheet>
        {teams.length === 0 ? (
          <Empty icon="teams" title="No teams yet">
            A team groups people, so a Team Lead's role can reach their team's records.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {teams.map((t) => (
              <TeamLine key={t.id} team={t} managers={managers} />
            ))}
          </ul>
        )}
      </Sheet>
    </div>
  );
}

function AddTeam() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [headquarters, setHeadquarters] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [pending, start] = useTransition();

  function add() {
    start(async () => {
      const result = await createTeam({ name: name.trim(), description: description.trim() || null, headquarters });
      if (!result.ok) {
        setError(result.fields ? null : result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success("Team added", { description: result.data.name });
      setName("");
      setDescription("");
      setHeadquarters([]);
      setError(null);
      setFields({});
      router.refresh();
    });
  }

  return (
    <Sheet className="px-5 pt-4 pb-5">
      <SectionTitle icon="teams">Add a team</SectionTitle>
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          add();
        }}
        className="mt-3 grid gap-4 sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)_auto] sm:items-end"
      >
        <Field label="Name" error={fields.name}>
          {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Field label="What it does" optional error={fields.description}>
          {(p) => <Input {...p} value={description} onChange={(e) => setDescription(e.target.value)} />}
        </Field>
        <div className="sm:order-last sm:col-span-3">
          <ChipsInput label="Headquarters" value={headquarters} onChange={setHeadquarters} placeholder="e.g. Makati office" error={fields.headquarters} />
        </div>
        <Button type="submit" variant="primary" loading={pending} disabled={!name.trim()} icon={<Plus className="size-4" aria-hidden />}>
          Add
        </Button>
      </form>
      {error && (
        <div className="mt-3">
          <FormError message={error} />
        </div>
      )}
    </Sheet>
  );
}

function TeamLine({ team, managers }: { team: TeamRow; managers: ManagerOption[] }) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [managerId, setManagerId] = useState(team.manager?.id ?? "");
  const [name, setName] = useState(team.name);
  const [description, setDescription] = useState(team.description ?? "");
  const [headquarters, setHeadquarters] = useState<string[]>(team.headquarters);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function save() {
    start(async () => {
      const result = await updateTeam(team.id, { name: name.trim(), description: description.trim() || null, headquarters, managerId: managerId || null });
      if (!result.ok) {
        setError(result.fields ? null : result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success("Team saved", { description: result.data.name });
      setEditing(false);
      setFields({});
      setError(null);
      router.refresh();
    });
  }

  async function toggle(): Promise<boolean> {
    const result = await updateTeam(team.id, { isActive: !team.isActive });
    if (!result.ok) {
      toast.error(result.error);
      return false;
    }
    toast.success(team.isActive ? "Team switched off" : "Team switched back on", { description: team.name });
    router.refresh();
    return true;
  }

  async function remove(): Promise<boolean> {
    const result = await deleteTeam(team.id);
    if (!result.ok) {
      toast.error(result.error);
      return false;
    }
    toast.success("Team deleted", { description: team.name });
    router.refresh();
    return true;
  }

  if (editing) {
    return (
      <li className="px-5 py-4">
        <form
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            save();
          }}
          className="grid gap-4 sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)_auto] sm:items-end"
        >
          <Field label="Name" error={fields.name}>
            {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} autoFocus />}
          </Field>
          <Field label="What it does" optional error={fields.description}>
            {(p) => <Input {...p} value={description} onChange={(e) => setDescription(e.target.value)} />}
          </Field>
          <div className="sm:col-span-3">
            <Field
              label="Manager"
              optional
              error={fields.managerId}
              hint={managers.length ? "Above the team lead: reaches this team and every other team they manage." : "Give someone the Manager role first (People and access → Users)."}
            >
              {(p) => (
                <Select {...p} value={managerId} onChange={(e) => setManagerId(e.target.value)} disabled={!managers.length && !managerId}>
                  <option value="">No manager</option>
                  {[...managers, ...(team.manager && !managers.some((m) => m.id === team.manager!.id) ? [team.manager] : [])].map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <div className="sm:order-last sm:col-span-3">
            <ChipsInput label="Headquarters" value={headquarters} onChange={setHeadquarters} placeholder="e.g. Makati office" error={fields.headquarters} />
          </div>
          <span className="flex gap-2">
            <Button
              variant="quiet"
              onClick={() => {
                setEditing(false);
                setName(team.name);
                setDescription(team.description ?? "");
                setHeadquarters(team.headquarters);
                setManagerId(team.manager?.id ?? "");
                setFields({});
                setError(null);
              }}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={pending} disabled={!name.trim()}>
              Save
            </Button>
          </span>
        </form>
        {error && (
          <div className="mt-3">
            <FormError message={error} />
          </div>
        )}
      </li>
    );
  }

  return (
    <li className="grid gap-2 px-5 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
      <div className="min-w-0">
        <p className="flex flex-wrap items-center gap-2 text-sm">
          <span className={`font-semibold ${team.isActive ? "text-ink" : "text-ink-3"}`}>{team.name}</span>
          {!team.isActive && <OffTag />}
        </p>
        <p className="text-meta text-ink-3">
          {team.memberCount === 0 ? (
            "Nobody yet"
          ) : (
            <Link href={`/admin/users?team=${encodeURIComponent(team.id)}`} className="text-ink-2 hover:text-ink hover:underline">
              {team.memberCount} {team.memberCount === 1 ? "person" : "people"}
            </Link>
          )}
          {team.manager && <> · Manager: {team.manager.name}</>}
          {team.description && <> · {team.description}</>}
        </p>
        {team.headquarters.length > 0 && (
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5" aria-label="Headquarters">
            <span className="text-meta text-ink-3">Headquarters</span>
            {team.headquarters.map((h) => (
              <Chip key={h}>{h}</Chip>
            ))}
          </div>
        )}
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Button size="sm" variant="quiet" onClick={() => setEditing(true)}>
          Edit
        </Button>
        <ConfirmButton
          label={team.isActive ? "Switch off" : "Switch on"}
          title={team.isActive ? `Switch ${team.name} off?` : `Switch ${team.name} back on?`}
          body={
            team.isActive
              ? "People already in it stay, but nobody new can be put in it. Switch it back on any time."
              : "People can be put in it again."
          }
          confirmLabel={team.isActive ? "Switch off" : "Switch on"}
          danger={team.isActive}
          triggerSize="sm"
          triggerVariant="quiet"
          onConfirm={toggle}
        />
        {team.memberCount === 0 && (
          <ConfirmButton
            label="Delete"
            title={`Delete ${team.name}?`}
            body="Nobody is in it, so nothing else changes."
            confirmLabel="Delete team"
            triggerSize="sm"
            triggerVariant="quiet"
            onConfirm={remove}
          />
        )}
      </div>
    </li>
  );
}
