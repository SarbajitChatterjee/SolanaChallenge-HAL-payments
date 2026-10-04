import { Link, createFileRoute } from "@tanstack/react-router";
import {
  AlertTriangle,
  CreditCard,
  FileText,
  Gauge,
  Hand,
  ListChecks,
  Power,
  RotateCcw,
  ShieldCheck,
  Tag,
  Wallet,
} from "lucide-react";

import { Panel, PanelTitle } from "@/components/ab/Panel";
import { pillClass } from "@/components/ab/PillButton";
import { CostCalculator } from "@/components/home/CostCalculator";
import { ARCHITECTURE_IMAGE_URL } from "@/config";
import { useEarlyAccessCount } from "@/lib/queries";

const TITLE = "HAL — a spending account for AI agents";
const DESCRIPTION =
  "Let AI agents buy the data they need, within your rules. Small purchases go through on their own. Big ones wait for you. Wrong ones are blocked.";

export const Route = createFileRoute("/")({
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
  component: Home,
});

const todayCards = [
  {
    title: "Give it a credit card.",
    body: "Cards can't handle 5-cent payments, and nothing stops the agent from spending more.",
    icon: CreditCard,
  },
  {
    title: "Give it a wallet with money.",
    body: "It can pay anyone, instantly. If it gets tricked or stuck in a loop, the wallet empties.",
    icon: Wallet,
  },
  {
    title: "Approve every purchase by hand.",
    body: "Safe, but then it's not an agent anymore.",
    icon: Hand,
  },
];

const steps = [
  "The agent asks to buy.",
  "HAL checks your rules.",
  "It pays the seller in USDC on Solana.",
  "The receipt goes into your ledger.",
];

const safeguards = [
  {
    title: "Response firewall",
    body: "Removes instructions aimed at agents before your agent reads the answer.",
    icon: ShieldCheck,
  },
  {
    title: "Trap traced to its seller",
    body: "A bad link is traced back, and that seller goes under review.",
    icon: AlertTriangle,
  },
  {
    title: "Loops stopped",
    body: "Paid once, reused after, then frozen if the agent keeps going.",
    icon: RotateCcw,
  },
];

const controls = [
  { title: "Approved sellers", body: "Only sellers on your list can be paid.", icon: ListChecks },
  { title: "Agreed prices", body: "If a seller asks for more, nothing is paid.", icon: Tag },
  { title: "Budgets", body: "Per task and per day.", icon: Gauge },
  { title: "Your OK above a limit", body: "Big purchases wait for you.", icon: Hand },
  { title: "Kill switch", body: "Stops one agent instantly.", icon: Power },
  {
    title: "Receipts",
    body: "Every payment has a Solana receipt and goes into an export for your accountant.",
    icon: FileText,
  },
];

function Section({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <section className={`mx-auto max-w-6xl px-4 py-12 sm:py-16 ${className ?? ""}`}>
      {children}
    </section>
  );
}

