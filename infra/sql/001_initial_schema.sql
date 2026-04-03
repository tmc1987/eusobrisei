-- CONTRATO_DE_PLATAFORMA_V1 - Esquema inicial
-- Banco alvo sugerido: PostgreSQL 15+

create extension if not exists pgcrypto;

create table tenants (
  tenant_id uuid primary key default gen_random_uuid(),
  name varchar(120) not null,
  status varchar(20) not null default 'active',
  created_at timestamptz not null default now()
);

create table device_groups (
  group_id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(tenant_id),
  name varchar(120) not null,
  profile varchar(64),
  created_at timestamptz not null default now()
);

create table devices (
  device_id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(tenant_id),
  group_id uuid references device_groups(group_id),
  hostname varchar(128) not null,
  os_version varchar(128),
  last_seen_at timestamptz,
  created_at timestamptz not null default now()
);

create table agents (
  agent_id uuid primary key default gen_random_uuid(),
  device_id uuid not null references devices(device_id),
  tenant_id uuid not null references tenants(tenant_id),
  agent_version varchar(32) not null,
  auth_status varchar(20) not null default 'active',
  cert_thumbprint varchar(128),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table policies (
  policy_id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(tenant_id),
  group_id uuid references device_groups(group_id),
  device_id uuid references devices(device_id),
  version varchar(64) not null,
  document jsonb not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  unique(tenant_id, group_id, device_id, version)
);

create table events (
  event_id uuid primary key,
  tenant_id uuid not null references tenants(tenant_id),
  device_id uuid not null references devices(device_id),
  agent_id uuid not null references agents(agent_id),
  event_type varchar(40) not null,
  severity varchar(4) not null,
  occurred_at timestamptz not null,
  context jsonb not null,
  policy_version varchar(64),
  received_at timestamptz not null default now()
);

create table action_audit (
  action_id uuid primary key,
  tenant_id uuid not null references tenants(tenant_id),
  device_id uuid not null references devices(device_id),
  agent_id uuid not null references agents(agent_id),
  trigger_event_id uuid,
  action_name varchar(64) not null,
  reason text,
  risk_level varchar(20) not null,
  pre_state jsonb,
  post_state jsonb,
  rollback_possible boolean not null,
  rollback_executed boolean,
  execution_status varchar(20) not null,
  error_message text,
  policy_version varchar(64),
  occurred_at timestamptz not null,
  received_at timestamptz not null default now()
);

create table idempotency_keys (
  key varchar(128) primary key,
  agent_id uuid not null references agents(agent_id),
  request_hash varchar(128) not null,
  first_seen_at timestamptz not null default now(),
  expires_at timestamptz not null
);

create index idx_events_tenant_device_time on events (tenant_id, device_id, occurred_at desc);
create index idx_audit_tenant_device_time on action_audit (tenant_id, device_id, occurred_at desc);
create index idx_policies_scope_active on policies (tenant_id, group_id, device_id, is_active);
