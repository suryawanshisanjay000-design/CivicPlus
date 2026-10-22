# CivicPulse Development Status

## Current Architecture
- Vite + React + TypeScript single-page MVP.
- Offline-first persistence using `localStorage`.
- Photo proof is stored as browser data URLs for local demo purposes.
- No backend or Supabase is connected yet.

## What Works Locally
- Anonymous citizen reporting.
- Deterministic fallback triage for department, priority, and SLA.
- Duplicate detection against nearby active tickets.
- Ticket number and PIN generation.
- Public tracking using ticket number + PIN.
- Official login demo roles.
- Dashboard filtering and ticket detail.
- Assignment, in-progress, resolution proof, closing note validation, and audit timeline.

## Demo Accounts
- Field officer: `officer@civicpulse.local` / `password`
- Supervisor: `supervisor@civicpulse.local` / `password`
- Commissioner: `commissioner@civicpulse.local` / `password`

## Next Implementation Order
1. Add Supabase schema and migrations.
2. Replace local repository with Supabase API calls.
3. Add Supabase Storage for before/after photos.
4. Add Supabase Auth for officials.
5. Add server-side Groq triage.
6. Deploy to Vercel.
