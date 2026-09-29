-- Nabhi: one database user per app on Supabase, instead of every app using "postgres".
--
-- What it does, for each app listed in nabhi_apps below:
--   1. Makes (or updates) a login user, e.g. nabhi_crm, with a new random password.
--   2. Makes that user the owner of the app's own tables (nbcm_* for the CRM), so the
--      app keeps running its migrations, and can't touch any other app's tables.
--   3. Closes those tables to Supabase's public Data API: anon and authenticated lose
--      every privilege on them, and Row Level Security is switched on (no policies, so
--      the Data API sees nothing). The owner (the app) is not affected by RLS.
--   4. Shows each new password ONCE, in the result below. Nothing is written to a file.
--
-- How to run it:
--   Supabase dashboard > SQL Editor > New query > paste this whole file > Run.
--   Copy each row of the result into that app's DATABASE_URL on Vercel (backend
--   project, Settings > Environment Variables, marked Sensitive), then redeploy it.
--   Don't save the query with the result, and don't paste the passwords anywhere else.
--
-- Running it again sets NEW passwords for the apps listed, so each listed app stops
-- working until its DATABASE_URL is updated. To change one app's password later
-- (someone left, a leak), keep only that app's line in nabhi_apps.
--
-- The "postgres" user keeps working (dashboard, Table Editor): it is made a member of
-- each app user. Change its own password afterwards under Database > Settings.

DROP TABLE IF EXISTS pg_temp.nabhi_apps;
DROP TABLE IF EXISTS pg_temp.nabhi_new_passwords;
CREATE TEMP TABLE nabhi_apps (app_user text PRIMARY KEY, prefix text NOT NULL);
CREATE TEMP TABLE nabhi_new_passwords (app text, app_user text, pooler_user text, password text, tables int);

-- The apps to set up (or to give new passwords). Remove the lines you don't want.
INSERT INTO nabhi_apps (app_user, prefix) VALUES
  ('nabhi_crm',          'nbcm'),
  ('nabhi_inventory',    'nbin'),
  ('nabhi_finance',      'nbfi'),
  ('nabhi_admin',        'nbad'),
  ('nabhi_platform',     'nbpl'),
  ('nabhi_pharmacy',     'nbph'),
  ('nabhi_in_licensing', 'nbil'),
  ('nabhi_regulatory',   'nbrg');

DO $$
DECLARE
  a record;
  r record;
  pw text;
  kind text;
  n int;
BEGIN
  FOR a IN SELECT * FROM nabhi_apps ORDER BY app_user LOOP
    -- a URL-safe random password, 32 characters
    pw := rtrim(translate(encode(extensions.gen_random_bytes(24), 'base64'), '+/', '-_'), '=');

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = a.app_user) THEN
      EXECUTE format(
        'CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS CONNECTION LIMIT 30 PASSWORD %L',
        a.app_user, pw);
    ELSE
      -- only the password (and login): on Supabase, "postgres" may not touch the other attributes
      EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', a.app_user, pw);
    END IF;

    -- postgres can hand tables over to it, and still sees them in the dashboard
    EXECUTE format('GRANT %I TO %I', a.app_user, current_user);

    EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), a.app_user);
    EXECUTE format('GRANT USAGE, CREATE ON SCHEMA public TO %I', a.app_user);

    n := 0;
    FOR r IN
      SELECT c.oid::regclass AS obj, c.relkind
      FROM pg_class c
      JOIN pg_namespace ns ON ns.oid = c.relnamespace
      WHERE ns.nspname = 'public'
        AND c.relname LIKE a.prefix || '\_%'
        AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
        -- a sequence that belongs to a table moves with the table
        AND NOT (c.relkind = 'S' AND EXISTS (
          SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype IN ('a', 'i') AND d.refobjid <> c.oid
        ))
      ORDER BY c.relkind DESC, c.relname
    LOOP
      kind := CASE r.relkind
        WHEN 'v' THEN 'VIEW'
        WHEN 'm' THEN 'MATERIALIZED VIEW'
        WHEN 'f' THEN 'FOREIGN TABLE'
        WHEN 'S' THEN 'SEQUENCE'
        ELSE 'TABLE'
      END;
      EXECUTE format('ALTER %s %s OWNER TO %I', kind, r.obj, a.app_user);
      EXECUTE format('REVOKE ALL ON %s %s FROM anon, authenticated',
                     CASE WHEN r.relkind = 'S' THEN 'SEQUENCE' ELSE 'TABLE' END, r.obj);
      IF r.relkind IN ('r', 'p') THEN
        EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', r.obj);
        n := n + 1;
      END IF;
    END LOOP;

    -- tables the app makes later: nothing for the Data API either
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated', a.app_user);
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated', a.app_user);

    INSERT INTO nabhi_new_passwords
    VALUES (replace(a.app_user, 'nabhi_', ''), a.app_user, a.app_user || '.<project-ref>', pw, n);
  END LOOP;
END
$$;

-- Each app's new password, shown once. For Vercel:
--   DATABASE_URL=postgresql://<pooler_user>:<password>@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
-- with <project-ref> in pooler_user replaced by your project's ref (Project Settings > General).
SELECT app, pooler_user, password, tables AS "tables it owns" FROM nabhi_new_passwords ORDER BY app;
