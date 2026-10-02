import { useEffect, useState } from "react";

import { PillButton } from "@/components/ab/PillButton";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { api, type AgentCreate, type AgentPatch, type RuleAgent, type RuleItem } from "@/lib/api";
import { formatUsdc } from "@/lib/format";
import { useSettings } from "@/lib/settings";

import { Field, UsdcInput, handleRulesError, inputClass, type FieldErrors } from "./shared";

type Values = {
  agent_id: string;
  description: string;
  allowed_tools: string[];
  per_task_cap: string;
  daily_cap: string;
  approval_above: string;
};

const empty: Values = {
  agent_id: "",
  description: "",
  allowed_tools: [],
  per_task_cap: "",
  daily_cap: "",
  approval_above: "",
};

function fromAgent(agent: RuleAgent): Values {
  return {
    agent_id: agent.agent_id,
    description: agent.description ?? "",
    allowed_tools: [...agent.allowed_tools],
    per_task_cap: agent.per_task_cap,
    daily_cap: agent.daily_cap,
    approval_above: agent.approval_above,
  };
}

const sameNumber = (a: string, b: string) => a.trim() === b.trim() || Number(a) === Number(b);
const sameList = (a: string[], b: string[]) =>
  a.length === b.length && [...a].sort().join("|") === [...b].sort().join("|");

export function AgentForm({
  open,
  onOpenChange,
  agent,
  items,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agent: RuleAgent | null;
  items: RuleItem[];
  onSaved: () => void;
}) {
  const { config } = useSettings();
  const [values, setValues] = useState<Values>(empty);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setValues(agent ? fromAgent(agent) : empty);
      setErrors({});
    }
  }, [open, agent]);

  const set = <K extends keyof Values>(key: K, value: Values[K]) =>
    setValues((current) => ({ ...current, [key]: value }));

  const activeItems = items.filter((item) => item.active);

  async function save() {
    setBusy(true);
    setErrors({});
    try {
      if (agent) {
        const original = fromAgent(agent);
        const patch: AgentPatch = {};
        if (values.description !== original.description) patch.description = values.description;
        if (!sameList(values.allowed_tools, original.allowed_tools))
          patch.allowed_tools = values.allowed_tools;
        if (!sameNumber(values.per_task_cap, original.per_task_cap))
          patch.per_task_cap = values.per_task_cap.trim();
        if (!sameNumber(values.daily_cap, original.daily_cap))
          patch.daily_cap = values.daily_cap.trim();
        if (!sameNumber(values.approval_above, original.approval_above))
          patch.approval_above = values.approval_above.trim();
        if (Object.keys(patch).length > 0) await api.updateAgent(config, agent.agent_id, patch);
      } else {
        const body: AgentCreate = {
          agent_id: values.agent_id.trim(),
          allowed_tools: values.allowed_tools,
          per_task_cap: values.per_task_cap.trim(),
          daily_cap: values.daily_cap.trim(),
          approval_above: values.approval_above.trim(),
        };
        if (values.description.trim()) body.description = values.description.trim();
        await api.createAgent(config, body);
      }
      onSaved();
      onOpenChange(false);
    } catch (error) {
      handleRulesError(error, setErrors);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto bg-[var(--card)] sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="font-display text-2xl">
            {agent ? `Edit ${agent.agent_id}` : "Add agent"}
          </SheetTitle>
          <SheetDescription>Changes apply to the next purchase.</SheetDescription>
        </SheetHeader>
        <form
          className="mt-4 space-y-5 px-4 pb-6"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          {agent ? null : (
            <Field
              id="agent-name"
              label="Name"
              help="Lowercase letters, digits and dashes, e.g. pricing-agent"
              error={errors["agent_id"] ?? errors["name"]}
            >
              <input
                id="agent-name"
                required
                value={values.agent_id}
                onChange={(event) => set("agent_id", event.target.value)}
                className={inputClass}
                autoComplete="off"
              />
            </Field>
          )}
          <Field id="agent-description" label="Description" error={errors["description"]}>
            <textarea
              id="agent-description"
              rows={2}
              value={values.description}
              onChange={(event) => set("description", event.target.value)}
              className={inputClass}
            />
          </Field>
          <fieldset className="space-y-2">
            <legend className="font-semibold">May buy</legend>
            {activeItems.map((item) => {
              const checked = values.allowed_tools.includes(item.tool);
              return (
                <label
                  key={item.tool}
                  className="panel-flat panel-white flex cursor-pointer items-start gap-3 p-3"
                >
                  <input
                    type="checkbox"
                    className="mt-1 size-4"
                    checked={checked}
                    onChange={() =>
                      set(
                        "allowed_tools",
                        checked
                          ? values.allowed_tools.filter((tool) => tool !== item.tool)
                          : [...values.allowed_tools, item.tool],
                      )
                    }
                  />
                  <span className="flex-1">
                    <span className="block font-semibold">{item.name}</span>
                    <span className="text-ink-muted block text-sm">
                      {item.vendor} · <span className="nums">{formatUsdc(item.price)}</span>
                    </span>
                  </span>
                </label>
              );
            })}
            {errors["allowed_tools"] ? (
              <p className="text-blocked-ink text-sm font-semibold" role="alert">
                {errors["allowed_tools"]}
              </p>
            ) : null}
          </fieldset>
          <Field
            id="agent-task"
            label="Task budget (USDC)"
            help="The most one task may spend."
            error={errors["per_task_cap"]}
          >
            <UsdcInput
              id="agent-task"
              value={values.per_task_cap}
              onChange={(v) => set("per_task_cap", v)}
            />
          </Field>
          <Field
            id="agent-daily"
            label="Daily budget (USDC)"
            help="The most this agent may spend per day (UTC). On the test network its wallet is filled with this amount."
            error={errors["daily_cap"]}
          >
            <UsdcInput
              id="agent-daily"
              value={values.daily_cap}
              onChange={(v) => set("daily_cap", v)}
            />
          </Field>
          <Field
            id="agent-approval"
            label="Needs your OK above (USDC)"
            help="Purchases above this wait for you."
            error={errors["approval_above"]}
          >
            <UsdcInput
              id="agent-approval"
              value={values.approval_above}
              onChange={(v) => set("approval_above", v)}
            />
          </Field>
          <div className="flex gap-2">
            <PillButton type="submit" variant="primary" disabled={busy}>
              Save
            </PillButton>
            <PillButton type="button" onClick={() => onOpenChange(false)}>
              Cancel
            </PillButton>
          </div>
        </form>
      </SheetContent>
    </Sheet>
  );
}
