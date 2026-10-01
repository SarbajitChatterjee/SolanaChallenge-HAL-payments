-- Optional: the API creates these tables itself on startup (app/db.py).
-- Run this in the Supabase SQL editor only if you prefer to create them by hand.
-- The tables live in their own schema, which Supabase's Data API (PostgREST) does not expose.

create schema if not exists agentbudget;

create table if not exists agentbudget.agent_state (
  agent_id  varchar(64) primary key,
  frozen    boolean not null default false
);

create table if not exists agentbudget.events (
  id             varchar(24) primary key,
  created_at     timestamptz not null,
  agent_id       varchar(64) not null,
  task_id        varchar(64) not null,
  tool           varchar(64),
  url            text,
  vendor         varchar(128),
  amount_micros  bigint,                 -- USD * 1e6, exact like USDC on-chain
  decision       varchar(8)  not null,   -- allow | hold | deny
  status         varchar(16) not null,   -- reserved | settled | held | blocked | failed | control
  reason         text,                   -- plain-language message for people
  reason_code    varchar(32),            -- stable code for software (paid, not_in_catalog, task_budget, ...)
  tx             varchar(128)
);
create index if not exists ix_events_agent_time on agentbudget.events (agent_id, created_at);
create index if not exists ix_events_agent_task on agentbudget.events (agent_id, task_id);

create table if not exists agentbudget.approvals (
  id             varchar(24) primary key,
  created_at     timestamptz not null,
  agent_id       varchar(64) not null,
  task_id        varchar(64) not null,
  tool           varchar(64) not null,
  vendor         varchar(128),
  amount_micros  bigint not null,
  reason         text,
  status         varchar(16) not null,   -- pending | approved | denied | used
  decided_at     timestamptz
);

create table if not exists agentbudget.early_access (
  email       varchar(254) primary key,   -- lower-cased
  created_at  timestamptz not null,
  role        varchar(16) not null,       -- builder | approver | vendor | curious
  use_case    text,
  consent_at  timestamptz not null
);

-- Belt and braces: even if someone exposes the schema later, anon/authenticated roles get nothing.
alter table agentbudget.agent_state enable row level security;
alter table agentbudget.events      enable row level security;
alter table agentbudget.approvals   enable row level security;
alter table agentbudget.early_access enable row level security;
revoke all on schema agentbudget from anon, authenticated;
