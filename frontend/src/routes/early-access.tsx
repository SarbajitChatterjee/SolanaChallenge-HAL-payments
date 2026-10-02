import { createFileRoute } from "@tanstack/react-router";
import { CheckCircle2, Loader2 } from "lucide-react";
import { useState } from "react";

import { Panel } from "@/components/ab/Panel";
import { PillButton } from "@/components/ab/PillButton";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, NetworkError, api, type EarlyAccessBody, type EarlyAccessRole } from "@/lib/api";
import { useSettings } from "@/lib/settings";

const TITLE = "Get early access — HAL";
const DESCRIPTION =
  "We're onboarding 10 teams first. Free setup, and we'll connect your agent with you.";

export const Route = createFileRoute("/early-access")({
  staticData: { sitemap: true },
  head: () => ({
    meta: [
      { title: TITLE },
      { name: "description", content: DESCRIPTION },
      { property: "og:title", content: TITLE },
      { property: "og:description", content: DESCRIPTION },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: EarlyAccessPage,
});

const roles: { value: EarlyAccessRole; label: string }[] = [
  { value: "builder", label: "I build AI agents" },
  { value: "approver", label: "I approve software spending" },
  { value: "vendor", label: "I sell an API that agents pay for" },
  { value: "curious", label: "Just curious" },
];

function EarlyAccessPage() {
  const { config } = useSettings();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<EarlyAccessRole>("builder");
  const [useCase, setUseCase] = useState("");
  const [consent, setConsent] = useState(false);
  const [website, setWebsite] = useState("");
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setFieldError(null);
    setFormError(null);

    if (!email.trim()) {
      setFieldError("Please enter your email.");
      return;
    }
    if (!consent) {
      setFormError("Please tick the box so we may email you.");
      return;
    }

    setSending(true);
    try {
      const body: EarlyAccessBody = {
        email: email.trim(),
        role,
        consent: true,
        website: website ? website : "",
      };
      if (useCase.trim()) body.use_case = useCase.trim();
      await api.earlyAccess(config, body);
      setDone(true);
    } catch (error) {
      if (error instanceof NetworkError) {
        setFormError(
          `The browser can't reach the API at ${error.baseUrl}. Check Settings, then try again.`,
        );
      } else if (error instanceof ApiError) {
        if (error.status === 422) setFieldError(error.detail);
        else if (error.status === 429) setFormError("Too many tries. Please wait a minute.");
        else setFormError(error.detail);
      } else {
        setFormError("Something went wrong. Please try again.");
      }
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-12">
      <h1 className="font-display text-4xl">Get early access.</h1>
      <p className="text-ink-muted mt-4">
        We&apos;re onboarding 10 teams first. Free setup, and we&apos;ll connect your agent with
        you.
      </p>

      <Panel tone="yellow" className="mt-8">
        {done ? (
          <p className="panel-text flex items-start gap-2 text-lg font-bold" role="status">
            <CheckCircle2 className="mt-1 size-5 shrink-0" aria-hidden="true" />
            Thanks! We&apos;ll get in touch within a few days.
          </p>
        ) : (
          <form onSubmit={submit} className="space-y-6" noValidate>
            <div className="space-y-1.5">
              <Label htmlFor="email" className="font-semibold">
                Email
              </Label>
              <Input
                id="email"
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="bg-white"
                aria-describedby={fieldError ? "email-error" : undefined}
              />
              {fieldError ? (
                <p id="email-error" className="text-blocked-ink text-sm font-semibold">
                  {fieldError}
                </p>
              ) : null}
            </div>

            <fieldset className="space-y-2">
              <legend className="font-semibold">Which fits you best?</legend>
              <RadioGroup
                value={role}
                onValueChange={(value) => setRole(value as EarlyAccessRole)}
                className="gap-2"
              >
                {roles.map((option) => (
                  <div key={option.value} className="flex items-center gap-2">
                    <RadioGroupItem
                      id={`role-${option.value}`}
                      value={option.value}
                      className="bg-white"
                    />
                    <Label htmlFor={`role-${option.value}`}>{option.label}</Label>
                  </div>
                ))}
              </RadioGroup>
            </fieldset>

            <div className="space-y-1.5">
              <Label htmlFor="use-case" className="font-semibold">
                What should your agent be able to buy?
              </Label>
              <Textarea
                id="use-case"
                value={useCase}
                maxLength={500}
                rows={4}
                onChange={(event) => setUseCase(event.target.value)}
                className="bg-white"
              />
              <p className="text-ink-muted nums text-xs">{useCase.length} of 500 characters</p>
            </div>

            <div className="flex items-start gap-3">
              <Checkbox
                id="consent"
                checked={consent}
                onCheckedChange={(value) => setConsent(value === true)}
                className="mt-1 bg-white"
                required
              />
              <Label htmlFor="consent" className="text-sm leading-relaxed font-normal">
                You may email me about HAL early access. I can ask you to delete my email at
                any time.
              </Label>
            </div>

            <div className="visually-hidden">
              <label htmlFor="website">Website</label>
              <input
                id="website"
                name="website"
                tabIndex={-1}
                autoComplete="off"
                value={website}
                onChange={(event) => setWebsite(event.target.value)}
              />
            </div>

            {formError ? (
              <p
                className="panel-flat panel-blocked panel-text p-3 text-sm font-semibold"
                role="status"
                aria-live="polite"
              >
                {formError}
              </p>
            ) : null}

            <PillButton type="submit" variant="primary" className="bg-white" disabled={sending}>
              {sending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
              Send
            </PillButton>
          </form>
        )}
      </Panel>
    </div>
  );
}
