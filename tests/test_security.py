import security


def test_security_headers_are_strict_and_production_adds_hsts():
    development = security.response_security_headers(False)
    production = security.response_security_headers(True)

    assert "default-src 'self'" in development["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in development["Content-Security-Policy"]
    assert "unsafe-inline" not in development["Content-Security-Policy"]
    assert development["X-Content-Type-Options"] == "nosniff"
    assert "Strict-Transport-Security" not in development
    assert production["Strict-Transport-Security"].startswith("max-age=31536000")
    assert "upgrade-insecure-requests" in production["Content-Security-Policy"]


def test_allowed_hosts_are_trimmed_and_empty_configuration_is_safe(monkeypatch):
    monkeypatch.setenv("ALLOWED_HOSTS", " example.com, *.example.org ")
    assert security.allowed_hosts() == ["example.com", "*.example.org"]

    monkeypatch.setenv("ALLOWED_HOSTS", " , ")
    assert "localhost" in security.allowed_hosts()
