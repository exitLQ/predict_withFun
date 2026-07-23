import openai_analyzer
from source_quality import assess_source, canonicalize_url


def test_url_canonicalization_removes_tracking_and_fragment():
    url = canonicalize_url(
        "https://www.reuters.com/world/story/?utm_source=x&id=7#section"
    )

    assert url == "https://reuters.com/world/story?id=7"


def test_source_categories_are_transparent():
    government = assess_source("https://example.gov/report", "Report")
    social = assess_source("https://x.com/user/status/1", "Post")

    assert government.category == "government"
    assert government.quality == "high"
    assert government.score == 0.95
    assert social.category == "social"
    assert social.quality == "low"


def test_extracted_sources_are_deduplicated_and_ranked():
    sources = openai_analyzer._extract_sources(
        {
            "items": [
                {
                    "title": "News",
                    "url": "https://www.reuters.com/story?utm_source=test",
                },
                {
                    "title": "Duplicate",
                    "url": "https://reuters.com/story#top",
                },
                {"title": "Post", "url": "https://x.com/user/status/1"},
            ]
        }
    )

    assert len(sources) == 2
    assert sources[0].domain == "reuters.com"
    assert sources[0].quality_score == 0.8
    assert sources[1].category == "social"
