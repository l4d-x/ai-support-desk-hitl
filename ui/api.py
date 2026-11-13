"""Thin client the Streamlit pages use to talk to the FastAPI backend.

The API key lives in Streamlit secrets and is only ever sent server-side (Streamlit runs the
Python), so it never reaches the visitor's browser.
"""

from __future__ import annotations

import os
import time

import requests
import streamlit as st


def _secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets[name])
    except Exception:  # no secrets file / missing key -> fall back to env vars
        return os.getenv(name, default)


API_URL = _secret("API_URL", "http://localhost:8000").rstrip("/")
API_KEY = _secret("API_KEY")
MAX_TICKETS_PER_SESSION = int(_secret("MAX_TICKETS_PER_SESSION", "5"))


class ApiError(Exception):
    """A problem with a user-friendly message."""


def wake_api(max_wait_s: int = 90) -> None:
    """Free hosts sleep when idle. Poll /health with a visible message until the API is up."""
    if st.session_state.get("api_awake"):
        return
    with st.status("Connecting to the support server...", expanded=True) as status:
        st.write(
            "The demo runs on a free tier that sleeps when idle. Waking it can take ~1 minute."
        )
        deadline = time.time() + max_wait_s
        while time.time() < deadline:
            try:
                if requests.get(f"{API_URL}/health", timeout=10).ok:
                    st.session_state.api_awake = True
                    status.update(label="Connected", state="complete", expanded=False)
                    return
            except requests.RequestException:
                pass
            time.sleep(3)
        status.update(label="The server did not respond", state="error")
    st.error("The support server is unavailable right now. Please try again in a minute.")
    st.stop()


def call(method: str, path: str, **kwargs):
    wake_api()
    try:
        res = requests.request(
            method, f"{API_URL}{path}", headers={"X-API-Key": API_KEY}, timeout=60, **kwargs
        )
    except requests.RequestException:
        st.session_state.api_awake = False
        raise ApiError("Could not reach the support server. Please try again.") from None

    if res.ok:
        return res.json()
    if res.status_code in (401, 503):
        raise ApiError("The app is not configured correctly (API key). Please tell the site owner.")
    try:
        detail = res.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, list):  # FastAPI validation errors
        detail = "Please check the form: " + "; ".join(
            d.get("msg", "invalid value") for d in detail
        )
    raise ApiError(detail or f"Unexpected error ({res.status_code}). Please try again.")
