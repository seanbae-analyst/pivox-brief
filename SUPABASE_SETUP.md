# Supabase setup — public settings picker (5 min, free)

The picker at `/settings.html` saves your theme/level choice to Supabase; the morning cron reads it.

## Steps
1. Create a free project at https://supabase.com (New project → pick a name + DB password).
2. In the project, open **SQL Editor** and run:

```sql
create table if not exists brief_settings (
  id            text primary key,
  themes        jsonb default '[]',
  custom        jsonb default '[]',
  explain_level text  default '초보',
  updated_at    timestamptz default now()
);

-- single-user personal app: this one table is anon read+write (low stakes —
-- worst case someone changes which stocks show in YOUR brief).
alter table brief_settings enable row level security;
create policy "anon all" on brief_settings for all using (true) with check (true);

insert into brief_settings (id) values ('default') on conflict (id) do nothing;
```

3. **Settings → API**: copy the **Project URL** and the **anon public** key.
4. Paste into `.env` (and tell me — I'll add them to Vercel + redeploy):

```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOi...
```

That's it. After redeploy, `/settings.html` saves to Supabase and the next morning brief uses it.
Until then the page works in browser-only (localStorage) mode.
