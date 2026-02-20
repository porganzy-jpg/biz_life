"""
HomeFinder - Property Data Scraper/Ingestion System
Automated scraping from Naver Real Estate and KB Real Estate,
with scheduling, deduplication, and auto-scoring.
"""

__all__ = [
    "NaverRealEstateScraper",
    "KBRealEstateScraper",
    "ScrapingScheduler",
    "map_naver_to_property",
    "map_kb_to_property",
]


def __getattr__(name):
    """Lazy imports to avoid circular import issues at module load time."""
    if name == "NaverRealEstateScraper":
        from backend.scraper.naver_scraper import NaverRealEstateScraper
        return NaverRealEstateScraper
    if name == "KBRealEstateScraper":
        from backend.scraper.kb_scraper import KBRealEstateScraper
        return KBRealEstateScraper
    if name == "ScrapingScheduler":
        from backend.scraper.scheduler import ScrapingScheduler
        return ScrapingScheduler
    if name == "map_naver_to_property":
        from backend.scraper.data_mapper import map_naver_to_property
        return map_naver_to_property
    if name == "map_kb_to_property":
        from backend.scraper.data_mapper import map_kb_to_property
        return map_kb_to_property
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
