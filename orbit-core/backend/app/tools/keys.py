"""Makes a new private key for signing sign-in tokens.

    uv run python -m app.tools.keys

Paste the JWT_PRIVATE_KEY line into the live API's environment settings (never
into chat or a repository). When replacing an older key, also move the older
key's public half (printed with --public-of) into JWT_PREVIOUS_PUBLIC_KEYS
until the tokens it signed have expired (SESSION_HOURS).
"""

import argparse
import json
import sys

from app.keys import new_private_pem, public_pem


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.tools.keys", description=__doc__.split("\n")[0])
    parser.add_argument("--public-of", metavar="PEM_FILE", help="print the public half of an existing private key instead")
    args = parser.parse_args(argv)
    if args.public_of:
        with open(args.public_of, encoding="utf-8") as f:
            print(json.dumps([public_pem(f.read())]))
        return 0
    pem = new_private_pem().strip().replace("\n", "\\n")
    print(f'JWT_PRIVATE_KEY="{pem}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
