#!/usr/bin/env python3
"""Thu thập có kiểm soát thơ chúc Tết công khai, lọc khổ Lục Bát 4 dòng.

Chỉ dùng nội bộ: không tái phân phối văn bản thô. Mỗi lần chạy luôn kiểm tra
robots.txt, giới hạn URL từ file seed, và lưu metadata/trạng thái từ chối.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_SEEDS = ROOT / "data" / "sft" / "tet4_web_seed_urls_v1.json"
DEFAULT_OUTPUT = ROOT / "data" / "sft" / "archive" / "tet4_legacy_staging_v1" / "tet4_web_staging_v1.jsonl"
DEFAULT_AUDIT = ROOT / "data" / "sft" / "archive" / "tet4_legacy_staging_v1" / "tet4_web_audit_v1.json"
DEFAULT_REVIEW = ROOT / "data" / "sft" / "archive" / "tet4_legacy_staging_v1" / "tet4_web_review_v1.jsonl"
USER_AGENT = "CapstoneTet4Research/0.1 (+internal-nonredistributed; contact: local-project)"
WS_RE = re.compile(r"[ \t\xa0]+")
TET_RE = re.compile(r"\b(tết|xuân|năm mới|giao thừa|an khang|phúc|lộc|thọ|mừng tuổi|lì xì)\b", re.I)
BLOCK_TAGS = {"p", "div", "li", "pre", "blockquote", "h1", "h2", "h3", "h4", "article", "section"}
SKIP_TAGS = {"script", "style", "nav", "footer", "header", "noscript", "svg"}


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines, self._parts, self._skip, self.meta = [], [], 0, {}

    def _flush(self):
        value = WS_RE.sub(" ", "".join(self._parts)).strip()
        if value:
            self.lines.append(value)
        self._parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in SKIP_TAGS:
            self._skip += 1
        if tag == "meta":
            key = (attrs.get("name") or attrs.get("property") or "").lower()
            value = attrs.get("content")
            if value and key in {"author", "article:author", "article:published_time", "date", "datepublished", "og:title"}:
                self.meta[key] = value.strip()
        if not self._skip and tag in BLOCK_TAGS | {"br"}:
            self._flush()

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self._skip:
            self._skip -= 1
        if not self._skip and tag in BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def close(self):
        super().close()
        self._flush()


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text or "").replace("\r", "").strip()


def robots_allowed(url: str) -> tuple[bool, str]:
    parsed = urlparse(url)
    robot_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robot_url)
    try:
        parser.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return False, f"robots_unavailable:{type(exc).__name__}"
    return parser.can_fetch(USER_AGENT, url), "robots_disallow" if not parser.can_fetch(USER_AGENT, url) else "ok"


def fetch(url: str, timeout: int) -> tuple[str | None, str | None]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                return None, f"unsupported_content_type:{content_type}"
            return response.read(3_000_000).decode(response.headers.get_content_charset() or "utf-8", errors="replace"), None
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return None, f"fetch_failed:{type(exc).__name__}"


def candidate_windows(lines: list[str], page_is_tet: bool):
    # Only neighboring rendered lines. This avoids joining arbitrary distant prose.
    for index in range(len(lines) - 3):
        block = lines[index:index + 4]
        text = "\n".join(block)
        if page_is_tet or TET_RE.search(text):
            yield index, text


def record_for(url, page, evaluator, assess):
    parser = PageText()
    parser.feed(page)
    parser.close()
    title = parser.meta.get("og:title") or next((line for line in parser.lines if len(line) < 180), "")
    author = parser.meta.get("author") or parser.meta.get("article:author") or None
    published = parser.meta.get("article:published_time") or parser.meta.get("date") or parser.meta.get("datepublished") or None
    accepted, review, seen, candidates = [], [], set(), []
    page_is_tet = bool(TET_RE.search(title + " " + " ".join(parser.lines[:20])))
    page_work_id = "web-page:" + hashlib.sha256(url.encode()).hexdigest()[:20]
    scanned_windows = 0
    for offset, poem in candidate_windows(parser.lines, page_is_tet):
        scanned_windows += 1
        fingerprint = hashlib.sha256(normalize(poem).lower().encode()).hexdigest()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        metrics = evaluator.evaluate(poem, expected_num_lines=4)
        lexical = assess(poem)
        base = {
            "source_id": "tet4_web_internal_v1",
            "work_id": f"web:{fingerprint[:20]}",
            "source_work_id": page_work_id,
            "source_record_id": f"{hashlib.sha256(url.encode()).hexdigest()[:12]}:{offset}",
            "line_offset": offset,
            "url": url,
            "domain": urlparse(url).netloc.lower(),
            "title": title,
            "author": author,
            "published_at": published,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "text": poem,
            "text_sha256": fingerprint,
            "metrics": {key: metrics[key] for key in ("scr", "tcr", "rma", "combined_rma", "structure_ok", "is_valid_lucbat")},
            "lexical_issues": lexical["issues"],
            "usage": "internal_only_no_redistribution",
        }
        # Structure is mandatory. RMA >= 50 means at least one of the two required
        # rhyme links is recognized; low-TCR material is quarantined for review.
        if metrics["structure_ok"] and metrics["rma"] >= 50 and metrics["tcr"] >= 70 and not lexical["hard_fail"]:
            candidates.append((offset, "accepted", base))
        elif metrics["structure_ok"] and not lexical["hard_fail"]:
            reasons = []
            if metrics["rma"] < 50:
                reasons.append("low_rhyme_score")
            if metrics["tcr"] < 70:
                reasons.append("low_tone_score")
            base["review_reason"] = ",".join(reasons)
            candidates.append((offset, "review", base))
    # A 4-line training unit must not share any rendered line with another kept unit.
    occupied, overlap_removed = set(), 0
    for offset, bucket, item in candidates:
        window = set(range(offset, offset + 4))
        if occupied & window:
            overlap_removed += 1
            continue
        occupied.update(window)
        (accepted if bucket == "accepted" else review).append(item)
    return {"url": url, "domain": urlparse(url).netloc.lower(), "title": title, "author": author, "published_at": published, "page_is_tet": page_is_tet, "rendered_lines": len(parser.lines), "scanned_windows": scanned_windows, "overlap_removed": overlap_removed}, accepted, review


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=Path, default=DEFAULT_SEEDS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--review-output", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    if args.delay_seconds < 1:
        raise ValueError("delay-seconds phải >= 1 để crawl có kiểm soát")
    from engine.evaluator import LucBatEvaluator
    from engine.lexical_guard import assess

    seed_data = json.loads(args.seeds.read_text(encoding="utf-8"))
    urls = [item for item in seed_data["sources"] if item.get("enabled", True)]
    if args.max_pages is not None:
        urls = urls[:args.max_pages]
    audit = {"version": "tet4-web-corpus-v1", "policy": seed_data["policy"], "started_at": datetime.now(timezone.utc).isoformat(), "seed_file": str(args.seeds), "pages": [], "accepted_records": 0, "review_records": 0}
    all_records, review_records, text_seen, review_seen = [], [], set(), set()
    evaluator = LucBatEvaluator()
    for position, seed_item in enumerate(urls):
        url = seed_item["url"]
        allowed, reason = robots_allowed(url)
        page_audit = {"url": url, "domain": urlparse(url).netloc.lower(), "query": seed_item.get("query"), "robots": reason, "status": "rejected"}
        if allowed:
            html, error = fetch(url, args.timeout)
            if error:
                page_audit["reason"] = error
            else:
                metadata, accepted, review = record_for(url, html, evaluator, assess)
                page_audit.update({"status": "processed", "metadata": metadata, "accepted": len(accepted), "review": len(review)})
                for item in accepted:
                    if item["text_sha256"] not in text_seen:
                        all_records.append(item); text_seen.add(item["text_sha256"])
                for item in review:
                    if item["text_sha256"] not in review_seen and item["text_sha256"] not in text_seen:
                        review_records.append(item); review_seen.add(item["text_sha256"])
        audit["pages"].append(page_audit)
        if position + 1 < len(urls):
            time.sleep(args.delay_seconds)
    audit["accepted_records"] = len(all_records)
    audit["review_records"] = len(review_records)
    audit["finished_at"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for item in all_records:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    with args.review_output.open("w", encoding="utf-8") as handle:
        for item in review_records:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"processed": sum(p["status"] == "processed" for p in audit["pages"]), "accepted": len(all_records), "review": len(review_records), "audit": str(args.audit), "review_output": str(args.review_output)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
