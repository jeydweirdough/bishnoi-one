# Nabhi desktop

Nabhi.exe, the desktop app, and the tool that sets each client company up.

Each company has its own Supabase database. We give each one:

- **Company ID**, for example `NBH-GETMEDS-01`: which company. Not a secret.
- **Activation key**, for example `7KQ4M-2XD9P-RTH6W-A3CFN-8B5JE`: opens the company's connection file. Give it to the company's administrator only, separately from the file.
- **Connection file**, `NBH-GETMEDS-01.nabhi`: the database connection for each app, with its password, encrypted with the activation key (AES-256-GCM, key from scrypt). Useless without the key, so it can go by email or shared drive.

Nabhi.exe asks for the Company ID, the activation key and the file once, on each PC, then keeps the connection (and the key, for renewed files) locked to that PC and that Windows account with Windows DPAPI. It starts each app's API and screens on the PC itself, on 127.0.0.1 only (ports in `lib/apps.mjs`), and opens the first app. There is no Vercel in between: the APIs work straight on the company's database.

## Setting a company up

1. On the company's Supabase, run `scripts/supabase/app-users.sql` (SQL Editor). It shows each app's own database user and password, once.
2. Issue the file, typing each app's connection when asked (it isn't shown on screen):

   ```
   cd nabhi-desktop
   npm run company -- issue
   ```

   The Company ID and activation key are printed once; the file is written to `nabhi-desktop/issued/` (never committed). Keep the activation key: it's needed to renew the file.

3. Give the Company ID and the file to the company, and the activation key to their administrator separately.

The connections must be the apps' own users (`nabhi_crm.<project-ref>`), not `postgres`. The tool refuses `postgres` unless run with `--allow-postgres`.

## Renewing

A file expires (30 days by default); Nabhi.exe fetches the newest one before then. To change a password, or to extend a file:

```
npm run company -- renew issued/NBH-GETMEDS-01.nabhi
```

Same Company ID and activation key; only the file changes. To see what a file holds, passwords hidden:

```
npm run company -- check issued/NBH-GETMEDS-01.nabhi
```

## Building Nabhi.exe

The installer carries each app's API (with its own Python) and screens (run on Electron's own Node). Build them, then the installer:

```
# 1. The APIs, each with its own Python (from its backend folder)
cd nabhi-crm/backend        && uv run --with pyinstaller python ../../nabhi-desktop/backends/build.py crm
cd nabhi-inventory/backend  && uv run --with pyinstaller python ../../nabhi-desktop/backends/build.py inventory

# 2. The screens
cd nabhi-desktop && npm run build:web

# 3. The installer: release/Nabhi-Setup-<version>.exe
npm run pack
```

The installer is unsigned: on the first install Windows shows "Windows protected your PC"; choose More info, then Run anyway. It installs for the current Windows user only, with no administrator rights, and adds a Nabhi shortcut to the desktop.

To try it from the repo instead (after steps 1 and 2): `npm start`. Set `NABHI_USER_DATA` to a folder to keep that try apart from a real setup. Running inside VS Code's terminal, clear `ELECTRON_RUN_AS_NODE` first, or Electron starts as plain Node.

Automatic updates: Nabhi.exe checks for a newer version on start only when built with an update address (electron-builder's `publish` setting, a `generic` URL where `release/latest.yml` and the installer are uploaded). Until then, hand out the new installer.

## Tests

```
npm test
```
