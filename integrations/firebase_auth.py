"""
integrations/firebase_auth.py — Firebase Authentication via REST API
=======================================================================
Authenticates using Firebase Identity Toolkit REST API with email/password.
Caches long-lived refresh tokens in firebase_session.json and generates
short-lived ID tokens on-demand for Firestore Security Rules compliance.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

FIREBASE_CONFIG_FILE = "firebase_config.json"
SESSION_FILE = "firebase_session.json"

IDENTITY_TOOLKIT_BASE = "https://identitytoolkit.googleapis.com/v1/accounts"
SECURE_TOKEN_URL = "https://securetoken.googleapis.com/v1/token"

_ERROR_MESSAGES = {
    "EMAIL_EXISTS": "An account with this email already exists — try signing in instead.",
    "EMAIL_NOT_FOUND": "No account found with this email — try creating one instead.",
    "INVALID_PASSWORD": "Incorrect password.",
    "INVALID_LOGIN_CREDENTIALS": "Incorrect email or password.",
    "WEAK_PASSWORD": "Password must be at least 6 characters.",
    "INVALID_EMAIL": "That doesn't look like a valid email address.",
    "MISSING_PASSWORD": "Please enter a password.",
    "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many attempts — please wait a bit and try again.",
    "OPERATION_NOT_ALLOWED": "Email/Password sign-in isn't enabled for this project yet in Firebase console.",
}


class AuthError(Exception):
    pass


def firebase_api_key(config_file: str = FIREBASE_CONFIG_FILE) -> str:
    """Reads the Firebase web apiKey from firebase_config.json."""
    path = Path(config_file)
    if not path.exists():
        raise AuthError(f"{path} not found. Please provide your Firebase web config.")
    cfg = json.loads(path.read_text(encoding="utf-8"))
    api_key = cfg.get("apiKey")
    if not api_key:
        raise AuthError(f"{path} is missing 'apiKey'.")
    return api_key


def load_session(session_file: str = SESSION_FILE) -> Optional[Dict[str, Any]]:
    """Loads cached session from disk."""
    path = Path(session_file)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_session(session: Dict[str, Any], session_file: str = SESSION_FILE) -> None:
    """Saves session tokens to disk."""
    Path(session_file).write_text(json.dumps(session, indent=2), encoding="utf-8")


def sign_out(session_file: str = SESSION_FILE) -> None:
    """Removes cached session."""
    Path(session_file).unlink(missing_ok=True)


def current_profile() -> Optional[Dict[str, Any]]:
    """Returns cached {uid, email} without making network calls."""
    session = load_session()
    if not session:
        return None
    return {"uid": session.get("uid"), "email": session.get("email")}


def raise_for_identity_error(resp: requests.Response) -> None:
    """Translates Firebase Identity Toolkit error response codes."""
    try:
        data = resp.json()
        code = data.get("error", {}).get("message", "")
        # Strip trailing context like ' : INVALID_LOGIN_CREDENTIALS'
        base_code = code.split(" : ")[0].split()[0] if code else ""
        msg = _ERROR_MESSAGES.get(base_code, code or f"HTTP {resp.status_code}")
    except Exception:
        msg = f"HTTP {resp.status_code}: {resp.text[:120]}"
    raise AuthError(msg)


def sign_in_with_password(email: str, password: str) -> Dict[str, Any]:
    """Authenticates an existing user via email & password."""
    api_key = firebase_api_key()
    url = f"{IDENTITY_TOOLKIT_BASE}:signInWithPassword?key={api_key}"
    resp = requests.post(url, json={"email": email.strip(), "password": password, "returnSecureToken": True}, timeout=20)
    if not resp.ok:
        raise_for_identity_error(resp)
    data = resp.json()
    session = {
        "uid": data["localId"],
        "email": data.get("email", email.strip()),
        "refresh_token": data["refreshToken"],
    }
    save_session(session)
    return {"uid": session["uid"], "email": session["email"], "id_token": data["idToken"]}


def sign_up_with_password(email: str, password: str) -> Dict[str, Any]:
    """Creates a new user account via email & password."""
    api_key = firebase_api_key()
    url = f"{IDENTITY_TOOLKIT_BASE}:signUp?key={api_key}"
    resp = requests.post(url, json={"email": email.strip(), "password": password, "returnSecureToken": True}, timeout=20)
    if not resp.ok:
        raise_for_identity_error(resp)
    data = resp.json()
    session = {
        "uid": data["localId"],
        "email": data.get("email", email.strip()),
        "refresh_token": data["refreshToken"],
    }
    save_session(session)
    return {"uid": session["uid"], "email": session["email"], "id_token": data["idToken"]}


def get_valid_id_token() -> Tuple[Optional[str], Optional[str]]:
    """
    Exchanges the cached refresh_token for a fresh short-lived ID token (~1h).
    Returns (id_token, uid) or (None, None).
    """
    session = load_session()
    if not session or not session.get("refresh_token"):
        return None, None
    try:
        api_key = firebase_api_key()
    except Exception:
        return None, None

    url = f"{SECURE_TOKEN_URL}?key={api_key}"
    try:
        resp = requests.post(url, data={"grant_type": "refresh_token", "refresh_token": session["refresh_token"]}, timeout=20)
        if not resp.ok:
            if resp.status_code in (400, 401):
                sign_out()
            return None, None
        data = resp.json()
        if "refresh_token" in data and data["refresh_token"] != session["refresh_token"]:
            session["refresh_token"] = data["refresh_token"]
            save_session(session)
        return data["id_token"], session["uid"]
    except Exception:
        return None, None
