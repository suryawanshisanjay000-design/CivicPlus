-- CivicPulse Demo Seed Data
-- Run this after the initial schema

-- Demo officials (password is "password" for all)
-- Password hash for "password" using bcrypt
-- In production, use proper password hashing

insert into officials (auth_user_id, email, full_name, role, department_id, password_hash) values
    (uuid_generate_v4(), 'officer@civicpulse.local', 'Asha Field Officer', 'FIELD_OFFICER', (select id from departments where code = 'ROADS'), '$2b$12$7Z2c3bpWbk.YiMNrB5eXg.AB19i7XydgyeRsxrk8hm0WVJx95RW4G'),
    (uuid_generate_v4(), 'supervisor@civicpulse.local', 'Ravi Supervisor', 'SUPERVISOR', (select id from departments where code = 'WATER'), '$2b$12$7Z2c3bpWbk.YiMNrB5eXg.AB19i7XydgyeRsxrk8hm0WVJx95RW4G'),
    (uuid_generate_v4(), 'commissioner@civicpulse.local', 'Meera Commissioner', 'COMMISSIONER', null, '$2b$12$7Z2c3bpWbk.YiMNrB5eXg.AB19i7XydgyeRsxrk8hm0WVJx95RW4G')
on conflict (email) do nothing;

-- Demo tickets
do $$
declare
    officer_id uuid;
    roads_dept_id uuid;
    water_dept_id uuid;
    ward1_id uuid;
    ward2_id uuid;
    ticket1_id uuid;
    ticket2_id uuid;
    ticket3_id uuid;
