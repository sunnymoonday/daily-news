"""분야별 주요기사를 모아 news.json을 만든다.

외부 라이브러리 없이 표준 라이브러리만 쓴다(GitHub Actions에서 바로 실행).
사용법: python scripts/fetch_news.py [출력 경로, 기본 news.json]
"""
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

KST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (compatible; daily-news-bot/1.0; +https://github.com/sunnymoonday/daily-news)"
PER_SECTION = 8

SECTIONS = [
    {"id": "economy", "name": "경제", "color": "--eco", "feeds": [
        ("연합뉴스", "https://www.yna.co.kr/rss/economy.xml"),
        ("한국경제", "https://www.hankyung.com/feed/economy"),
    ]},
    {"id": "current", "name": "시사", "color": "--sisa", "feeds": [
        ("연합뉴스", "https://www.yna.co.kr/rss/politics.xml"),
        ("연합뉴스", "https://www.yna.co.kr/rss/society.xml"),
    ]},
    {"id": "estate", "name": "부동산", "color": "--estate", "feeds": [
        ("한국경제", "https://www.hankyung.com/feed/realestate"),
        ("매일경제", "https://www.mk.co.kr/rss/50300009/"),
    ]},
    {"id": "policy", "name": "정부정책", "color": "--policy", "feeds": [
        ("정책브리핑", "korea.kr"),
    ]},
]

# 주요기사로 보기 어려운 단신·알림성 기사
SKIP = re.compile(r"^\s*[\[【(]?\s*(포토|사진|게시판|인사|부고|부음|화촉|오늘의|날씨|운세|모집|알림|표|그래픽|영상)\s*[\]】)]")

# "(서울=연합뉴스) 홍길동 기자 =" 같은 기사 첫머리 표기
BYLINE = re.compile(r"^\([^)]*=[^)]*\)\s*(?:[^=]{0,30}?(?:기자|특파원|통신원)\s*)?=?\s*")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
    for enc in ("utf-8", "euc-kr", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def clean(text, limit=None):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        cut = text[:limit]
        end = max(cut.rfind(". "), cut.rfind("다."))
        text = cut[: end + 2].strip() if end > limit * 0.5 else cut.rstrip() + "…"
    return text


def parse_date(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s.strip())
        return d.astimezone(KST) if d.tzinfo else d.replace(tzinfo=KST)
    except (TypeError, ValueError):
        return None


def from_rss(source, url):
    root = ET.fromstring(get(url).encode("utf-8"))
    items = []
    for it in root.iter("item"):
        title = clean(it.findtext("title"))
        link = (it.findtext("link") or "").strip()
        if not title or not link or SKIP.search(title):
            continue
        summary = clean(BYLINE.sub("", clean(it.findtext("description"))), 140)
        if len(summary) < 15:  # "(서울=연합뉴스" 처럼 잘린 문구는 버린다
            summary = ""
        items.append({
            "title": title,
            "summary": summary,
            "source": source,
            "url": link,
            "published": parse_date(it.findtext("pubDate")),
        })
    return items


def from_korea_kr():
    page = get("https://www.korea.kr/news/policyNewsList.do")
    items = []
    for m in re.finditer(r'<a href="(/news/policyNewsView\.do\?newsId=\d+)"[^>]*>(.*?)</a>', page, re.S):
        body = m.group(2)
        title = re.search(r"<strong>(.*?)</strong>", body, re.S)
        if not title:
            continue
        sub = re.search(r'class="stitle">(.*?)</span>', body, re.S)
        lead = re.search(r'class="lead">(.*?)</span>', body, re.S)
        summary = clean(sub.group(1)) if sub and clean(sub.group(1)) else clean(lead.group(1) if lead else "", 140)
        items.append({
            "title": clean(title.group(1)),
            "summary": summary,
            "source": "정책브리핑",
            "url": "https://www.korea.kr" + m.group(1),
            "published": None,
        })
    return items


def norm(title):
    return re.sub(r"[^0-9A-Za-z가-힣]", "", title)[:18]


def collect(section):
    lists = []
    for source, url in section["feeds"]:
        try:
            lists.append(from_korea_kr() if url == "korea.kr" else from_rss(source, url))
        except Exception as e:  # 한 피드가 실패해도 나머지로 채운다
            print(f"[warn] {section['name']} {source} {url}: {e}", file=sys.stderr)
    for lst in lists:
        lst.sort(key=lambda x: x["published"] or datetime.max.replace(tzinfo=KST), reverse=True)
    # 피드를 번갈아 가며 뽑아 한 언론사로 쏠리지 않게 한다
    picked, seen = [], set()
    for i in range(max((len(l) for l in lists), default=0)):
        for lst in lists:
            if i < len(lst) and len(picked) < PER_SECTION:
                key = norm(lst[i]["title"])
                if key not in seen and lst[i]["url"] not in seen:
                    seen.update({key, lst[i]["url"]})
                    picked.append(lst[i])
    for p in picked:
        p["published"] = p["published"].strftime("%Y-%m-%dT%H:%M:%S+09:00") if p["published"] else None
    return picked


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "news.json"
    now = datetime.now(KST)
    sections = []
    for s in SECTIONS:
        items = collect(s)
        print(f"{s['name']}: {len(items)}건")
        sections.append({k: s[k] for k in ("id", "name", "color")} | {"items": items})
    if not any(s["items"] for s in sections):
        sys.exit("기사를 하나도 가져오지 못했습니다. 기존 news.json을 유지합니다.")
    data = {"updated": now.strftime("%Y-%m-%dT%H:%M:%S+09:00"), "sections": sections}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"저장: {out} ({now:%Y-%m-%d %H:%M} KST)")


if __name__ == "__main__":
    main()
