"""
Downloader for wp.lutemusic.org / lutemusic.org.

Tab files live at:  https://lutemusic.org/tabs/composers/{Composer}/{filename}.tab
Directory listing:  https://lutemusic.org/tabs/composers/{Composer}/

Search (returns piece-page URLs):
  https://wp.lutemusic.org/?s={query}&post_type=setting
"""

from __future__ import annotations
import re
import urllib.request
import urllib.parse
from pathlib import Path

_TAB_BASE = "https://lutemusic.org/tabs/composers"
_PDF_BASE = "https://lutemusic.org/composers"
_SEARCH_BASE = "https://wp.lutemusic.org"


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "lute-tab-analyzer/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "lute-tab-analyzer/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def list_composer_tabs(composer: str) -> list[str]:
    """
    Return a list of .tab filenames (without path) available for a composer.
    composer should match the directory name on the server, e.g. "Dowland".
    """
    url = f"{_TAB_BASE}/{composer}/"
    html = _fetch(url)
    # Parse hrefs ending in .tab from the Apache directory listing
    return sorted(set(re.findall(r'href="([^"]+\.tab)"', html, re.IGNORECASE)))


def download_tab(composer: str, filename: str, dest_dir: str | Path = ".") -> Path:
    """
    Download a single .tab file and save it to dest_dir.
    filename may include or omit the .tab extension.
    Returns the local Path of the saved file.
    """
    if not filename.lower().endswith(".tab"):
        filename += ".tab"
    url = f"{_TAB_BASE}/{composer}/{filename}"
    content = _fetch(url)
    dest = Path(dest_dir) / filename
    dest.write_text(content, encoding="utf-8")
    return dest


def download_pdf(composer: str, filename: str, dest_dir: str | Path = ".") -> Path:
    """
    Download the PDF for a piece and save it to dest_dir.
    filename may include or omit the .tab or .pdf extension.
    Returns the local Path of the saved file.

    Strategy:
      1. Try the direct URL (same path as .tab but with .pdf extension).
      2. If that fails (404 / error), search for the piece by name and scrape the
         WordPress piece page for any href ending in .pdf.
    """
    import urllib.error

    stem = re.sub(r"\.(tab|pdf)$", "", filename, flags=re.IGNORECASE)
    pdf_name = stem + ".pdf"
    dest = Path(dest_dir) / pdf_name

    # Strategy 1: known PDF URL pattern (lutemusic.org/composers/{Composer}/pdf/{stem}.pdf)
    direct_url = f"{_PDF_BASE}/{composer}/pdf/{pdf_name}"
    try:
        data = _fetch_bytes(direct_url)
        dest.write_bytes(data)
        return dest
    except (urllib.error.HTTPError, urllib.error.URLError):
        pass

    # Strategy 2: search WordPress and scrape the piece page for a .pdf href
    search_query = stem.replace("_", " ")
    results = search_pieces(search_query)
    for result in results:
        try:
            page_html = _fetch(result["url"])
        except Exception:
            continue
        pdf_hrefs = re.findall(r'href="([^"]+\.pdf)"', page_html, re.IGNORECASE)
        if pdf_hrefs:
            data = _fetch_bytes(pdf_hrefs[0])
            dest.write_bytes(data)
            return dest

    raise FileNotFoundError(
        f"Could not locate a PDF for {composer}/{stem}. "
        f"Tried {direct_url} and searched WordPress pages."
    )


def search_pieces(query: str) -> list[dict]:
    """
    Search wp.lutemusic.org and return a list of dicts with keys:
      title, url
    """
    params = urllib.parse.urlencode({"s": query, "post_type": "setting"})
    html = _fetch(f"{_SEARCH_BASE}/?{params}")

    results = []
    # Extract piece links from search result anchors
    for m in re.finditer(
        r'<a[^>]+href="(https://wp\.lutemusic\.org/music-piece/[^"]+)"[^>]*>(.*?)</a>',
        html,
        re.IGNORECASE | re.DOTALL,
    ):
        href = m.group(1)
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if title and href not in [r["url"] for r in results]:
            results.append({"title": title, "url": href})

    return results
