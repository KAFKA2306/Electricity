import os

from scripts.collect_eia_electricity import build_url


def test_build_url_requires_key_and_carries_explicit_route_fields(monkeypatch):
    monkeypatch.setenv("EIA_API_KEY", "secret-key")
    url = build_url("electricity/rto/region-data", ["value"], "hourly", "2026-08-01T00", "2026-08-02T00", 100)
    assert "electricity/rto/region-data/data/" in url
    assert "data%5B0%5D=value" in url
    assert "frequency=hourly" in url
    assert "api_key=secret-key" in url


def test_build_url_fails_without_key(monkeypatch):
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    try:
        build_url("electricity/rto/region-data", ["value"], "hourly", None, None, 10)
    except RuntimeError as exc:
        assert "EIA_API_KEY" in str(exc)
    else:
        raise AssertionError("missing EIA_API_KEY must fail")
