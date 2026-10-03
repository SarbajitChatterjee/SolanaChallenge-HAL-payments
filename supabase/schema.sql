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

-- Rules, edited from the dashboard (seeded from app/catalog.json on first start)
create table if not exists agentbudget.agents (
  agent_id               varchar(64) primary key,
  description            text,
  allowed_tools          text not null,         -- JSON list of item ids
  per_task_cap_micros    bigint not null,
  daily_cap_micros       bigint not null,
  approval_above_micros  bigint not null,
  active                 boolean not null,      -- archived agents keep their history
  created_at             timestamptz not null,
  updated_at             timestamptz not null
);

create table if not exists agentbudget.catalog_items (
  tool          varchar(64) primary key,
  name          varchar(80) not null,
  description   text,
  vendor        varchar(128) not null,
  url           text not null,                  -- may contain {vendor_base}
  price_micros  bigint not null,                -- agreed price; payments above it are never signed
  active        boolean not null,
  created_at    timestamptz not null,
  updated_at    timestamptz not null
);

-- Change history: who changed which rule, when, from what to what
create table if not exists agentbudget.audit_log (
  id          varchar(24) primary key,
  created_at  timestamptz not null,
  actor       varchar(32) not null,             -- operator | demo visitor
  action      varchar(64) not null,             -- agent.created, item.updated, demo.reset, ...
  target      varchar(128),
  details     text                              -- JSON: {"field": [old, new]}
);

-- Purchase firewall (feat/7.1). The API also adds these itself on startup.
alter table agentbudget.agents add column if not exists max_repeats integer not null default 2;
alter table agentbudget.agents add column if not exists repeat_window_minutes integer not null default 60;
alter table agentbudget.agents add column if not exists max_attempts_per_min integer not null default 30;
alter table agentbudget.agents add column if not exists velocity_share_10m double precision not null default 0.2;
alter table agentbudget.catalog_items add column if not exists reuse_ttl_seconds integer not null default 0;
alter table agentbudget.catalog_items add column if not exists reuse_scope varchar(8) not null default 'agent';
alter table agentbudget.catalog_items add column if not exists content_policy varchar(16) not null default 'annotate';
alter table agentbudget.catalog_items add column if not exists expect_json text;

-- A seller is identified by its origin (scheme://host)
create table if not exists agentbudget.event_details (
  event_id              varchar(24) primary key,
  agent_id              varchar(64) not null,
  created_at            timestamptz not null,
  fingerprint           varchar(64),            -- SHA-256 of tool + canonical params
  params_json           text,
  quoted_price_micros   bigint,
  caused_by_event_id    varchar(24),
  reused_from_event_id  varchar(24),
  content_flags_json    text,
  delivery_status       varchar(24),
  match_status          varchar(24)
);
create index if not exists ix_event_details_fingerprint on agentbudget.event_details (agent_id, fingerprint, created_at);

create table if not exists agentbudget.purchase_payloads (
  event_id    varchar(24) primary key,
  body_json   text not null,                    -- max 256 KB, only for items with reuse
  expires_at  timestamptz not null
);

create table if not exists agentbudget.content_links (
  id               varchar(24) primary key,
  url_normalized   text not null,
  source_event_id  varchar(24) not null,
  seller_origin    varchar(256) not null,
  agent_id         varchar(64) not null,
  created_at       timestamptz not null
);
create index if not exists ix_content_links_url on agentbudget.content_links (url_normalized);

create table if not exists agentbudget.seller_status (
  seller_origin  varchar(256) primary key,
  status         varchar(16) not null default 'active',   -- active | under_review
  updated_at     timestamptz not null,
  updated_by     varchar(32)
);

create table if not exists agentbudget.seller_incidents (
  id             varchar(24) primary key,
  seller_origin  varchar(256) not null,
  kind           varchar(16) not null,                    -- injection | delivery | overquote
  event_id       varchar(24),
  created_at     timestamptz not null
);
create index if not exists ix_seller_incidents_origin on agentbudget.seller_incidents (seller_origin);

create table if not exists agentbudget.claims (
  id             varchar(24) primary key,
  event_id       varchar(24) not null,
  seller_origin  varchar(256) not null,
  amount_micros  bigint not null,
  status         varchar(16) not null default 'open',
  evidence_json  text,
  created_at     timestamptz not null
);

-- Belt and braces: even if someone exposes the schema later, anon/authenticated roles get nothing.
alter table agentbudget.agent_state enable row level security;
alter table agentbudget.events      enable row level security;
alter table agentbudget.approvals   enable row level security;
alter table agentbudget.early_access enable row level security;
alter table agentbudget.agents        enable row level security;
alter table agentbudget.catalog_items enable row level security;
alter table agentbudget.audit_log     enable row level security;
alter table agentbudget.event_details enable row level security;
alter table agentbudget.purchase_payloads enable row level security;
alter table agentbudget.content_links enable row level security;
alter table agentbudget.seller_status enable row level security;
alter table agentbudget.seller_incidents enable row level security;
alter table agentbudget.claims enable row level security;
revoke all on schema agentbudget from anon, authenticated;