function Home() {
  const count = useEarlyAccessCount();
  const signups = count.data?.count ?? 0;

  return (
    <div>
      <Section className="pb-6 sm:pb-8">
        <div className="max-w-3xl">
          <h1 className="font-display text-4xl leading-tight sm:text-5xl">
            Let AI agents buy what they need. Within your rules.
          </h1>
          <p className="text-ink-muted mt-5 text-lg">
            The purchase firewall for AI agents. HAL checks what was ordered, what was paid, and
            what came back.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Link to="/demo" search={{ tour: "1" }} className={pillClass("primary")}>
              Take the 3-minute tour
            </Link>
            <Link to="/early-access" className={pillClass()}>
              Get early access
            </Link>
          </div>
        </div>
      </Section>

      <Section>
        <h2 className="font-display text-3xl">Agents can pay now. Nobody can safely let them.</h2>
        <p className="text-ink-muted mt-4 max-w-3xl">
          An agent that checks a new supplier needs a company record, an exchange rate, recent news
          and maybe a credit report. Each costs between 1 and 50 cents, from a different seller.
        </p>
        <div className="mt-8 grid gap-6 md:grid-cols-3">
          {todayCards.map((card) => (
            <Panel key={card.title} tone="blocked">
              <p className="panel-text text-xs font-bold">Today you can...</p>
              <card.icon className="panel-text mt-3 size-6" aria-hidden="true" />
              <PanelTitle className="mt-2">{card.title}</PanelTitle>
              <p className="mt-2 text-sm">{card.body}</p>
            </Panel>
          ))}
        </div>
      </Section>

      <Section>
        <h2 className="font-display text-3xl">
          Built first for teams whose agents already pay per request.
        </h2>
        <div className="mt-8 grid gap-6 md:grid-cols-2">
          <Panel tone="sky">
            <PanelTitle>You build the agent</PanelTitle>
            <p className="mt-2">
              Your agent buys data per request and holds its own wallet. You want limits without
              writing them yourself.
            </p>
            <Link to="/connect" className={pillClass("neutral", "mt-5")}>
              Connect your agent
            </Link>
          </Panel>
          <Panel tone="pink">
            <PanelTitle>You approve the spending</PanelTitle>
            <p className="mt-2">
              You want small purchases to just happen, the big ones to come to you, and a record
              your accountant can use.
            </p>
            <Link to="/demo" search={{ tour: "1" }} className={pillClass("neutral", "mt-5")}>
              Try the live demo
            </Link>
          </Panel>
        </div>
      </Section>

      <Section>
        <h2 className="font-display text-3xl">One question before every purchase.</h2>
        <Panel tone="yellow" flat className="mt-8 overflow-hidden p-2 sm:p-3">
          <img
            src={ARCHITECTURE_IMAGE_URL}
            alt="How a purchase flows through HAL"
            loading="lazy"
            className="block w-full bg-card"
          />
        </Panel>
        <ol className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((step, index) => (
            <li key={step} className="panel panel-white flex gap-3 p-5">
              <span className="panel-flat panel-yellow panel-text nums grid size-9 shrink-0 place-items-center font-bold">
                {index + 1}
              </span>
              <span className="font-semibold">{step}</span>
            </li>
          ))}
        </ol>
      </Section>

      <Section>
        <h2 className="font-display text-3xl">Why this only works on Solana.</h2>
        <ul className="mt-6 grid gap-4 md:grid-cols-3">
          {[
            "Payments of a few cents cost a fraction of a cent.",
            "Sellers don't need an account for your agent: it just pays.",
            "The agent's wallet only holds its budget, so it can't spend more, even if software fails.",
          ].map((point) => (
            <li key={point} className="panel-flat panel-purple panel-text p-4 font-semibold">
              {point}
            </li>
          ))}
        </ul>
        <div className="mt-8">
          <CostCalculator />
        </div>
      </Section>

      <Section>
        <h2 className="font-display text-3xl">What you control.</h2>
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          {safeguards.map((item) => (
            <Panel key={item.title} tone="mint">
              <item.icon className="panel-text size-6" aria-hidden="true" />
              <PanelTitle className="mt-2">{item.title}</PanelTitle>
              <p className="mt-1.5 text-sm">{item.body}</p>
            </Panel>
          ))}
        </div>
        <ul className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {controls.map((control) => (
            <li key={control.title} className="panel-flat panel-white flex gap-3 p-3">
              <control.icon className="size-5 shrink-0" aria-hidden="true" />
              <span className="text-sm">
                <strong>{control.title}.</strong> {control.body}
              </span>
            </li>
          ))}
        </ul>
      </Section>

      <Section>
        <Panel tone="yellow" className="text-center">
          <h2 className="panel-text font-display text-3xl">
            We&apos;re looking for our first 10 teams.
          </h2>
          <p className="mt-3">
            Free setup, and we connect your agent with you in a 30-minute call.
          </p>
          {signups >= 10 ? (
            <p className="nums mt-2 font-semibold">{signups} teams have signed up.</p>
          ) : null}
          <div className="mt-6 flex justify-center">
            <Link to="/early-access" className={pillClass("primary", "bg-white")}>
              Get early access
            </Link>
          </div>
        </Panel>
      </Section>

      <div className="flex justify-center pb-8">
        <span
          className="h-1.5 w-40 rounded-sm bg-gradient-to-r from-purple-line to-mint-line"
          aria-hidden="true"
        />
      </div>
    </div>
  );
}
