"""
publishers/oauth.py
───────────────────
TikTok OAuth 2.0 Authorization Code flow.

Starts a local HTTP server, opens the browser to TikTok's authorization page,
receives the callback with an auth code, exchanges it for tokens, and persists
them via token_store.

Usage:
  python -m publishers.oauth          # run standalone
  python main.py --auth               # run via main entry point
"""

import hashlib
import secrets
import threading
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
import webbrowser

import requests

from config import settings
from publishers import token_store
from utils.logger import logger

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
REDIRECT_HOST = "localhost"
REDIRECT_PORT = 8080
REDIRECT_PATH = "/callback"
SCOPES_PRODUCTION = "user.info.basic,video.upload,video.publish"
SCOPES_SANDBOX = "user.info.basic,video.upload"
CALLBACK_TIMEOUT = 120


def _redirect_uri():
    return f"http://{REDIRECT_HOST}:{REDIRECT_PORT}{REDIRECT_PATH}"


def _generate_pkce():
    """Generate PKCE code_verifier and code_challenge (S256).

    TikTok uses hex-encoded SHA256 for code_challenge (not base64url).
    See: https://developers.tiktok.com/doc/login-kit-desktop/
    """
    charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    verifier = "".join(secrets.choice(charset) for _ in range(64))
    challenge = hashlib.sha256(verifier.encode("ascii")).hexdigest()
    return verifier, challenge


def _scopes():
    """Return the appropriate OAuth scopes for sandbox vs production."""
    return SCOPES_SANDBOX if settings.TIKTOK_SANDBOX else SCOPES_PRODUCTION


def build_auth_url(state, code_challenge):
    params = {
        "client_key": settings.TIKTOK_CLIENT_KEY,
        "scope": _scopes(),
        "response_type": "code",
        "redirect_uri": _redirect_uri(),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code(code, code_verifier):
    payload = {
        "client_key": settings.TIKTOK_CLIENT_KEY,
        "client_secret": settings.TIKTOK_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": _redirect_uri(),
        "code_verifier": code_verifier,
    }
    resp = requests.post(TOKEN_URL, data=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if data.get("error"):
        raise RuntimeError(
            f"TikTok token exchange failed: "
            f"{data.get('error_description', data['error'])}"
        )

    return data


class _CallbackHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != REDIRECT_PATH:
            self.send_response(404)
            self.end_headers()
            return

        params = parse_qs(parsed.query)
        self.server.callback_params = params

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()

        if "error" in params:
            error = params["error"][0]
            desc = params.get("error_description", [""])[0]
            self.wfile.write(
                f"<h1>Authorization Failed</h1><p>{error}: {desc}</p>".encode()
            )
        else:
            self.wfile.write(
                b"<h1>Authorization Successful</h1>"
                b"<p>You can close this window and return to the terminal.</p>"
            )

        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, format, *args):
        pass


def run_oauth_flow():
    if not settings.TIKTOK_CLIENT_KEY or not settings.TIKTOK_CLIENT_SECRET:
        raise ValueError(
            "TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET must be set in .env"
        )

    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = _generate_pkce()
    auth_url = build_auth_url(state, code_challenge)

    server = HTTPServer((REDIRECT_HOST, REDIRECT_PORT), _CallbackHandler)
    server.callback_params = {}

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    logger.info(
        "Starting OAuth callback server on http://{}:{}",
        REDIRECT_HOST, REDIRECT_PORT,
    )
    logger.info("Requesting scopes: {}", _scopes())
    logger.info("Opening browser for TikTok authorization...")
    webbrowser.open(auth_url)

    logger.info(
        "Waiting for authorization callback (timeout: {}s)...",
        CALLBACK_TIMEOUT,
    )
    server_thread.join(timeout=CALLBACK_TIMEOUT)

    if server_thread.is_alive():
        server.shutdown()
        server.server_close()
        raise TimeoutError(
            f"OAuth callback not received within {CALLBACK_TIMEOUT} seconds"
        )

    server.server_close()
    params = server.callback_params

    if "error" in params:
        error = params["error"][0]
        desc = params.get("error_description", [""])[0]
        raise RuntimeError(f"Authorization denied: {error} — {desc}")

    if "code" not in params:
        raise RuntimeError("No authorization code received in callback")

    received_state = params.get("state", [""])[0]
    if received_state != state:
        raise RuntimeError("OAuth state mismatch — possible CSRF attack")

    code = params["code"][0]
    logger.info("Authorization code received, exchanging for tokens...")

    token_data = exchange_code(code, code_verifier)

    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]
    open_id = token_data["open_id"]
    expires_in = token_data.get("expires_in", 86400)

    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    ).isoformat()

    token_store.save_tokens(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        open_id=open_id,
    )

    logger.info("Tokens saved to {}", settings.TOKEN_FILE)
    logger.info("TikTok Open ID: {}", open_id)
    logger.info(
        "Access token expires at {} (in {}s)", expires_at, expires_in,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "open_id": open_id,
        "expires_in": expires_in,
    }


if __name__ == "__main__":
    run_oauth_flow()
