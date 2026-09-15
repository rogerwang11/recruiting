"""Resolve an app-only bearer token.

The developer console shows two different credentials, and which one you land on
depends on where you click. The bearer token is displayed once and easy to miss;
the API Key / API Key Secret pair is shown prominently and can be regenerated at
will. Either works here: the pair mints a bearer token through the OAuth 2.0
client-credentials flow, which is free and does not count against read billing.
"""

from __future__ import annotations

import base64
import urllib.parse

import requests

TOKEN_URL = "https://api.x.com/oauth2/token"


class AuthError(Exception):
    """Raised when credentials are missing or rejected by X."""


def bearer_from_key_pair(api_key: str, api_secret: str, timeout: int = 30) -> str:
    """Exchange an API Key / Secret pair for an app-only bearer token."""
    # X requires each half to be percent-encoded before the pair is joined and
    # base64'd — a secret containing a reserved character breaks otherwise.
    encoded = ":".join(
        urllib.parse.quote(part, safe="") for part in (api_key, api_secret)
    )
    credentials = base64.b64encode(encoded.encode()).decode()

    response = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        },
        data={"grant_type": "client_credentials"},
        timeout=timeout,
    )

    if response.status_code == 403:
        raise AuthError(
            "403 exchanging the key pair for a bearer token. The app is usually "
            "not attached to a Project, or the project has no credits."
        )
    if not response.ok:
        raise AuthError(
            f"{response.status_code} exchanging the key pair: {response.text[:200]}"
        )

    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise AuthError(f"No access_token in X's response: {payload}")
    return token
