import os


def allowed_hosts() -> list[str]:
    configured = os.getenv(
        "ALLOWED_HOSTS",
        "localhost,127.0.0.1,testserver",
    )
    hosts = [item.strip() for item in configured.split(",") if item.strip()]
    return hosts or ["localhost", "127.0.0.1", "testserver"]


def production_mode() -> bool:
    return os.getenv("ENVIRONMENT", "development").casefold() == "production"


def https_redirect_enabled() -> bool:
    default = "true" if production_mode() else "false"
    return os.getenv("HTTPS_REDIRECT", default).casefold() == "true"


def response_security_headers(production: bool | None = None) -> dict[str, str]:
    is_production = production_mode() if production is None else production
    directives = [
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        "script-src 'self'",
        "style-src 'self' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data:",
        "connect-src 'self'",
        "manifest-src 'self'",
    ]
    if is_production:
        directives.append("upgrade-insecure-requests")
    headers = {
        "Content-Security-Policy": "; ".join(directives),
        "Cross-Origin-Opener-Policy": "same-origin",
        "Permissions-Policy": (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        ),
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }
    if is_production:
        headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    return headers