begin
    select id into officer_id from officials where email = 'officer@civicpulse.local' limit 1;
    select id into roads_dept_id from departments where code = 'ROADS';
    select id into water_dept_id from departments where code = 'WATER';
    select id into ward1_id from wards where ward_number = 1;
    select id into ward2_id from wards where ward_number = 2;

    -- Ticket 1: Pothole - SUBMITTED
    ticket1_id := uuid_generate_v4();
    insert into tickets (id, ticket_number, tracking_pin_hash, description, category, department_code, department_id, ward_id, priority, status, latitude, longitude, address, sla_hours, sla_deadline, created_at)
    values (
        ticket1_id,
        'CP-2026-123456',
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', -- hash of '123456'
        'Large pothole on Main Street near the bus stop causing traffic issues and accidents',
        'Pothole / Road',
        'ROADS',
        roads_dept_id,
        ward1_id,
        'HIGH',
        'SUBMITTED',
        12.9716, 77.5946,
        'Main Street, Bus Stop Area',
        48,
        now() + interval '48 hours',
        now() - interval '2 hours'
    );

    insert into timeline_events (id, ticket_id, at, label, detail)
    values
        (uuid_generate_v4(), ticket1_id, now() - interval '2 hours', 'Submitted', 'Anonymous complaint received.'),
        (uuid_generate_v4(), ticket1_id, now() - interval '1 hour 55 minutes', 'Triaged', 'Routed to Roads with high priority.');

    -- Ticket 2: Water leak - ASSIGNED
    ticket2_id := uuid_generate_v4();
    insert into tickets (id, ticket_number, tracking_pin_hash, description, category, department_code, department_id, ward_id, priority, status, latitude, longitude, address, sla_hours, sla_deadline, created_at, assigned_at, assigned_officer_id)
    values (
        ticket2_id,
        'CP-2026-789012',
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        'Water pipe burst on Park Avenue flooding the sidewalk and road',
        'Water / Sewer',
        'WATER',
        water_dept_id,
        ward2_id,
        'URGENT',
        'ASSIGNED',
        12.9784, 77.6046,
        'Park Avenue, Near Metro Station',
        24,
        now() + interval '24 hours',
        now() - interval '6 hours',
        now() - interval '4 hours',
        officer_id
    );

    insert into timeline_events (id, ticket_id, at, label, detail, actor_id)
    values
        (uuid_generate_v4(), ticket2_id, now() - interval '6 hours', 'Submitted', 'Anonymous complaint received.', null),
        (uuid_generate_v4(), ticket2_id, now() - interval '5 hours 55 minutes', 'Triaged', 'Routed to Water with urgent priority.', null),
        (uuid_generate_v4(), ticket2_id, now() - interval '4 hours', 'Assigned', 'Assigned to Asha Field Officer.', officer_id);

    -- Ticket 3: Garbage - IN_PROGRESS
    ticket3_id := uuid_generate_v4();
    insert into tickets (id, ticket_number, tracking_pin_hash, description, category, department_code, department_id, ward_id, priority, status, latitude, longitude, address, sla_hours, sla_deadline, created_at, assigned_at, started_at, assigned_officer_id)
    values (
        ticket3_id,
        'CP-2026-345678',
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        'Garbage pile accumulating at the corner of 5th Cross and 10th Main for over a week',
        'Garbage',
        'SOLID_WASTE',
        (select id from departments where code = 'SOLID_WASTE'),
        ward1_id,
        'MEDIUM',
        'IN_PROGRESS',
        12.9750, 77.5900,
        '5th Cross, 10th Main Junction',
        24,
        now() + interval '12 hours',
        now() - interval '18 hours',
        now() - interval '16 hours',
        now() - interval '2 hours',
        officer_id
    );

    insert into timeline_events (id, ticket_id, at, label, detail, actor_id)
    values
        (uuid_generate_v4(), ticket3_id, now() - interval '18 hours', 'Submitted', 'Anonymous complaint received.', null),
        (uuid_generate_v4(), ticket3_id, now() - interval '17 hours 55 minutes', 'Triaged', 'Routed to Solid Waste with medium priority.', null),
        (uuid_generate_v4(), ticket3_id, now() - interval '16 hours', 'Assigned', 'Assigned to Asha Field Officer.', officer_id),
        (uuid_generate_v4(), ticket3_id, now() - interval '2 hours', 'In Progress', 'Field work has started.', officer_id);

    -- Ticket 4: Resolved
    insert into tickets (id, ticket_number, tracking_pin_hash, description, category, department_code, department_id, ward_id, priority, status, latitude, longitude, address, sla_hours, sla_deadline, created_at, assigned_at, started_at, resolved_at, closing_notes, after_photo_url, assigned_officer_id)
    values (
        uuid_generate_v4(),
        'CP-2026-901234',
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        'Streetlight not working on Gandhi Road for past 3 days',
        'Streetlight / Electrical',
        'ELECTRICAL',
        (select id from departments where code = 'ELECTRICAL'),
        ward2_id,
        'URGENT',
        'RESOLVED',
        12.9800, 77.6100,
        'Gandhi Road, Near School',
        12,
        now() - interval '6 hours',
        now() - interval '10 hours',
        now() - interval '9 hours',
        now() - interval '8 hours',
        now() - interval '1 hour',
        'Replaced faulty LED bulb and checked wiring. Light now functioning properly.',
        'https://example.com/after-photo.jpg',
        officer_id
    );

    -- Ticket 5: Breached (SLA passed)
    insert into tickets (id, ticket_number, tracking_pin_hash, description, category, department_code, department_id, ward_id, priority, status, latitude, longitude, address, sla_hours, sla_deadline, created_at, assigned_at, assigned_officer_id)
    values (
        uuid_generate_v4(),
        'CP-2026-567890',
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        'Open manhole cover on Ring Road creating safety hazard',
        'Public Health',
        'PUBLIC_HEALTH',
        (select id from departments where code = 'PUBLIC_HEALTH'),
        ward1_id,
        'HIGH',
        'BREACHED',
        12.9650, 77.5800,
        'Ring Road, Sector 4',
        72,
        now() - interval '2 hours',
        now() - interval '80 hours',
        now() - interval '78 hours',
        officer_id
    );

    -- Duplicate ticket linked to ticket1
    insert into tickets (id, ticket_number, tracking_pin_hash, description, category, department_code, department_id, ward_id, priority, status, latitude, longitude, address, sla_hours, sla_deadline, created_at, duplicate_of, impact_count)
    values (
        uuid_generate_v4(),
        'CP-2026-111222',
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        'Another report of the same pothole on Main Street',
        'Pothole / Road',
        'ROADS',
        roads_dept_id,
        ward1_id,
        'HIGH',
        'SUBMITTED',
        12.9717, 77.5947,
        'Main Street, Bus Stop Area',
        48,
        now() + interval '48 hours',
        now() - interval '30 minutes',
        ticket1_id,
        2
    );

    insert into timeline_events (id, ticket_id, at, label, detail)
    values
        (uuid_generate_v4(), (select id from tickets where ticket_number = 'CP-2026-111222'), now() - interval '30 minutes', 'Submitted', 'Anonymous complaint received.'),
        (uuid_generate_v4(), (select id from tickets where ticket_number = 'CP-2026-111222'), now() - interval '25 minutes', 'Duplicate Detected', 'Linked to existing ticket CP-2026-123456');
end $$;