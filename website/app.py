import os
import secrets
from datetime import datetime, timezone

from flask import (
    Flask, render_template, request, redirect, session, url_for, jsonify,
)

from tiktok_web import (
    generate_pkce, build_auth_url, exchange_code,
    fetch_user_info, init_video_upload, upload_video_bytes,
    check_publish_status,
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-me")

TIKTOK_CLIENT_KEY = os.environ.get("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "")


def _redirect_uri():
    """Build the OAuth redirect URI from the current request host."""
    scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
    return f"{scheme}://{request.host}/callback/"


# ── Existing routes (unchanged) ──────────────────────────────────────────────

@app.route("/tiktokmYW5VHluS2PcrCxUS646CWf1TCNmsqzG.txt")
def tiktok_verification():
    return "tiktok-developers-site-verification=mYW5VHluS2PcrCxUS646CWf1TCNmsqzG", 200, {"Content-Type": "text/plain"}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ── OAuth routes ─────────────────────────────────────────────────────────────

@app.route("/login")
def login():
    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = generate_pkce()

    session["oauth_state"] = state
    session["code_verifier"] = code_verifier

    auth_url = build_auth_url(
        TIKTOK_CLIENT_KEY, _redirect_uri(), state, code_challenge,
    )
    return redirect(auth_url)


@app.route("/callback/")
def callback():
    error = request.args.get("error")
    if error:
        desc = request.args.get("error_description", error)
        return render_template("index.html", error=f"Authorization failed: {desc}")

    received_state = request.args.get("state", "")
    if received_state != session.get("oauth_state"):
        return render_template("index.html", error="OAuth state mismatch. Please try again.")

    code = request.args.get("code")
    if not code:
        return render_template("index.html", error="No authorization code received.")

    code_verifier = session.pop("code_verifier", "")
    session.pop("oauth_state", None)

    try:
        token_data = exchange_code(
            TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET,
            _redirect_uri(), code, code_verifier,
        )
    except Exception as exc:
        return render_template("index.html", error=f"Token exchange failed: {exc}")

    session["access_token"] = token_data["access_token"]
    session["refresh_token"] = token_data["refresh_token"]
    session["open_id"] = token_data.get("open_id", "")

    try:
        user_info = fetch_user_info(session["access_token"])
        session["user_info"] = user_info
    except Exception:
        session["user_info"] = {"open_id": session["open_id"]}

    return redirect(url_for("dashboard"))


# ── Dashboard ────────────────────────────────────────────────────────────────

@app.route("/dashboard")
def dashboard():
    if "access_token" not in session:
        return redirect(url_for("login"))

    user_info = session.get("user_info", {})
    uploads = session.get("uploads", [])
    return render_template("dashboard.html", user_info=user_info, uploads=uploads)


# ── Video upload ─────────────────────────────────────────────────────────────

@app.route("/upload", methods=["POST"])
def upload():
    if "access_token" not in session:
        return redirect(url_for("login"))

    video_file = request.files.get("video")
    caption = request.form.get("caption", "").strip() or "AI cat video"

    if not video_file or video_file.filename == "":
        return redirect(url_for("dashboard"))

    video_bytes = video_file.read()
    if not video_bytes:
        return redirect(url_for("dashboard"))

    access_token = session["access_token"]

    try:
        init_data = init_video_upload(access_token, len(video_bytes), caption)
        upload_video_bytes(init_data["upload_url"], video_bytes)
    except Exception as exc:
        return render_template(
            "dashboard.html",
            user_info=session.get("user_info", {}),
            uploads=session.get("uploads", []),
            error=f"Upload failed: {exc}",
        )

    publish_id = init_data["publish_id"]

    uploads = session.get("uploads", [])
    uploads.insert(0, {
        "publish_id": publish_id,
        "caption": caption,
        "status": "PROCESSING_UPLOAD",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    })
    session["uploads"] = uploads

    return render_template("uploading.html", publish_id=publish_id, caption=caption)


@app.route("/upload/status/<publish_id>")
def upload_status(publish_id):
    if "access_token" not in session:
        return jsonify({"error": "not authenticated"}), 401

    if request.headers.get("Accept", "").startswith("application/json"):
        try:
            result = check_publish_status(session["access_token"], publish_id)
        except Exception as exc:
            return jsonify({"status": "ERROR", "detail": str(exc)})

        status = result.get("status", "UNKNOWN")

        # Update session upload history
        uploads = session.get("uploads", [])
        for entry in uploads:
            if entry["publish_id"] == publish_id:
                entry["status"] = status
                break
        session["uploads"] = uploads

        return jsonify({
            "status": status,
            "fail_reason": result.get("fail_reason"),
        })

    # Initial HTML page load
    caption = ""
    for entry in session.get("uploads", []):
        if entry["publish_id"] == publish_id:
            caption = entry.get("caption", "")
            break
    return render_template("uploading.html", publish_id=publish_id, caption=caption)


# ── Logout ───────────────────────────────────────────────────────────────────

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
