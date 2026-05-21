"""
papers_helper.py
================
Find research papers for a thesis topic across arXiv, Semantic Scholar, and
Google Scholar, then use an offline Ollama model to rank, summarize, and
extract key info from each — and propose a literature-review outline.

Outputs a Markdown report and (optionally) downloads open-access PDFs.

Run:
    python papers_helper.py
    python papers_helper.py "graph neural networks for drug discovery" --limit 8 --no-scholar

Requires:
    pip install requests selenium
    Ollama running locally with a model pulled, e.g.:
        ollama pull gemma3:4b
        ollama serve
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable

import requests

# Make emoji / non-ASCII safe on Windows consoles (cp1252 → utf-8).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ------------------------------ CONFIG ------------------------------

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "gemma3:4b"
OLLAMA_TIMEOUT = 300  # seconds per request

ARXIV_API = "http://export.arxiv.org/api/query"
SEMANTIC_API = "https://api.semanticscholar.org/graph/v1/paper/search"
OPENALEX_API = "https://api.openalex.org/works"
SCHOLAR_URL = "https://scholar.google.com/scholar"
OPENALEX_MAILTO = "researcher@example.com"  # put your email here for the polite pool

OUTPUT_ROOT = Path(__file__).resolve().parent / "papers_out"
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; papers_helper/1.0; +https://example.com/research)",
    "Accept": "application/json, application/atom+xml, text/html",
}


def _request_with_retry(url: str, *, label: str, attempts: int = 4, base_wait: float = 4.0) -> requests.Response | None:
    """GET with exponential backoff on 429 / 5xx / network errors."""
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            r = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 500, 502, 503, 504):
                wait = base_wait * (2 ** i)
                print(f"  {label}: HTTP {r.status_code}, retrying in {wait:.0f}s ({i + 1}/{attempts})")
                time.sleep(wait)
                continue
            body = (r.text or "")[:300].replace("\n", " ")
            print(f"  {label}: HTTP {r.status_code} — giving up. body={body}")
            return None
        except Exception as exc:
            last_exc = exc
            wait = base_wait * (2 ** i)
            print(f"  {label}: network error {exc!r}, retrying in {wait:.0f}s")
            time.sleep(wait)
    if last_exc:
        print(f"  {label}: exhausted retries ({last_exc!r})")
    return None


# ------------------------------ DATA --------------------------------


@dataclass
class Paper:
    source: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    abstract: str = ""
    url: str = ""
    pdf_url: str | None = None
    relevance: float | None = None
    summary: str = ""
    key_info: dict = field(default_factory=dict)

    def cite_key(self) -> str:
        first_author = (self.authors[0].split()[-1] if self.authors else "anon").lower()
        first_author = re.sub(r"[^a-z]", "", first_author) or "anon"
        first_word = re.findall(r"[A-Za-z]+", self.title or "paper")
        keyword = (first_word[0] if first_word else "paper").lower()
        return f"{first_author}{self.year or ''}{keyword}"[:40]


# --------------------------- SEARCHERS ------------------------------


def search_arxiv(query: str, limit: int = 8) -> list[Paper]:
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": limit,
        "sortBy": "relevance",
    }
    url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"
    print(f"  arxiv: GET {url}")
    r = _request_with_retry(url, label="arxiv")
    if r is None:
        return []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(r.text)
    out = []
    for entry in root.findall("a:entry", ns):
        title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
        if not title:
            continue
        summary = (entry.findtext("a:summary", default="", namespaces=ns) or "").strip()
        link_html = ""
        link_pdf = None
        for link in entry.findall("a:link", ns):
            href = link.get("href", "")
            if link.get("title") == "pdf":
                link_pdf = href
            elif link.get("rel") == "alternate":
                link_html = href
        published = entry.findtext("a:published", default="", namespaces=ns)
        year = int(published[:4]) if published[:4].isdigit() else None
        authors = [a.findtext("a:name", default="", namespaces=ns).strip()
                   for a in entry.findall("a:author", ns)]
        out.append(Paper(
            source="arXiv",
            title=title,
            authors=[a for a in authors if a],
            year=year,
            venue="arXiv",
            abstract=summary,
            url=link_html or link_pdf or "",
            pdf_url=link_pdf,
        ))
    print(f"  arxiv: {len(out)} results")
    return out


def search_openalex(query: str, limit: int = 8) -> list[Paper]:
    """OpenAlex (https://openalex.org) — generous free limits, no key required."""
    params = {
        "search": query,
        "per-page": min(limit, 25),
        "select": "id,title,abstract_inverted_index,authorships,publication_year,doi,open_access,primary_location",
        "mailto": OPENALEX_MAILTO,
    }
    url = f"{OPENALEX_API}?{urllib.parse.urlencode(params)}"
    print(f"  openalex: GET {url}")
    r = _request_with_retry(url, label="openalex", attempts=3, base_wait=3.0)
    if r is None:
        return []
    out: list[Paper] = []
    for w in r.json().get("results", []):
        title = w.get("title") or ""
        if not title:
            continue
        abstract = _inverted_index_to_text(w.get("abstract_inverted_index"))
        authors = [a.get("author", {}).get("display_name", "") for a in (w.get("authorships") or [])]
        primary = w.get("primary_location") or {}
        venue = (primary.get("source") or {}).get("display_name")
        pdf_url = (w.get("open_access") or {}).get("oa_url") or primary.get("pdf_url")
        doi = w.get("doi")
        link = doi if doi and doi.startswith("http") else (f"https://doi.org/{doi}" if doi else (w.get("id") or ""))
        out.append(Paper(
            source="OpenAlex",
            title=title,
            authors=[a for a in authors if a],
            year=w.get("publication_year"),
            venue=venue,
            abstract=abstract,
            url=link,
            pdf_url=pdf_url,
        ))
    print(f"  openalex: {len(out)} results")
    return out


def _inverted_index_to_text(idx: dict | None) -> str:
    """OpenAlex stores abstracts as {word: [positions]}; reconstruct linear text."""
    if not idx:
        return ""
    positions: list[tuple[int, str]] = []
    for word, locs in idx.items():
        for loc in locs:
            positions.append((loc, word))
    positions.sort()
    return " ".join(w for _, w in positions)


def search_semantic_scholar(query: str, limit: int = 8) -> list[Paper]:
    fields = "title,abstract,authors,year,venue,url,openAccessPdf,externalIds"
    params = {"query": query, "limit": limit, "fields": fields}
    url = f"{SEMANTIC_API}?{urllib.parse.urlencode(params)}"
    print(f"  semantic: GET {url}")
    r = _request_with_retry(url, label="semantic", attempts=2, base_wait=4.0)
    if r is None:
        return []
    out = []
    for d in r.json().get("data", []):
        out.append(Paper(
            source="Semantic Scholar",
            title=d.get("title") or "",
            authors=[a.get("name", "") for a in (d.get("authors") or [])],
            year=d.get("year"),
            venue=d.get("venue"),
            abstract=d.get("abstract") or "",
            url=d.get("url") or "",
            pdf_url=(d.get("openAccessPdf") or {}).get("url"),
        ))
    print(f"  semantic: {len(out)} results")
    return out


def search_google_scholar(query: str, limit: int = 8) -> list[Paper]:
    """
    Uses Selenium because Scholar has no public API. May trigger CAPTCHA; on
    failure we just return [] so the rest of the pipeline still works.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
    except Exception as exc:
        print(f"  scholar: selenium unavailable ({exc})")
        return []

    print(f"  scholar: launching Chrome for {query!r}")
    driver = webdriver.Chrome()
    try:
        driver.get(f"{SCHOLAR_URL}?q={urllib.parse.quote(query)}")
        time.sleep(2.5)
        if "captcha" in driver.page_source.lower() or "unusual traffic" in driver.page_source.lower():
            print("  scholar: blocked by CAPTCHA — solve in the window, then press Enter here.")
            try:
                input()
            except EOFError:
                pass
        results = []
        cards = driver.find_elements(By.CSS_SELECTOR, "div.gs_r.gs_or.gs_scl")
        for c in cards[:limit]:
            try:
                title_el = c.find_element(By.CSS_SELECTOR, "h3.gs_rt")
                title = title_el.text.strip()
                link = ""
                anchor = title_el.find_elements(By.TAG_NAME, "a")
                if anchor:
                    link = anchor[0].get_attribute("href") or ""
                meta = ""
                meta_els = c.find_elements(By.CSS_SELECTOR, "div.gs_a")
                if meta_els:
                    meta = meta_els[0].text.strip()
                snippet = ""
                snip_els = c.find_elements(By.CSS_SELECTOR, "div.gs_rs")
                if snip_els:
                    snippet = snip_els[0].text.strip()
                pdf_link = None
                pdf_els = c.find_elements(By.CSS_SELECTOR, "div.gs_or_ggsm a")
                if pdf_els:
                    pdf_link = pdf_els[0].get_attribute("href")
                year_match = re.search(r"\b(19|20)\d{2}\b", meta)
                authors_part = meta.split(" - ")[0] if " - " in meta else meta
                authors = [a.strip() for a in re.split(r",| and ", authors_part) if a.strip()]
                results.append(Paper(
                    source="Google Scholar",
                    title=title,
                    authors=authors,
                    year=int(year_match.group()) if year_match else None,
                    venue=meta.split(" - ")[1] if " - " in meta else None,
                    abstract=snippet,
                    url=link,
                    pdf_url=pdf_link,
                ))
            except Exception:
                continue
        print(f"  scholar: {len(results)} results")
        return results
    finally:
        try:
            driver.quit()
        except Exception:
            pass


# --------------------------- DEDUP ----------------------------------


def _normalize_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", t.lower())


def dedupe(papers: Iterable[Paper]) -> list[Paper]:
    seen: dict[str, Paper] = {}
    for p in papers:
        key = _normalize_title(p.title)[:80]
        if not key:
            continue
        if key in seen:
            cur = seen[key]
            if not cur.abstract and p.abstract:
                cur.abstract = p.abstract
            if not cur.pdf_url and p.pdf_url:
                cur.pdf_url = p.pdf_url
            if not cur.year and p.year:
                cur.year = p.year
        else:
            seen[key] = p
    return list(seen.values())


# --------------------------- OLLAMA ---------------------------------


def ollama(prompt: str, *, model: str = OLLAMA_MODEL, json_only: bool = False) -> str:
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2 if json_only else 0.4},
    }
    if json_only:
        body["format"] = "json"
    r = requests.post(f"{OLLAMA_URL}/api/generate", json=body, timeout=OLLAMA_TIMEOUT)
    r.raise_for_status()
    return r.json().get("response", "").strip()


def _safe_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).rstrip("`").strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                return {}
    return {}


def llm_rank(paper: Paper, topic: str) -> float:
    prompt = (
        f"You are helping a researcher decide which papers to read for a thesis "
        f"on: \"{topic}\".\n\n"
        f"Paper title: {paper.title}\n"
        f"Year: {paper.year}\n"
        f"Abstract: {paper.abstract[:1800]}\n\n"
        "On a scale of 1 to 10, how relevant is this paper to the thesis topic? "
        "Return STRICT JSON: {\"score\": <int 1-10>, \"reason\": \"<short reason>\"}."
    )
    try:
        data = _safe_json(ollama(prompt, json_only=True))
        score = float(data.get("score", 5))
        return max(0.0, min(10.0, score))
    except Exception as exc:
        print(f"    rank failed for {paper.title[:50]!r}: {exc}")
        return 5.0


def llm_summarize(paper: Paper) -> str:
    if not paper.abstract:
        return ""
    prompt = (
        "Summarize the following research-paper abstract in 2-3 sentences. "
        "Plain prose, no bullets, no preamble.\n\n"
        f"Title: {paper.title}\nAbstract: {paper.abstract[:2200]}"
    )
    try:
        return ollama(prompt)
    except Exception as exc:
        print(f"    summary failed: {exc}")
        return ""


def llm_extract(paper: Paper) -> dict:
    if not paper.abstract:
        return {}
    prompt = (
        "Extract structured info from this paper. Return STRICT JSON with keys: "
        "method, dataset, results, limitations. Use short strings; use \"\" if unknown.\n\n"
        f"Title: {paper.title}\nAbstract: {paper.abstract[:2200]}"
    )
    try:
        data = _safe_json(ollama(prompt, json_only=True))
        return {k: str(data.get(k, "")).strip() for k in ("method", "dataset", "results", "limitations")}
    except Exception as exc:
        print(f"    extract failed: {exc}")
        return {}


def llm_outline(topic: str, papers: list[Paper]) -> str:
    bulleted = "\n".join(
        f"- ({p.relevance or '?'}) {p.title} ({p.year}) — {p.summary[:200]}"
        for p in papers[:15]
    )
    prompt = (
        f"You are helping draft a literature review on \"{topic}\".\n"
        f"Here are the most relevant papers (relevance / title / year / summary):\n\n"
        f"{bulleted}\n\n"
        "Propose a literature-review outline with 4-6 thematic sections. For each "
        "section, give a 1-sentence description and list the titles of papers that "
        "belong in it. Use Markdown headings."
    )
    try:
        return ollama(prompt)
    except Exception as exc:
        return f"_Outline generation failed: {exc}_"


# --------------------------- PDF ------------------------------------


def download_pdf(url: str | None, dst: Path) -> bool:
    if not url:
        return False
    try:
        with requests.get(url, headers=REQUEST_HEADERS, stream=True, timeout=30, allow_redirects=True) as r:
            ctype = r.headers.get("Content-Type", "")
            if r.status_code != 200 or "pdf" not in ctype.lower():
                return False
            dst.parent.mkdir(parents=True, exist_ok=True)
            with open(dst, "wb") as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        f.write(chunk)
        return True
    except Exception as exc:
        print(f"    pdf download failed for {url}: {exc}")
        return False


# --------------------------- REPORT ---------------------------------


def render_markdown(topic: str, papers: list[Paper], outline: str) -> str:
    lines: list[str] = []
    lines.append(f"# Literature search: {topic}\n")
    lines.append(f"_Generated by papers_helper.py — {len(papers)} papers after dedup._\n")
    lines.append("## Suggested outline\n")
    lines.append(outline.strip() + "\n")
    lines.append("## Papers (ranked by LLM relevance)\n")
    for i, p in enumerate(papers, 1):
        lines.append(f"### {i}. {p.title}")
        meta_bits = []
        if p.authors:
            meta_bits.append(", ".join(p.authors[:6]) + (" et al." if len(p.authors) > 6 else ""))
        if p.year:
            meta_bits.append(str(p.year))
        if p.venue:
            meta_bits.append(p.venue)
        meta_bits.append(f"source: {p.source}")
        lines.append("_" + " · ".join(meta_bits) + "_")
        if p.relevance is not None:
            lines.append(f"**Relevance:** {p.relevance:.1f} / 10")
        if p.summary:
            lines.append(f"**Summary.** {p.summary}")
        if p.key_info:
            for k in ("method", "dataset", "results", "limitations"):
                v = p.key_info.get(k, "")
                if v:
                    lines.append(f"- **{k.capitalize()}:** {v}")
        if p.url:
            lines.append(f"- Link: <{p.url}>")
        if p.pdf_url:
            lines.append(f"- PDF: <{p.pdf_url}>")
        lines.append("")
    return "\n".join(lines)


# --------------------------- DRIVER ---------------------------------


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "topic"


def run(topic: str, limit: int, use_scholar: bool, download_pdfs: bool) -> Path:
    print(f"\n🔎 Topic: {topic}")
    print(f"   limit per source: {limit}  scholar: {use_scholar}  pdfs: {download_pdfs}\n")

    all_papers: list[Paper] = []
    all_papers += search_openalex(topic, limit=limit)
    all_papers += search_arxiv(topic, limit=limit)
    all_papers += search_semantic_scholar(topic, limit=limit)
    if use_scholar:
        all_papers += search_google_scholar(topic, limit=limit)

    papers = dedupe(all_papers)
    print(f"\n📚 {len(papers)} unique papers after dedup")
    if not papers:
        print("No papers found. Try a different query.")
        sys.exit(1)

    print("\n🧠 Ranking & summarizing with Ollama (this is the slow part)...")
    for i, p in enumerate(papers, 1):
        print(f"  [{i}/{len(papers)}] {p.title[:75]}")
        p.relevance = llm_rank(p, topic)
        p.summary = llm_summarize(p)
        p.key_info = llm_extract(p)

    papers.sort(key=lambda x: x.relevance or 0.0, reverse=True)

    print("\n🗺  Generating outline...")
    outline = llm_outline(topic, papers)

    out_dir = OUTPUT_ROOT / slugify(topic)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "report.md"
    report_path.write_text(render_markdown(topic, papers, outline), encoding="utf-8")
    (out_dir / "papers.json").write_text(
        json.dumps([asdict(p) for p in papers], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if download_pdfs:
        pdf_dir = out_dir / "pdfs"
        print(f"\n📥 Downloading PDFs to {pdf_dir}...")
        ok = 0
        for p in papers:
            if not p.pdf_url:
                continue
            name = (p.cite_key() or slugify(p.title)) + ".pdf"
            if download_pdf(p.pdf_url, pdf_dir / name):
                ok += 1
        print(f"   downloaded {ok} PDFs")

    print(f"\n✅ Done. Open {report_path}")
    return report_path


def main():
    ap = argparse.ArgumentParser(description="Find and analyze research papers with an offline LLM.")
    ap.add_argument("topic", nargs="?", help="Thesis topic / search query")
    ap.add_argument("--limit", type=int, default=8, help="Results per source (default 8)")
    ap.add_argument("--no-scholar", action="store_true", help="Skip Google Scholar (Selenium)")
    ap.add_argument("--no-pdfs", action="store_true", help="Don't download PDFs")
    args = ap.parse_args()

    topic = args.topic
    if not topic:
        try:
            topic = input("Thesis topic / search query: ").strip()
        except EOFError:
            topic = ""
    if not topic:
        print("No topic given.")
        sys.exit(1)

    run(
        topic=topic,
        limit=args.limit,
        use_scholar=not args.no_scholar,
        download_pdfs=not args.no_pdfs,
    )


if __name__ == "__main__":
    main()
