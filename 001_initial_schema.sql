-- CivicPulse Supabase Database Schema
-- Run this in Supabase SQL Editor or via supabase db push

-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- Departments table
create table if not exists departments (
    id uuid primary key default uuid_generate_v4(),
    code text unique not null,
    name text not null,
    default_sla_hours integer not null,
    created_at timestamptz default now()
);

-- Wards table
create table if not exists wards (
    id uuid primary key default uuid_generate_v4(),
    ward_number integer unique not null,
    ward_name text not null,
    zone_name text,
    created_at timestamptz default now()
);

-- Officials table (municipal users)
create table if not exists officials (
    id uuid primary key default uuid_generate_v4(),
    auth_user_id uuid unique, -- Links to Supabase Auth
    email text unique not null,
    full_name text not null,
    role text not null check (role in ('FIELD_OFFICER', 'SUPERVISOR', 'COMMISSIONER')),
    department_id uuid references departments(id),
    ward_id uuid references wards(id),
    password_hash text not null,
    created_at timestamptz default now()
);

-- Tickets table
create table if not exists tickets (
    id uuid primary key default uuid_generate_v4(),
    ticket_number text unique not null,
    tracking_pin_hash text not null,
    description text not null,
    translated_description text,
    category text not null,
    subcategory text,
    department_id uuid references departments(id),
    department_code text not null,
    ward_id uuid references wards(id),
    priority text not null check (priority in ('LOW', 'MEDIUM', 'HIGH', 'URGENT', 'CRITICAL')),
    status text not null check (status in ('SUBMITTED', 'ASSIGNED', 'IN_PROGRESS', 'RESOLUTION_SUBMITTED', 'RESOLVED', 'BREACHED', 'REOPENED')),
    latitude numeric,
    longitude numeric,
    landmark text,
    address text,
    before_photo_url text,
    after_photo_url text,
    assigned_officer_id uuid references officials(id),
    sla_hours integer not null,
    sla_deadline timestamptz not null,
    created_at timestamptz default now(),
    assigned_at timestamptz,
    started_at timestamptz,
    resolved_at timestamptz,
    closing_notes text,
    duplicate_of uuid references tickets(id),
    impact_count integer default 1,
    reopen_until timestamptz
);

-- Timeline events table
create table if not exists timeline_events (
    id uuid primary key default uuid_generate_v4(),
    ticket_id uuid not null references tickets(id) on delete cascade,
    at timestamptz default now(),
    label text not null,
    detail text not null,
    actor_id uuid references officials(id)
);

-- Indexes for performance
create index if not exists idx_tickets_department_code on tickets(department_code);
create index if not exists idx_tickets_status on tickets(status);
create index if not exists idx_tickets_assigned_officer on tickets(assigned_officer_id);
create index if not exists idx_tickets_created_at on tickets(created_at desc);
create index if not exists idx_tickets_sla_deadline on tickets(sla_deadline);
create index if not exists idx_timeline_events_ticket_id on timeline_events(ticket_id);
create index if not exists idx_officials_email on officials(email);

-- Seed departments
insert into departments (code, name, default_sla_hours) values
    ('ROADS', 'Roads', 48),
    ('WATER', 'Water', 24),
    ('SOLID_WASTE', 'Solid Waste', 24),
    ('ELECTRICAL', 'Electrical', 12),
    ('PUBLIC_HEALTH', 'Public Health', 72)
on conflict (code) do nothing;

-- Seed wards
insert into wards (ward_number, ward_name, zone_name) values
    (1, 'Central Ward', 'Zone A'),
    (2, 'North Ward', 'Zone A'),
    (3, 'South Ward', 'Zone B'),
    (4, 'East Ward', 'Zone B'),
    (5, 'West Ward', 'Zone C')
on conflict (ward_number) do nothing;

-- Enable RLS
alter table departments enable row level security;
alter table wards enable row level security;
alter table officials enable row level security;
alter table tickets enable row level security;
alter table timeline_events enable row level security;

-- RLS Policies

-- Departments: readable by authenticated users
create policy "departments_read_authenticated" on departments
    for select to authenticated using (true);

-- Wards: readable by authenticated users
create policy "wards_read_authenticated" on wards
    for select to authenticated using (true);

-- Officials: users can read their own profile
create policy "officials_read_own" on officials
    for select to authenticated using (auth_user_id = auth.uid());

-- Officials: supervisors/commissioners can read all
create policy "officials_read_all_supervisor" on officials
    for select to authenticated using (
        exists (
            select 1 from officials o
            where o.auth_user_id = auth.uid()
            and o.role in ('SUPERVISOR', 'COMMISSIONER')
        )
    );

-- Tickets: public tracking via ticket_number + PIN (handled by backend, not direct DB access)
-- Officials: field officers see assigned or ward tickets
create policy "tickets_read_field_officer" on tickets
    for select to authenticated using (
        exists (
            select 1 from officials o
            where o.auth_user_id = auth.uid()
            and o.role = 'FIELD_OFFICER'
            and (tickets.assigned_officer_id = o.id or tickets.ward_id = o.ward_id)
        )
    );

-- Officials: supervisors/commissioners see all
create policy "tickets_read_supervisor" on tickets
    for select to authenticated using (
        exists (
            select 1 from officials o
            where o.auth_user_id = auth.uid()
            and o.role in ('SUPERVISOR', 'COMMISSIONER')
        )
    );

-- Officials: field officers can update assigned tickets
create policy "tickets_update_field_officer" on tickets
    for update to authenticated using (
        exists (
            select 1 from officials o
            where o.auth_user_id = auth.uid()
            and o.role = 'FIELD_OFFICER'
            and tickets.assigned_officer_id = o.id
        )
    );

-- Officials: supervisors/commissioners can update all
create policy "tickets_update_supervisor" on tickets
    for update to authenticated using (
        exists (
            select 1 from officials o
            where o.auth_user_id = auth.uid()
            and o.role in ('SUPERVISOR', 'COMMISSIONER')
        )
    );

-- Timeline events: readable with ticket access
create policy "timeline_read_with_ticket" on timeline_events
    for select to authenticated using (
        exists (
            select 1 from tickets t
            where t.id = timeline_events.ticket_id
            and (
                exists (
                    select 1 from officials o
                    where o.auth_user_id = auth.uid()
                    and (o.role in ('SUPERVISOR', 'COMMISSIONER') 
                        or (o.role = 'FIELD_OFFICER' and (t.assigned_officer_id = o.id or t.ward_id = o.ward_id)))
                )
            )
        )
    );

-- Storage bucket for ticket photos
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('tickets', 'tickets', true, 5242880, array['image/jpeg', 'image/png'])
on conflict (id) do nothing;

-- Storage policies
create policy "tickets_public_read" on storage.objects
    for select using (bucket_id = 'tickets');

create policy "tickets_authenticated_upload" on storage.objects
    for insert to authenticated with check (bucket_id = 'tickets');

create policy "tickets_owner_update" on storage.objects
    for update to authenticated using (bucket_id = 'tickets' and auth.uid() = owner);

create policy "tickets_owner_delete" on storage.objects
    for delete to authenticated using (bucket_id = 'tickets' and auth.uid() = owner);