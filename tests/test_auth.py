"""Either credential shape from the developer console should work."""

import base64

import pytest

from xhire import auth, config


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self.ok = status_code < 400
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_key_pair_exchanges_for_a_bearer_token(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, data=None, timeout=None):
        captured.update(url=url, headers=headers, data=data)
        return FakeResponse(payload={"token_type": "bearer", "access_token": "AAAA123"})

    monkeypatch.setattr(auth.requests, "post", fake_post)
    token = auth.bearer_from_key_pair("mykey", "mysecret")

    assert token == "AAAA123"
    assert captured["data"] == {"grant_type": "client_credentials"}
    decoded = base64.b64decode(
        captured["headers"]["Authorization"].removeprefix("Basic ")
    ).decode()
    assert decoded == "mykey:mysecret"


def test_credentials_are_percent_encoded_before_encoding(monkeypatch):
    # A secret with a reserved character must not corrupt the pair.
    captured = {}
    monkeypatch.setattr(
        auth.requests,
        "post",
        lambda url, headers=None, data=None, timeout=None: (
            captured.update(headers=headers),
            FakeResponse(payload={"access_token": "AAAA"}),
        )[1],
    )
    auth.bearer_from_key_pair("key:with:colons", "secret/with+chars")

    decoded = base64.b64decode(
        captured["headers"]["Authorization"].removeprefix("Basic ")
    ).decode()
    assert decoded == "key%3Awith%3Acolons:secret%2Fwith%2Bchars"


def test_403_explains_the_usual_cause(monkeypatch):
    monkeypatch.setattr(
        auth.requests,
        "post",
        lambda *a, **kw: FakeResponse(status_code=403, text="forbidden"),
    )
    with pytest.raises(auth.AuthError, match="not attached to a Project"):
        auth.bearer_from_key_pair("k", "s")


def test_dotenv_bearer_token_is_used_directly(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# a comment\n\nX_BEARER_TOKEN=AAAAtoken\n")
    monkeypatch.setattr(config, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)

    assert config.bearer_token() == "AAAAtoken"


def test_dotenv_key_pair_triggers_an_exchange(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('X_API_KEY="abc"\nX_API_SECRET=def\n')
    monkeypatch.setattr(config, "REPO_ROOT", tmp_path)
    for var in ("X_BEARER_TOKEN", "X_API_KEY", "X_API_SECRET"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(auth, "bearer_from_key_pair", lambda k, s: f"minted:{k}:{s}")

    # Quotes around a value must be stripped before the exchange.
    assert config.bearer_token() == "minted:abc:def"


def test_missing_credentials_names_both_options(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REPO_ROOT", tmp_path)
    for var in ("X_BEARER_TOKEN", "X_API_KEY", "X_API_SECRET"):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(config.ConfigError) as exc:
        config.bearer_token()
    assert "X_BEARER_TOKEN" in str(exc.value)
    assert "X_API_KEY" in str(exc.value)
