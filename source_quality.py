from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
}
NEWS_DOMAINS = {
    "apnews.com",
    "bbc.com",
    "bbc.co.uk",
    "bloomberg.com",
    "economist.com",
    "ft.com",
    "nytimes.com",
    "reuters.com",
    "theguardian.com",
    "washingtonpost.com",
    "wsj.com",
}
INSTITUTIONAL_DOMAINS = {
    "europa.eu",
    "imf.org",
    "nato.int",
    "oecd.org",
    "un.org",
    "who.int",
    "worldbank.org",
}
SOCIAL_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "reddit.com",
    "tiktok.com",
    "x.com",
}


@dataclass(frozen=True)
class SourceAssessment:
    url: str
    domain: str
    category: str
    quality: str
    score: float
    reason: str


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").casefold()
    if host.startswith("www."):
        host = host[4:]
    port = f":{parsed.port}" if parsed.port else ""
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.casefold().startswith("utm_")
            and key.casefold() not in TRACKING_PARAMETERS
        ]
    )
    path = parsed.path.rstrip("/") or "/"
    return urlunparse(
        (
            parsed.scheme.casefold() or "https",
            f"{host}{port}",
            path,
            "",
            query,
            "",
        )
    )


def _matches(domain: str, candidates: set[str]) -> bool:
    return any(domain == item or domain.endswith(f".{item}") for item in candidates)


def assess_source(url: str, title: str) -> SourceAssessment:
    canonical_url = canonicalize_url(url)
    domain = (urlparse(canonical_url).hostname or "").casefold()
    title_lower = title.casefold()
    if domain.endswith((".gov", ".gov.uk", ".gv.at")):
        return SourceAssessment(
            canonical_url,
            domain,
            "government",
            "high",
            0.95,
            "Government domain; likely an authoritative primary source.",
        )
    if domain.endswith(".edu") or domain.endswith(".ac.uk"):
        return SourceAssessment(
            canonical_url,
            domain,
            "academic",
            "high",
            0.9,
            "Academic institution domain.",
        )
    if _matches(domain, INSTITUTIONAL_DOMAINS):
        return SourceAssessment(
            canonical_url,
            domain,
            "official",
            "high",
            0.9,
            "Recognized intergovernmental or institutional domain.",
        )
    if _matches(domain, NEWS_DOMAINS):
        return SourceAssessment(
            canonical_url,
            domain,
            "news",
            "high",
            0.8,
            "Established news organization domain.",
        )
    if _matches(domain, SOCIAL_DOMAINS):
        return SourceAssessment(
            canonical_url,
            domain,
            "social",
            "low",
            0.35,
            "Social content may be timely but requires independent verification.",
        )
    if any(term in title_lower for term in ("official", "press release", "statement")):
        return SourceAssessment(
            canonical_url,
            domain,
            "official",
            "medium",
            0.7,
            "Title indicates official material; domain is not on the trusted list.",
        )
    return SourceAssessment(
        canonical_url,
        domain,
        "other",
        "medium",
        0.5,
        "General web source; verify authorship and supporting evidence.",
    )
