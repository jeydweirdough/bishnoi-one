"""Interactive local setup. Never pass credentials as command-line arguments."""
from getpass import getpass
from pathlib import Path
import os
from cryptography.fernet import Fernet
from dotenv import dotenv_values, set_key
from app.config import API_DIR


def main():
    if os.environ.get('VERCEL_ENV') or os.environ.get('ENVIRONMENT', '').lower() == 'production':
        raise SystemExit('This helper is for local development only.')
    path = API_DIR / '.env'
    existing = dotenv_values(path)
    print('Dedicated Finance Zoho setup. Inputs are hidden; values stay in backend/.env.')
    client_id = getpass('New Finance Client ID: ').strip()
    secret = getpass('New Finance Client Secret: ').strip()
    if not client_id or not secret or any(c in client_id + secret for c in '\r\n\x00'):
        raise SystemExit('Both values are required and must be single-line.')
    region = input('Zoho region [com]: ').strip() or 'com'
    from app.zoho_connection import REGIONS
    if region not in REGIONS:
        raise SystemExit('Unsupported region; no settings changed.')
    key = existing.get('ZOHO_ENCRYPTION_KEY') or Fernet.generate_key().decode()
    try:
        Fernet(key.encode())
    except ValueError:
        raise SystemExit('Existing encryption key is invalid. Contact IT before replacing it.') from None
    for name, value in {'ZOHO_CLIENT_ID': client_id, 'ZOHO_CLIENT_SECRET': secret,
                        'ZOHO_ENCRYPTION_KEY': key, 'ZOHO_REGION': region,
                        'ZOHO_REDIRECT_URI': 'http://localhost:4301/finance/integrations/zoho/callback'}.items():
        set_key(str(path), name, value)
    os.chmod(path, 0o600)
    print('Saved locally. Keep .env and its encryption key private. Restart the Finance API to load settings.')
    print('Then open http://localhost:4301/finance/integrations/zoho')


if __name__ == '__main__':
    main()
