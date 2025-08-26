# coding: utf-8
from typing import List, Dict, Iterable
import httpx
from bs4 import BeautifulSoup

import core.config as cfg
from core.logger import log

# ---------------- Const / Config ----------------
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)

DUCKDUCKGO_HTML_BASE = getattr(cfg, "DUCKDUCKGO_HTML_BASE", "https://html.duckduckgo.com/html/")
DDG_LITE_BASE = "https://lite.duckduckgo.com/lite/"
STARTPAGE_HTML = "https://www.startpage.com/sp/search"

SOURCE_SITES = getattr(cfg, "SOURCE_SITES", [
    "pravo.gov.ru", "consultant.ru", "base.garant.ru", "sudact.ru", "publication.pravo.gov.ru"
])
SEARCH_MAX_RESULTS = int(getattr(cfg, "SEARCH_MAX_RESULTS", 8))

GOOGLE_API_KEY = getattr(cfg, "GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = getattr(cfg, "GOOGLE_CSE_ID", "")
STARTPAGE_ENABLED = bool(getattr(cfg, "STARTPAGE_ENABLED", False))

SEARXNG_URL = getattr(cfg, "SEARXNG_URL", "")
SEARXNG_ENABLED = bool(getattr(cfg, "SEARXNG_ENABLED", False))

DISABLE_DDG = bool(getattr(cfg, "DISABLE_DDG", False))

HTTP_TIMEOUT_SECONDS = int(getattr(cfg, "HTTP_TIMEOUT_SECONDS", 15))


# ---------------- HTTP helper ----------------
def _http_get(url: str, params: Dict | None = None, headers: Dict | None = None) -> str:
    h = {"User-Agent": UA, "Accept-Language": "ru,en;q=0.9"}
    if headers:
        h.update(headers)
    r = httpx.get(
        url,
        params=params or {},
        headers=h,
        timeout=HTTP_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    r.raise_for_status()
    return r.text


# ---------------- Google Custom Search JSON API ----------------
def _google_cse_query(q: str) -> List[Dict]:
    if not (GOOGLE_API_KEY and GOOGLE_CSE_ID):
        return []
    try:
        params = {"key": GOOGLE_API_KEY, "cx": GOOGLE_CSE_ID, "q": q, "hl": "ru"}
        r = httpx.get(
            "https://www.googleapis.com/customsearch/v1",
            params=params,
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        r.raise_for_status()
        j = r.json()
        out: List[Dict] = []
        for item in j.get("items", []) or []:
            out.append({
                "title": item.get("title") or "",
                "url": item.get("link") or "",
                "snippet": item.get("snippet") or "",
            })
            if len(out) >= SEARCH_MAX_RESULTS:
                break
        log.info("Google CSE results: %d", len(out))
        return out
    except Exception as e:
        log.warning("Google CSE failed: %s", e)
        return []


# ---------------- SearXNG (JSON) ----------------
def _searxng_query(q: str) -> List[Dict]:
    if not (SEARXNG_ENABLED and SEARXNG_URL):
        return []
    try:
        headers = {
            "User-Agent": UA,
            "Accept": "application/json",
            # ниже — чтобы пройти локальный botdetection/trusted_proxies
            "X-Real-IP": "127.0.0.1",
            # "X-Forwarded-For": "127.0.0.1",  # при необходимости
        }
        params = {
            "q": q,
            "format": "json",
            "language": "ru",
            # можно добавить категории/диапазон по желанию:
            # "categories": "general",
            # "time_range": "year",
            # "safesearch": 0,
        }
        r = httpx.get(
            f"{SEARXNG_URL.rstrip('/')}/search",
            params=params,
            headers=headers,
            timeout=HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        r.raise_for_status()
        j = r.json()
        out: List[Dict] = []
        for item in j.get("results", []) or []:
            out.append({
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "snippet": item.get("content") or "",
            })
            if len(out) >= SEARCH_MAX_RESULTS:
                break
        log.info("SearXNG results: %d", len(out))
        return out
    except Exception as e:
        log.warning("SearXNG failed: %s", e)
        return []


# ---------------- DuckDuckGo (HTML + Lite) fallback ----------------
def _parse_ddg_html(text: str) -> List[Dict]:
    soup = BeautifulSoup(text, "lxml")
    out: List[Dict] = []
    # новая/старая разметка
    for a in soup.select(".result__a, a.result__a"):
        title = a.get_text(" ", strip=True)
        url = a.get("href")
        if not url:
            continue
        # пытаемся вытащить сниппет
        parent = a.find_parent()
        snippet_el = parent.select_one(".result__snippet, .result__snippet.js-result-snippet") if parent else None
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
        out.append({"title": title, "url": url, "snippet": snippet})
        if len(out) >= SEARCH_MAX_RESULTS:
            break
    return out


def _parse_ddg_lite(text: str) -> List[Dict]:
    soup = BeautifulSoup(text, "lxml")
    out: List[Dict] = []
    for td in soup.select("td.result-link"):
        a = td.select_one("a[href]")
        if not a:
            continue
        title = a.get_text(" ", strip=True)
        url = a.get("href")
        tr = td.find_parent("tr")
        snippet = ""
        if tr:
            nxt = tr.find_next_sibling("tr")
            if nxt:
                s_td = nxt.select_one("td.result-snippet")
                if s_td:
                    snippet = s_td.get_text(" ", strip=True)
        out.append({"title": title, "url": url, "snippet": snippet})
        if len(out) >= SEARCH_MAX_RESULTS:
            break
    return out


def _ddg_query_any(q: str) -> List[Dict]:
    if DISABLE_DDG:
        return []
    # сначала html, потом lite
    try:
        html = _http_get(DUCKDUCKGO_HTML_BASE, params={"q": q})
        out = _parse_ddg_html(html)
        if out:
            return out[:SEARCH_MAX_RESULTS]
    except Exception as e:
        log.warning("DDG html failed: %s", e)
    try:
        lite = _http_get(DDG_LITE_BASE, params={"q": q})
        out = _parse_ddg_lite(lite)
        if out:
            return out[:SEARCH_MAX_RESULTS]
    except Exception as e:
        log.warning("DDG lite failed: %s", e)
    return []


# ---------------- Startpage (HTML) fallback ----------------
def _startpage_query(q: str) -> List[Dict]:
    if not STARTPAGE_ENABLED:
        return []
    try:
        params = {"query": q, "cat": "web", "language": "ru_RU"}
        html = _http_get(
            STARTPAGE_HTML,
            params=params,
            headers={"Referer": "https://www.startpage.com/"},
        )
        soup = BeautifulSoup(html, "lxml")
        out: List[Dict] = []
        for res in soup.select("a.result-link"):
            title = res.get_text(" ", strip=True)
            url = res.get("href") or ""
            if not url:
                continue
            out.append({"title": title, "url": url, "snippet": ""})
            if len(out) >= SEARCH_MAX_RESULTS:
                break
        log.info("Startpage results: %d", len(out))
        return out
    except Exception as e:
        log.warning("Startpage failed: %s", e)
        return []


# ---------------- Utilities ----------------
def _with_sites(q: str) -> str:
    if not SOURCE_SITES:
        return q
    sites = " OR ".join([f"site:{s}" for s in SOURCE_SITES])
    return f"{q} {sites}".strip()


def _dedup(results: List[Dict]) -> List[Dict]:
    seen = set()
    out: List[Dict] = []
    for r in results:
        u = (r.get("url") or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(r)
        if len(out) >= SEARCH_MAX_RESULTS:
            break
    return out


# ---------------- Public API ----------------
def multi_query_search(queries: Iterable[str]) -> List[Dict]:
    """
    Приоритет:
    1) Google CSE (если ключи есть) — strict (с site:) и broad
    2) SearXNG (если включён) — strict и broad
    3) DuckDuckGo (HTML/Lite) — fallback
    4) Startpage (HTML) — дополнительный fallback
    """
    all_results: List[Dict] = []

    def run_phase(label: str, fn, q: str):
        nonlocal all_results
        try:
            res = fn(q) or []
            if res:
                log.info("%s hits: %d", label, len(res))
                all_results += res
        except Exception as e:
            log.warning("%s failed: %s", label, e)

    for q in queries:
        strict_q = _with_sites(q)

        # Google CSE
        if GOOGLE_API_KEY and GOOGLE_CSE_ID:
            run_phase("Google CSE strict", _google_cse_query, strict_q)
            if len(all_results) < SEARCH_MAX_RESULTS:
                run_phase("Google CSE broad", _google_cse_query, q)

        # SearXNG
        if SEARXNG_ENABLED and SEARXNG_URL and len(all_results) < SEARCH_MAX_RESULTS:
            run_phase("SearXNG strict", _searxng_query, strict_q)
            if len(all_results) < SEARCH_MAX_RESULTS:
                run_phase("SearXNG broad", _searxng_query, q)

        # DDG
        if len(all_results) < SEARCH_MAX_RESULTS:
            run_phase("DDG any strict", _ddg_query_any, strict_q)
            if len(all_results) < SEARCH_MAX_RESULTS:
                run_phase("DDG any broad", _ddg_query_any, q)

        # Startpage
        if STARTPAGE_ENABLED and len(all_results) < SEARCH_MAX_RESULTS:
            run_phase("Startpage strict", _startpage_query, strict_q)
            if len(all_results) < SEARCH_MAX_RESULTS:
                run_phase("Startpage broad", _startpage_query, q)

        if len(all_results) >= SEARCH_MAX_RESULTS:
            break

    out = _dedup(all_results)
    log.info("Search total results (dedup): %d", len(out))
    return out
