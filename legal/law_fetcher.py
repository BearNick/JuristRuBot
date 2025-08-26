from typing import Dict
import httpx
from bs4 import BeautifulSoup
import re

FZ_EDIT_RE = re.compile(r"(ФЗ[\--]\d{1,4}[\--]ФЗ\s+от\s+\d{2}\.\d{2}\.\d{4})")

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

def fetch_page(url: str) -> Dict:
    r = httpx.get(url, timeout=25, follow_redirects=True, headers={
        "User-Agent": UA,
        "Accept-Language": "ru,en;q=0.9",
    })
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    for s in soup(["script", "style", "noscript"]):
        s.extract()
    text = soup.get_text(" ", strip=True)
    title = soup.title.get_text(strip=True) if soup.title else url

    edit_match = FZ_EDIT_RE.search(text)
    snippet = text[:1800]
    if edit_match:
        snippet = f"{edit_match.group(1)} — {snippet}"

    return {"url": url, "title": title, "text": text, "snippet": snippet}