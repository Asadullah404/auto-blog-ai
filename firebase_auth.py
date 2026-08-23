"""
firebase_auth.py — Firebase Auth via email/password (Identity Toolkit REST API).

Shared by pipeline_gui.py (interactive sign-in/sign-up) and automation.py
(reads the same cached session to authenticate its own Firestore calls).
Each PyInstaller .exe bundles this file independently, same as the rest of
the app's two-exe split — there is no IPC between the processes, just a
shared file on disk.

Deliberately email/password rather than "Sign in with Google": Google
Sign-In requires a separately-registered OAuth client (a hard Google
platform requirement, not a Firebase limitation — Firebase's own SDKs only
hide this on platforms with an official SDK, which Python desktop isn't
one of). Email/password needs nothing beyond the project's public web
apiKey, so there's no OAuth client to create/manage/bundle at all.

Only the long-lived refresh token + profile info are cached to disk
(firebase_session.json). ID tokens are short-lived (~1h) and are always
re-derived from the refresh token via get_valid_id_token().

firebase_config.json (apiKey/authDomain/projectId) is not a traditional
secret — see firebase_config.example.json — access control is enforced by
Firestore Security Rules keyed on the caller's authenticated uid, not by
hiding this value.
"""
import json
from pathlib import Path

import requests

FIREBASE_CONFIG_FILE = "firebase_config.json"
SESSION_FILE         = "firebase_session.json"

IDENTITY_TOOLKIT_BASE = "https://identitytoolkit.googleapis.com/v1/accounts"
SECURE_TOKEN_URL      = "https://securetoken.googleapis.com/v1/token"

# Identity Toolkit's error codes, translated to something a user can act on.
_ERROR_MESSAGES = {
    "EMAIL_EXISTS":         "An account with this email already exists — try signing in instead.",
    "EMAIL_NOT_FOUND":      "No account found with this email — try creating one instead.",
    "INVALID_PASSWORD":     "Incorrect password.",
    "INVALID_LOGIN_CREDENTIALS": "Incorrect email or password.",
    "WEAK_PASSWORD":        "Password must be at least 6 characters.",
    "INVALID_EMAIL":        "That doesn't look like a valid email address.",
    "MISSING_PASSWORD":     "Please enter a password.",
    "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many attempts — please wait a bit and try again.",
    "OPERATION_NOT_ALLOWED": "Email/Password sign-in isn't enabled for this project yet — "
                              "in the Firebase console, go to Authentication -> Sign-in "
                              "method -> enable Email/Password.",
}


class AuthError(Exception):
    pass


def _firebase_api_key() -> str:
    path = Path(FIREBASE_CONFIG_FILE)
    if not path.exists():
        raise AuthError(
            f"{path} not found. This should have been bundled with the app — "
            f"try reinstalling. (Contains the Firebase project's public web "
            f"config, not a private key — see firebase_config.example.json.)")
    cfg = json.loads(path.read_text(encoding="utf-8"))
    api_key = cfg.get("apiKey")
    if not api_key:
        raise AuthError(f"{path} is missing 'apiKey'.")
    return api_key


def _load_session() -> dict | None:
    path = Path(SESSION_FILE)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _save_session(session: dict):
    Path(SESSION_FILE).write_text(json.dumps(session, indent=2), encoding="utf-8")


def sign_out():
    """Deletes the cached session, if any."""
    Path(SESSION_FILE).unlink(missing_ok=True)


def current_profile() -> dict | None:
    """Cached {uid, email} without a network call — for instant GUI display
    on launch, before the async refresh completes."""
    session = _load_session()
    if not session:
        return None
    return {k: session.get(k) for k in ("uid", "email")}


def _raise_for_identity_error(resp):
    try:
        code = resp.json()["error"]["message"]
    except (ValueError, KeyError):
        raise AuthError(f"Firebase request failed: {resp.status_code} {resp.text}")
    raise AuthError(_ERROR_MESSAGES.get(code, code))


def _password_auth(endpoint: str, email: str, password: str) -> dict:
    api_key = _firebase_api_key()
    resp = requests.post(
        f"{IDENTITY_TOOLKIT_BASE}:{endpoint}",
        params={"key": api_key},
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=30,
    )
    if not resp.ok:
        _raise_for_identity_error(resp)
    data = resp.json()

    session = {
        "refreshToken": data["refreshToken"],
        "uid":          data["localId"],
        "email":        data.get("email", email),
    }
    _save_session(session)
    return {k: session[k] for k in ("uid", "email")}


def sign_up(email: str, password: str) -> dict:
    """Creates a new email/password account and signs in. Returns {uid, email}."""
    return _password_auth("signUp", email, password)


def sign_in(email: str, password: str) -> dict:
    """Signs in an existing email/password account. Returns {uid, email}."""
    return _password_auth("signInWithPassword", email, password)


def get_valid_id_token() -> tuple[str, str] | tuple[None, None]:
    """
    Returns (id_token, uid) for the currently signed-in user, refreshing the
    short-lived ID token from the cached refresh token on every call (Firebase
    rotates refresh tokens, so the cache is rewritten each time). Returns
    (None, None) if no one is signed in or the session was revoked.
    """
    session = _load_session()
    if not session or not session.get("refreshToken"):
        return None, None

    api_key = _firebase_api_key()
    try:
        resp = requests.post(
            SECURE_TOKEN_URL,
            params={"key": api_key},
            data={
                "grant_type": "refresh_token",
                "refresh_token": session["refreshToken"],
            },
            timeout=30,
        )
    except requests.RequestException:
        return None, None

    if not resp.ok:
        # Refresh token revoked/expired — clear the stale session so callers
        # know to prompt sign-in again rather than retrying forever.
        sign_out()
        return None, None

    data = resp.json()
    session["refreshToken"] = data["refresh_token"]
    _save_session(session)
    return data["id_token"], data["user_id"]
