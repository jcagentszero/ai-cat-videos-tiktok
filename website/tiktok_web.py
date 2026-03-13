"""
website/tiktok_web.py
─────────────────────
Self-contained TikTok API helpers for the web app.

Duplicates a small subset of publishers/oauth.py and publishers/tiktok.py
to avoid importing the CLI codebase (which has side effects at import time).
"""

import hashlib
import secrets

import requests

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
BASE_URL = "https://open.tiktokapis.com/v2"
SCOPES = "user.info.basic,video.upload"


def generate_pkce():
    """Generate PKCE code_verifier and code_challenge (S256).

    TikTok uses hex-encoded SHA256 for code_challenge (not base64url).
    """
    charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    verifier = "".join(secrets.choice(charset) for _ in range(64))
    challenge = hashlib.sha256(verifier.encode("ascii")).hexdigest()
    return verifier, challenge


def build_auth_url(client_key, redirect_uri, state, code_challenge):
    """Build the TikTok OAuth authorization URL."""
    from urllib.parse import urlencode

    params = {
        "client_key": client_key,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code(client_key, client_secret, redirect_uri, code, code_verifier):
    """Exchange authorization code for access/refresh tokens."""
    payload = {
        "client_key": client_key,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    resp = requests.post(TOKEN_URL, data=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if data.get("error"):
        raise RuntimeError(
            f"Token exchange failed: {data.get('error_description', data['error'])}"
        )
    return data


def refresh_access_token(client_key, client_secret, refresh_token):
    """Refresh an expired access token."""
    payload = {
        "client_key": client_key,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    resp = requests.post(TOKEN_URL, data=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if data.get("error"):
        raise RuntimeError(
            f"Token refresh failed: {data.get('error_description', data['error'])}"
        )
    return data


def fetch_user_info(access_token):
    """Fetch the authenticated user's basic info."""
    url = f"{BASE_URL}/user/info/?fields=open_id,union_id,avatar_url,display_name"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    error = data.get("error", {})
    if error.get("code") != "ok":
        raise RuntimeError(
            f"Fetch user info failed: {error.get('message', error.get('code'))}"
        )
    return data.get("data", {}).get("user", {})


def init_video_upload(access_token, file_size, caption):
    """Initialize a video upload (FILE_UPLOAD source, SELF_ONLY, AIGC)."""
    url = f"{BASE_URL}/post/publish/video/init/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    body = {
        "post_info": {
            "title": caption,
            "privacy_level": "SELF_ONLY",
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "is_aigc": True,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": file_size,
            "total_chunk_count": 1,
        },
    }
    resp = requests.post(url, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    error = data.get("error", {})
    if error.get("code") != "ok":
        raise RuntimeError(
            f"Init upload failed: {error.get('message', error.get('code'))}"
        )

    result = data.get("data", {})
    if not result.get("publish_id") or not result.get("upload_url"):
        raise RuntimeError("Init upload response missing publish_id or upload_url")
    return result


def upload_video_bytes(upload_url, video_bytes):
    """PUT video bytes to the TikTok upload URL."""
    file_size = len(video_bytes)
    headers = {
        "Content-Type": "video/mp4",
        "Content-Length": str(file_size),
        "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
    }
    resp = requests.put(upload_url, headers=headers, data=video_bytes, timeout=300)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Video upload failed with status {resp.status_code}")
    return True


def check_publish_status(access_token, publish_id):
    """Check the publish status of an uploaded video."""
    url = f"{BASE_URL}/post/publish/status/fetch/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    body = {"publish_id": publish_id}
    resp = requests.post(url, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    error = data.get("error", {})
    if error.get("code") != "ok":
        raise RuntimeError(
            f"Status check failed: {error.get('message', error.get('code'))}"
        )
    return data.get("data", {})
