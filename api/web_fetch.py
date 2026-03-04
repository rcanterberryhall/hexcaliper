import re

import httpx
from bs4 import BeautifulSoup

_URL_RE = re.compile(r"https?://[^\s<>\"{}|\\^`\[\]]{4,}")
MAX_CHARS = 3000
MAX_URLS = 3


def extract_urls(text: str) -> list[str]:
    return _URL_RE.findall(text)[:MAX_URLS]


_SSL_CA = "/etc/ssl/certs/ca-certificates.crt"


async def fetch_url(url: str) -> str | None:
    try:
        async with httpx.AsyncClient(
            timeout=15.0, follow_redirects=True, verify=_SSL_CA
        ) as client:
            resp = await client.get(
                url, headers={"User-Agent": "Mozilla/5.0 Hexcaliper/1.0"}
            )
        if not resp.is_success:
            return None
        ct = resp.headers.get("content-type", "")
        if "html" in ct:
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "aside"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
        else:
            text = resp.text
        return text[:MAX_CHARS]
    except Exception:
        return None


async def fetch_context(message: str) -> dict[str, str]:
    results: dict[str, str] = {}
    for url in extract_urls(message):
        content = await fetch_url(url)
        if content:
            results[url] = content
    return results
