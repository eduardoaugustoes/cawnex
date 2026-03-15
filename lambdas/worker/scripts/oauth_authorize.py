#!/usr/bin/env python3
"""Run the Anthropic OAuth PKCE flow to get tokens.

Usage:
    python scripts/oauth_authorize.py

Opens browser, you authorize, paste the code, get tokens in .env.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
AUTH_URL = "https://claude.ai/oauth/authorize"
TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
REDIRECT_URI = "https://platform.claude.com/oauth/code/callback"
SCOPES = "user:inference user:profile"


def generate_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def exchange_code_curl(code: str, verifier: str) -> dict:
    """Use curl for the exchange — avoids Python urllib quirks."""
    payload = json.dumps({
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    })

    result = subprocess.run(
        [
            "curl", "-s", "-X", "POST", TOKEN_URL,
            "-H", "Content-Type: application/json",
            "-d", payload,
        ],
        capture_output=True, text=True, timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(f"curl failed: {result.stderr}")

    print(f"  Response: {result.stdout[:200]}")
    return json.loads(result.stdout)


def write_env(access_token: str, refresh_token: str) -> None:
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env_path = os.path.abspath(env_path)

    lines: list[str] = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                key = line.split("=")[0].strip()
                if key not in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_REFRESH_TOKEN", "GITHUB_TOKEN"):
                    lines.append(line)

    lines.append(f"ANTHROPIC_AUTH_TOKEN={access_token}\n")
    lines.append(f"ANTHROPIC_REFRESH_TOKEN={refresh_token}\n")

    gh_token = os.popen("gh auth token 2>/dev/null").read().strip()
    if gh_token:
        lines.append(f"GITHUB_TOKEN={gh_token}\n")

    with open(env_path, "w") as f:
        f.writelines(lines)
    print(f"✓ Wrote tokens to {env_path}")


def main() -> None:
    print("=== Anthropic OAuth PKCE Flow ===\n")

    verifier, challenge = generate_pkce()

    params = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": verifier,
    })
    url = f"{AUTH_URL}?{params}"

    print(f"1. Opening browser...\n   {url}\n")
    webbrowser.open(url)

    print("2. Authorize in the browser.")
    print("3. You'll be redirected — copy the code from the page.\n")

    raw = input("Paste the code (or full URL): ").strip()

    # Extract code from URL if they pasted the full redirect URL
    if "code=" in raw:
        parsed = urllib.parse.urlparse(raw)
        params_dict = urllib.parse.parse_qs(parsed.query)
        code = params_dict.get("code", [""])[0]
    else:
        code = raw

    # Strip #state fragment
    if "#" in code:
        code = code.split("#")[0]

    if not code:
        print("No code provided.")
        sys.exit(1)

    print(f"\nCode: {code[:20]}... ({len(code)} chars)")
    print(f"Verifier: {verifier[:20]}... ({len(verifier)} chars)")
    print(f"\n4. Exchanging code for tokens...")

    try:
        tokens = exchange_code_curl(code, verifier)
    except Exception as e:
        print(f"\n✗ Failed: {e}")
        sys.exit(1)

    if "error" in tokens:
        print(f"\n✗ Error: {tokens}")
        sys.exit(1)

    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    expires_in = tokens.get("expires_in", 0)

    if not access_token:
        print(f"\n✗ No access_token in response: {tokens}")
        sys.exit(1)

    print(f"\n✓ Access token:  {access_token[:25]}... (expires in {expires_in}s)")
    if refresh_token:
        print(f"✓ Refresh token: {refresh_token[:25]}...")

    write_env(access_token, refresh_token)

    if refresh_token:
        update = input("\nUpdate ANTHROPIC_REFRESH_TOKEN in GitHub secrets? [y/N] ").strip().lower()
        if update == "y":
            result = os.popen(
                f'echo "{refresh_token}" | gh secret set ANTHROPIC_REFRESH_TOKEN --repo eduardoaugustoes/cawnex 2>&1'
            ).read()
            print(f"  {result.strip() or '✓ Secret updated'}")

    print(f"\n✓ Ready! Run:")
    print(f"  source .env")
    print(f"  python scripts/smoke_test.py planner")


if __name__ == "__main__":
    main()
