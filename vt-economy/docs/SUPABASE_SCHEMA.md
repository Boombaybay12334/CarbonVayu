# Supabase Schema

## Core Tables

```sql
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

create table user_profiles (
  id uuid primary key default gen_random_uuid(),
  firebase_uid text unique not null,
  email text not null,
  role text not null check (role in ('common_man', 'state', 'admin')),
  state_name text,
  state_id uuid references states(id),
  created_at timestamptz default now()
);
```

## RLS Policies

```sql
alter table user_profiles enable row level security;
alter table states enable row level security;
alter table vt_history enable row level security;
alter table carbon_relations enable row level security;
alter table projects enable row level security;

-- Public read for economy data
create policy "public_read_states" on states for select using (true);
create policy "public_read_vt_history" on vt_history for select using (true);
create policy "public_read_carbon_relations" on carbon_relations for select using (true);
create policy "public_read_projects" on projects for select using (true);

-- User profile access
create policy "profile_self_read" on user_profiles
for select using (firebase_uid = auth.jwt() ->> 'sub');

create policy "profile_self_insert" on user_profiles
for insert with check (firebase_uid = auth.jwt() ->> 'sub');

create policy "profile_self_update" on user_profiles
for update using (firebase_uid = auth.jwt() ->> 'sub');

-- State scoped write protection for vt_history
create policy "state_write_vt_history" on vt_history
for insert with check (
  exists (
    select 1 from user_profiles up
    where up.firebase_uid = auth.jwt() ->> 'sub'
      and up.state_id = vt_history.state_id
      and up.role in ('state', 'admin')
  )
);

create policy "state_update_vt_history" on vt_history
for update using (
  exists (
    select 1 from user_profiles up
    where up.firebase_uid = auth.jwt() ->> 'sub'
      and up.state_id = vt_history.state_id
      and up.role in ('state', 'admin')
  )
);

-- State scoped write protection for carbon_relations
create policy "state_write_relations" on carbon_relations
for insert with check (
  exists (
    select 1 from user_profiles up
    where up.firebase_uid = auth.jwt() ->> 'sub'
      and up.role in ('state', 'admin')
      and (up.state_id = carbon_relations.source_state_id or up.state_id = carbon_relations.target_state_id)
  )
);

create policy "state_update_relations" on carbon_relations
for update using (
  exists (
    select 1 from user_profiles up
    where up.firebase_uid = auth.jwt() ->> 'sub'
      and up.role in ('state', 'admin')
      and (up.state_id = carbon_relations.source_state_id or up.state_id = carbon_relations.target_state_id)
  )
);

-- State scoped write protection for projects
create policy "state_write_projects" on projects
for insert with check (
  exists (
    select 1 from user_profiles up
    where up.firebase_uid = auth.jwt() ->> 'sub'
      and up.role in ('state', 'admin')
      and up.state_id = projects.state_id
  )
);

create policy "state_update_projects" on projects
for update using (
  exists (
    select 1 from user_profiles up
    where up.firebase_uid = auth.jwt() ->> 'sub'
      and up.role in ('state', 'admin')
      and up.state_id = projects.state_id
  )
);
```

## Dummy Seeding (18 states from scaffold)

```sql
insert into states (name, vt_balance, archetype, ecosystem, area_km2, rank) values
('Sikkim', 9420, 'Mountain Carbon Sink', 'Alpine Forest + Glacial', 7096, 1),
('Himachal Pradesh', 8870, 'Forest Buffer', 'Temperate Conifer + River Valley', 55673, 2),
('Arunachal Pradesh', 8210, 'Primary Forest Reserve', 'Tropical + Subtropical Broadleaf', 83743, 3),
('Uttarakhand', 7650, 'Himalayan Watershed', 'Alpine + Mixed Forest', 53483, 4),
('Meghalaya', 7100, 'Rainforest Sink', 'Tropical Moist Broadleaf', 22429, 5),
('Mizoram', 6800, 'Bamboo Forest Zone', 'Mixed Bamboo + Broadleaf', 21081, 6),
('Karnataka', 6340, 'Coastal Carbon Sink', 'Tropical Forest + Coastline', 191791, 7),
('Kerala', 6100, 'Backwater Ecosystem', 'Tropical Moist + Mangrove', 38852, 8),
('Tamil Nadu', 4900, 'Coastal Industrial Mix', 'Tropical Dry + Coastline', 130058, 9),
('Odisha', 4500, 'Transitional Forest', 'Dry Deciduous + Coastal', 155707, 10),
('Rajasthan', 3800, 'Arid Emitter', 'Desert + Scrubland', 342239, 11),
('Madhya Pradesh', 3500, 'Deforested Interior', 'Tropical Dry Deciduous', 308252, 12),
('Uttar Pradesh', 2900, 'Agricultural Emitter', 'Indo-Gangetic Plain', 240928, 13),
('Chhattisgarh', 2750, 'Mining Zone', 'Central Forest + Industrial', 135192, 14),
('Goa', 2300, 'Coastal Tourism Emitter', 'Tropical + Coastal Strip', 3702, 15),
('Haryana', 2100, 'Stubble Burning Zone', 'Semi-Arid Agricultural', 44212, 16),
('Jharkhand', 1580, 'Heavy Industrial', 'Chota Nagpur + Forest', 79716, 17),
('Delhi', 1200, 'Urban Heat Emitter', 'Urban + Peri-urban', 1484, 18);
```
