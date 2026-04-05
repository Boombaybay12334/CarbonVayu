import { createClient } from "@supabase/supabase-js";

export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY,
);

/*
Supabase schema reference (see docs/SUPABASE_SCHEMA.md for complete SQL)

create table user_profiles (
  id uuid primary key default gen_random_uuid(),
  firebase_uid text unique not null,
  email text not null,
  role text not null check (role in ('common_man', 'state', 'admin')),
  state_name text,
  state_id uuid references states(id),
  created_at timestamptz default now()
);

create table states (
  id uuid primary key default gen_random_uuid(),
  name text unique not null,
  vt_balance numeric default 0,
  archetype text,
  ecosystem text,
  area_km2 numeric,
  rank integer
);

create table vt_history (
  id uuid primary key default gen_random_uuid(),
  state_id uuid references states(id),
  year integer not null,
  vt_score numeric not null,
  note text
);

create table carbon_relations (
  id uuid primary key default gen_random_uuid(),
  source_state_id uuid references states(id),
  target_state_id uuid references states(id),
  relation_type text,
  vt_impact numeric,
  status text check (status in ('fine_pending', 'gain', 'neutral')),
  period text
);

create table projects (
  id uuid primary key default gen_random_uuid(),
  state_id uuid references states(id),
  title text not null,
  description text,
  vt_gain_estimate numeric,
  funds_needed numeric,
  funds_raised numeric default 0,
  created_at timestamptz default now()
);
*/
