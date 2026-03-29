"""Scrapling: use Fetcher.get for static HTTP. For protected sites install scrapling[fetchers] and consider StealthyFetcher."""

from __future__ import annotations

def scrape_url_to_text(url: str, *, max_chars: int = 6000) -> str:
    try:
        from scrapling.fetchers import Fetcher
    except Exception as e:  # pragma: no cover
        return f"[scrapling_unavailable] {e}"

    try:
        page = Fetcher.get(url)
        text = page.css("body::text").getall()
        blob = "\n".join(t.strip() for t in text if t and t.strip())
        return blob[:max_chars] if blob else page.text[:max_chars]
    except Exception as e:
        return f"[scrape_error] {e}"