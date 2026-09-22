
import os
import re
import json
import html
import base64
import hashlib
import time
import asyncio
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import requests
import feedparser
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO


# ============================================================
# FUTBOL PULSE - ONE SHOT PUBLISHER
# GitHub Actions runs this script every 10 minutes.
# ============================================================

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

CHANNEL_LINK = "https://t.me/Futbol_Pulse24"

TEXT_MODEL = "gemini-3.5-flash"
IMAGE_MODEL = "gemini-3.1-flash-image"

STATE_FILE = "posted_news.json"

REQUEST_TIMEOUT = 25
MAX_ARTICLE_CHARS = 14000
MAX_NEWS_PER_SOURCE = 12
MAX_POSTS_PER_RUN = 4
MAX_NEWS_AGE_HOURS = 72

MIN_WIDTH = 900
MIN_HEIGHT = 500
MIN_BYTES = 40_000

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 Chrome/140 Safari/537.36 "
        "FutbolPulseBot/5.0"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

RSS_FEEDS = [
    {
        "name": "BBC Sport",
        "url": "https://feeds.bbci.co.uk/sport/football/rss.xml",
    },
    {
        "name": "The Guardian Football",
        "url": "https://www.theguardian.com/football/rss",
    },
    {
        "name": "ESPN Soccer",
        "url": "https://www.espn.com/espn/rss/soccer/news",
    },
]

MAJOR_CLUBS = [
    "real madrid", "barcelona", "atletico madrid",
    "manchester united", "manchester city", "liverpool",
    "arsenal", "chelsea", "tottenham",
    "bayern munich", "bayern", "borussia dortmund",
    "psg", "paris saint-germain", "juventus",
    "inter milan", "inter", "ac milan", "milan",
    "napoli", "roma", "newcastle", "aston villa",
    "al hilal", "al nassr", "galatasaray", "fenerbahce",
    "benfica", "porto", "ajax",
]

MAJOR_PLAYERS = [
    "mbappe", "kylian mbappe", "vinicius", "vinicius junior",
    "bellingham", "jude bellingham", "haaland", "erling haaland",
    "salah", "mohamed salah", "messi", "lionel messi",
    "ronaldo", "cristiano ronaldo", "lewandowski",
    "de bruyne", "kevin de bruyne", "rodri",
    "yamal", "lamine yamal", "pedri", "saka", "bukayo saka",
    "rashford", "bruno fernandes", "kane", "harry kane",
    "son heung-min", "neymar", "osimhen", "gyokeres",
    "lautaro martinez", "griezmann", "foden", "phil foden",
    "palmer", "cole palmer", "musiala", "wirtz",
]

MAJOR_COMPETITIONS = [
    "champions league", "uefa champions league",
    "europa league", "conference league",
    "premier league", "la liga", "laliga", "serie a",
    "bundesliga", "ligue 1", "world cup", "fifa world cup",
    "euro", "european championship", "copa america",
    "afcon", "fa cup", "carabao cup", "copa del rey",
]

CATEGORY_EMOJI = {
    "breaking": "🚨",
    "transfer": "🔄",
    "player": "⭐",
    "injury": "🚑",
    "manager": "🧠",
    "match": "🔥",
    "result": "⚽",
    "other": "📰",
}


def clean_text(value):
    if not value:
        return ""
    value = html.unescape(str(value))
    value = re.sub(r"<script.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_title(value):
    value = clean_text(value).lower()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def make_id(url, title):
    raw = (url.strip() + "|" + normalize_title(title)).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(data)
        return set()
    except FileNotFoundError:
        return set()
    except Exception as e:
        print("STATE LOAD ERROR:", repr(e))
        return set()


def save_state(state):
    # Keep the repository file small.
    values = list(state)[-3000:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(values, f, ensure_ascii=False, indent=2)


def request_text(url, timeout=REQUEST_TIMEOUT):
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text


def get_meta(soup, *names):
    for name in names:
        tag = soup.find("meta", attrs={"property": name})
        if tag and tag.get("content"):
            return html.unescape(tag["content"]).strip()

        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return html.unescape(tag["content"]).strip()

    return ""


def parse_date(value):
    if not value:
        return None

    value = value.strip()

    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    try:
        value2 = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(value2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def article_from_jsonld(soup):
    blocks = []

    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw:
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        objects = data if isinstance(data, list) else [data]

        for obj in objects:
            if isinstance(obj, dict) and "@graph" in obj:
                objects.extend(obj["@graph"])

            if not isinstance(obj, dict):
                continue

            body = obj.get("articleBody")
            if isinstance(body, str) and body.strip():
                blocks.append(body.strip())

    return max(blocks, key=len) if blocks else ""


def extract_article_text(soup):
    body = article_from_jsonld(soup)

    if len(body) >= 700:
        return clean_text(body)[:MAX_ARTICLE_CHARS]

    candidates = [
        "article",
        "[itemprop='articleBody']",
        "main",
        ".article-body",
        ".article__body",
        ".story-body",
        ".entry-content",
        ".content-body",
    ]

    best = ""

    for selector in candidates:
        node = soup.select_one(selector)
        if not node:
            continue

        paragraphs = [
            clean_text(p.get_text(" ", strip=True))
            for p in node.find_all(["p", "h2", "h3"])
        ]

        paragraphs = [
            p for p in paragraphs
            if len(p) >= 35
            and not p.lower().startswith(
                ("sign up", "subscribe", "advertisement", "related")
            )
        ]

        text = "\n".join(paragraphs)

        if len(text) > len(best):
            best = text

    if len(best) < 500:
        paragraphs = [
            clean_text(p.get_text(" ", strip=True))
            for p in soup.find_all("p")
        ]

        paragraphs = [p for p in paragraphs if len(p) >= 40]
        best = "\n".join(paragraphs[:80])

    return best[:MAX_ARTICLE_CHARS]


def extract_original_image(soup, article_url):
    candidates = []

    # The article's own OpenGraph image has priority.
    og = get_meta(soup, "og:image")
    if og:
        candidates.append(urljoin(article_url, og))

    twitter = get_meta(soup, "twitter:image")
    if twitter:
        candidates.append(urljoin(article_url, twitter))

    # JSON-LD image is still from the same article page.
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        try:
            data = json.loads(raw)
        except Exception:
            continue

        objects = data if isinstance(data, list) else [data]
        for obj in objects:
            if not isinstance(obj, dict):
                continue

            image = obj.get("image")

            if isinstance(image, str):
                candidates.append(urljoin(article_url, image))

            elif isinstance(image, dict):
                value = image.get("url")
                if value:
                    candidates.append(urljoin(article_url, value))

            elif isinstance(image, list):
                for value in image:
                    if isinstance(value, str):
                        candidates.append(urljoin(article_url, value))
                    elif isinstance(value, dict) and value.get("url"):
                        candidates.append(
                            urljoin(article_url, value["url"])
                        )

    # Same article page only. No Google/image-site search.
    for img in soup.find_all("img"):
        src = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-original")
            or img.get("data-lazy-src")
        )

        if src:
            candidates.append(urljoin(article_url, src))

    seen = set()

    for url in candidates:
        url = url.strip()

        if not url.startswith(("http://", "https://")):
            continue

        if url in seen:
            continue

        seen.add(url)

        if validate_image(url):
            return url

    return None


def validate_image(url):
    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()

        content_type = r.headers.get("content-type", "").lower()
        data = r.content

        if "image" not in content_type and not data:
            return False

        if len(data) < MIN_BYTES:
            return False

        image = Image.open(BytesIO(data))
        width, height = image.size

        if width < MIN_WIDTH or height < MIN_HEIGHT:
            return False

        return True

    except Exception:
        return False


def download_image(url):
    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()

        data = r.content

        if len(data) < MIN_BYTES:
            return None

        image = Image.open(BytesIO(data))
        image.verify()

        return data

    except Exception as e:
        print("IMAGE DOWNLOAD ERROR:", repr(e))
        return None


def fetch_article(url, fallback_title="", fallback_description=""):
    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        title = (
            get_meta(soup, "og:title", "twitter:title")
            or fallback_title
        )

        description = (
            get_meta(
                soup,
                "og:description",
                "description",
                "twitter:description",
            )
            or fallback_description
        )

        article_text = extract_article_text(soup)

        image_url = extract_original_image(
            soup,
            url,
        )

        return {
            "title": clean_text(title),
            "description": clean_text(description),
            "article_text": article_text,
            "image_url": image_url,
        }

    except Exception as e:
        print("ARTICLE ERROR:", url, repr(e))

        return {
            "title": fallback_title,
            "description": fallback_description,
            "article_text": "",
            "image_url": None,
        }


def fetch_news():
    results = []
    seen_urls = set()
    seen_titles = set()

    for source in RSS_FEEDS:
        try:
            feed = feedparser.parse(
                requests.get(
                    source["url"],
                    headers=HEADERS,
                    timeout=REQUEST_TIMEOUT,
                ).content
            )

            for entry in feed.entries[:MAX_NEWS_PER_SOURCE]:
                title = clean_text(
                    getattr(entry, "title", "")
                )

                link = getattr(entry, "link", "")
                link = urljoin(source["url"], link)

                description = clean_text(
                    getattr(entry, "summary", "")
                    or getattr(entry, "description", "")
                )

                published_raw = (
                    getattr(entry, "published", "")
                    or getattr(entry, "updated", "")
                    or getattr(entry, "created", "")
                )
                published_at = parse_date(published_raw)

                if published_at is not None:
                    age = datetime.now(timezone.utc) - published_at
                    if age > timedelta(hours=MAX_NEWS_AGE_HOURS):
                        continue

                if not title or not link:
                    continue

                if link in seen_urls:
                    continue

                title_key = normalize_title(title)

                if title_key in seen_titles:
                    continue

                seen_urls.add(link)
                seen_titles.add(title_key)

                results.append(
                    {
                        "source": source["name"],
                        "title": title,
                        "description": description,
                        "link": link,
                        "published_at": published_at.isoformat() if published_at else "",
                    }
                )

        except Exception as e:
            print(
                "RSS ERROR:",
                source["name"],
                repr(e),
            )

    print("RSS NEWS FOUND:", len(results))
    return results


def is_major_match_text(text):
    lower = text.lower()

    club_count = sum(
        1 for club in MAJOR_CLUBS
        if club in lower
    )

    match_words = [
        " vs ",
        " v ",
        "versus",
        "match",
        "fixture",
        "kick-off",
        "kickoff",
        "live",
        "preview",
    ]

    has_match_word = any(
        word in lower
        for word in match_words
    )

    return club_count >= 2 and has_match_word


def gemini_text(prompt):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{TEXT_MODEL}:generateContent"
    )

    body = {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "You are the senior editor of Futbol Pulse. "
                        "You must never invent facts, names, scores, "
                        "quotes, transfers, dates or injuries."
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 6000,
            "responseMimeType": "application/json",
        },
    }

    try:
        r = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": GEMINI_API_KEY,
            },
            json=body,
            timeout=90,
        )

        if not r.ok:
            print(
                "GEMINI TEXT ERROR:",
                r.status_code,
                r.text[:1000],
            )
            return None

        data = r.json()

        parts = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [])
        )

        text = "\n".join(
            p.get("text", "")
            for p in parts
            if p.get("text")
        ).strip()

        return text or None

    except Exception as e:
        print("GEMINI TEXT EXCEPTION:", repr(e))
        return None


def parse_json(text):
    if not text:
        return None

    text = text.strip()

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.I,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")

        if start >= 0 and end > start:
            try:
                return json.loads(
                    text[start:end + 1]
                )
            except Exception:
                pass

        return None


def select_and_write_news(news):
    source_blocks = []

    for i, item in enumerate(news):
        source_blocks.append(
            f"""
SOURCE_INDEX: {i}
SOURCE: {item["source"]}
TITLE: {item["title"]}
DESCRIPTION: {item["description"]}
URL: {item["link"]}
"""
        )

    prompt = f"""
Select only the most important football stories for a Telegram
channel aimed at Uzbek-speaking football fans.

There can be 0 to {MAX_POSTS_PER_RUN} stories.

PRIORITY:
- breaking and official news
- major transfers
- Mbappe, Haaland, Vinicius, Bellingham, Yamal, Salah,
  Messi, Ronaldo and other major players
- Real Madrid, Barcelona, Manchester City, Manchester United,
  Liverpool, Arsenal, Chelsea, Bayern, PSG, Juventus, Inter,
  Milan and other major clubs
- Champions League, Premier League, La Liga, Serie A,
  Bundesliga, Ligue 1, World Cup, EURO
- important injuries, suspensions, coach changes
- major upcoming matches and live match announcements

REJECT:
- small routine training updates
- low-interest minor statistics
- duplicate stories
- clickbait without factual substance
- rumors presented as confirmed facts
- stories where the source is too vague to support the claim

IMAGE RULES — VERY IMPORTANT:
1. For a normal news story, image_mode MUST be "original".
2. The program will use ONLY the image from the same source article.
3. Never ask the program to search for another footballer image.
4. If the source article has no usable original image, the final post
   must be allowed to have NO image.
5. image_mode="ai" is allowed ONLY for a genuinely important upcoming
   match/live announcement involving at least two major clubs.
6. For a normal transfer, injury, player news, result or quote,
   image_mode MUST remain "original".
7. Never use AI image generation as a fallback for normal news.

LANGUAGE:
- Write the final title and body in natural Uzbek Latin.
- Preserve names, clubs, competitions and numbers accurately.
- Fully convey the important factual content available in the source.
- Do not copy long source passages word-for-word.
- Do not invent missing details.

For each selected story, return:
- source_index: exact integer from the supplied source list
- title_uz
- body_uz
- category: breaking|transfer|player|injury|manager|match|result|other
- importance: integer 1-10
- image_mode: original|ai
- match_datetime_utc: ISO-8601 UTC string ONLY when an upcoming match
  time is explicitly supported by the source, otherwise empty
- match_teams: empty unless it is an upcoming match announcement
- source_claim: a short factual sentence explaining why this story is
  important, based only on the source

For a match announcement:
- image_mode="ai" only if BOTH teams are major clubs and the match is
  genuinely important.
- Do not use image_mode="ai" merely because the story contains the word
  "match".
- Do not invent the match time.

Return ONLY this JSON object:
{{
  "items": [
    {{
      "source_index": 0,
      "title_uz": "...",
      "body_uz": "...",
      "category": "breaking",
      "importance": 9,
      "image_mode": "original",
      "match_datetime_utc": "",
      "match_teams": "",
      "source_claim": "..."
    }}
  ]
}}

SOURCES:
{"".join(source_blocks)}
"""

    raw = gemini_text(prompt)
    data = parse_json(raw)

    if not isinstance(data, dict):
        print("SELECTION JSON INVALID")
        return []

    items = data.get("items")

    if not isinstance(items, list):
        return []

    valid = []

    for item in items:
        if not isinstance(item, dict):
            continue

        try:
            index = int(item.get("source_index"))
        except Exception:
            continue

        if index < 0 or index >= len(news):
            continue

        title = clean_text(item.get("title_uz", ""))
        body = clean_text(item.get("body_uz", ""))

        if not title or not body:
            continue

        try:
            importance = int(item.get("importance", 0))
        except Exception:
            importance = 0

        if importance < 7:
            continue

        category = str(
            item.get("category", "other")
        ).lower().strip()

        allowed_categories = set(CATEGORY_EMOJI.keys())

        if category not in allowed_categories:
            category = "other"

        image_mode = str(
            item.get("image_mode", "original")
        ).lower().strip()

        if image_mode not in {"original", "ai"}:
            image_mode = "original"

        source = news[index]

        combined = (
            source["title"]
            + " "
            + source["description"]
        )

        # AI image is strictly limited to major upcoming matches.
        if image_mode == "ai" and not is_major_match_text(combined):
            image_mode = "original"

        valid.append(
            {
                "source_index": index,
                "source": source["source"],
                "source_title": source["title"],
                "source_url": source["link"],
                "title_uz": title,
                "body_uz": body,
                "category": category,
                "importance": importance,
                "image_mode": image_mode,
                "match_datetime_utc": clean_text(
                    item.get("match_datetime_utc", "")
                ),
                "match_teams": clean_text(
                    item.get("match_teams", "")
                ),
                "source_claim": clean_text(
                    item.get("source_claim", "")
                ),
            }
        )

    # Highest importance first.
    valid.sort(
        key=lambda x: x["importance"],
        reverse=True,
    )

    return valid[:MAX_POSTS_PER_RUN]


def generate_ai_match_image(item):
    title = item["title_uz"]
    body = item["body_uz"]

    prompt = f"""
Create a premium 16:9 football news image for the Futbol Pulse
Telegram channel.

This is an UPCOMING MATCH ANNOUNCEMENT, not a final result.

MATCH:
{title}

DETAILS:
{body}

REQUIREMENTS:
- 16:9 landscape
- high quality, sharp, realistic professional sports photography
- dramatic stadium atmosphere
- clearly represent the two named clubs
- authentic-looking club colors and kits
- if named players are explicitly in the story, they may be represented
- do not invent a score
- do not imply that the match has already been played
- no fake statistics
- no fake quotes
- no random unrelated footballers
- no unrelated clubs
- minimal or no text inside the image
- premium sports-news visual
- natural anatomy and realistic faces
- suitable for a Telegram football news channel
"""

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{IMAGE_MODEL}:generateContent"
    )

    body_json = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt
                    }
                ],
            }
        ],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {
                "aspectRatio": "16:9",
                "imageSize": "2K",
            },
        },
    }

    try:
        r = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": GEMINI_API_KEY,
            },
            json=body_json,
            timeout=180,
        )

        if not r.ok:
            print(
                "GEMINI IMAGE ERROR:",
                r.status_code,
                r.text[:1200],
            )
            return None

        data = r.json()

        parts = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [])
        )

        for part in parts:
            inline = (
                part.get("inlineData")
                or part.get("inline_data")
            )

            if inline and inline.get("data"):
                return base64.b64decode(
                    inline["data"]
                )

    except Exception as e:
        print("AI IMAGE EXCEPTION:", repr(e))

    return None


def format_post(item):
    emoji = CATEGORY_EMOJI.get(
        item["category"],
        "📰",
    )

    title = html.escape(item["title_uz"])
    body = html.escape(item["body_uz"])

    text = (
        f"{emoji} <b>{title}</b>\n\n"
        f"{body}"
    )

    if item["image_mode"] == "ai":
        text += "\n\n🔥 <b>Muhim o‘yin anonsi</b>"

    text += (
        f'\n\n📰 <b>Manba:</b> '
        f'{html.escape(item["source"])}'
        f'\n⚽ <a href="{CHANNEL_LINK}">Futbol Pulse</a>'
    )

    # Telegram sendPhoto caption limit.
    if len(text) > 1000:
        text = text[:990] + "…"

    return text


def telegram_send_message(text):
    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    r = requests.post(
        url,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )

    if not r.ok:
        raise RuntimeError(
            f"Telegram message error {r.status_code}: {r.text}"
        )

    return r.json()


def telegram_send_photo(image_bytes, caption):
    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendPhoto"
    )

    files = {
        "photo": (
            "futbol_pulse.jpg",
            image_bytes,
            "image/jpeg",
        )
    }

    data = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "caption": caption,
        "parse_mode": "HTML",
    }

    r = requests.post(
        url,
        data=data,
        files=files,
        timeout=60,
    )

    if not r.ok:
        raise RuntimeError(
            f"Telegram photo error {r.status_code}: {r.text}"
        )

    return r.json()


def process_item(item):
    print(
        "\nPROCESS:",
        item["title_uz"],
        "| image_mode=",
        item["image_mode"],
    )

    article = fetch_article(
        item["source_url"],
        fallback_title=item["source_title"],
        fallback_description="",
    )

    # The image must come from THIS source article.
    original_image_url = article.get("image_url")

    # For normal news: original image only.
    if item["image_mode"] == "original":
        image_bytes = None

        if original_image_url:
            image_bytes = download_image(
                original_image_url
            )

        caption = format_post(item)

        if image_bytes:
            telegram_send_photo(
                image_bytes,
                caption,
            )
            print("POSTED WITH ORIGINAL SOURCE IMAGE")
        else:
            # Never replace it with another football image.
            telegram_send_message(caption)
            print("POSTED WITHOUT IMAGE — no suitable source image")

        return True

    # For a major upcoming match: AI image only.
    if item["image_mode"] == "ai":
        image_bytes = generate_ai_match_image(item)

        if image_bytes:
            telegram_send_photo(
                image_bytes,
                format_post(item),
            )
            print("POSTED WITH AI MATCH IMAGE")
            return True

        # AI image failed: do NOT use a random/source image as fallback.
        # The match announcement is still published as text.
        telegram_send_message(
            format_post(item)
        )
        print("AI IMAGE FAILED — posted text only")
        return True

    return False


def publish_once():
    """Fetch, select and publish fresh football news once."""
    print("==========================================")
    print("⚽ FUTBOL PULSE — PUBLISH CYCLE")
    print("==========================================")

    state = load_state()
    news = fetch_news()

    if not news:
        print("No RSS news.")
        return

    fresh = []

    for item in news:
        item_id = make_id(item["link"], item["title"])
        item["id"] = item_id

        if item_id not in state:
            fresh.append(item)

    print("FRESH NEWS:", len(fresh))

    if not fresh:
        print("Nothing new to publish.")
        return

    selected = select_and_write_news(fresh)
    print("SELECTED:", len(selected))

    if not selected:
        print("No important stories selected.")
        return

    for item in selected:
        try:
            posted = process_item(item)

            if not posted:
                print("NOT POSTED — state not updated")
                continue

            state.add(
                make_id(
                    item["source_url"],
                    item["source_title"],
                )
            )
            save_state(state)
            time.sleep(2)

        except Exception as e:
            print("POST ERROR:", item["title_uz"], repr(e))

    print("PUBLISH CYCLE DONE.")


async def start_command(update, context):
    await update.message.reply_text(
        "⚽ <b>FUTBOL PULSE</b>\n\n"
        "Bot ishlayapti! ✅\n\n"
        "/news — eng muhim futbol yangiliklari",
        parse_mode="HTML",
    )


def build_user_post(item):
    emoji = CATEGORY_EMOJI.get(item.get("category", "other"), "📰")
    title = html.escape(item["title_uz"])
    body = html.escape(item["body_uz"])

    text = f"{emoji} <b>{title}</b>\n\n{body}"

    if item.get("image_mode") == "ai":
        text += "\n\n🔥 <b>Muhim o‘yin anonsi</b>"

    text += (
        f'\n\n📰 <b>Manba:</b> {html.escape(item["source"])}'
        f'\n⚽ <a href="{CHANNEL_LINK}">Futbol Pulse</a>'
    )

    return text[:1000] if len(text) > 1000 else text


def get_selected_for_command():
    news = fetch_news()
    if not news:
        return []

    selected = select_and_write_news(news)
    return selected


async def news_command(update, context):
    status = await update.message.reply_text(
        "⚽ Yangiliklar tekshirilmoqda...\n\n🤖 Muhimlari saralanmoqda..."
    )

    try:
        selected = await asyncio.to_thread(get_selected_for_command)

        if not selected:
            await status.edit_text(
                "Hozircha yetarlicha muhim yangilik topilmadi. ⚽"
            )
            return

        await status.edit_text(
            f"🔥 {len(selected)} ta muhim yangilik topildi.\n"
            "🖼️ Rasm tayyorlanmoqda..."
        )

        for item in selected:
            image_bytes = await asyncio.to_thread(
                lambda: (
                    fetch_article(
                        item["source_url"],
                        fallback_title=item["source_title"],
                        fallback_description="",
                    ).get("image_url")
                )
            )

            photo_bytes = None

            if item.get("image_mode") == "ai":
                photo_bytes = await asyncio.to_thread(
                    generate_ai_match_image, item
                )
            elif image_bytes:
                photo_bytes = await asyncio.to_thread(
                    download_image, image_bytes
                )

            caption = build_user_post(item)

            if photo_bytes:
                bio = BytesIO(photo_bytes)
                bio.name = "futbol_pulse.jpg"
                await update.message.reply_photo(
                    photo=bio,
                    caption=caption,
                    parse_mode="HTML",
                )
            else:
                await update.message.reply_text(
                    caption,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )

        await status.edit_text("✅ Yangiliklar yuborildi.")

    except Exception as e:
        print("NEWS COMMAND ERROR:", repr(e))
        await status.edit_text(
            "❌ Yangiliklarni olishda xatolik yuz berdi."
        )


async def hourly_publisher():
    """Publish automatically every hour while the process is alive."""
    while True:
        try:
            await asyncio.to_thread(publish_once)
        except Exception as e:
            print("HOURLY PUBLISH ERROR:", repr(e))

        await asyncio.sleep(3600)


async def post_init(application):
    application.create_task(hourly_publisher())


def main():
    print("==========================================")
    print("⚽ FUTBOL PULSE BOT v6")
    print("==========================================")
    print("Telegram: /start /news")
    print("Auto publisher: every 1 hour")
    print("==========================================")

    try:
        from telegram import Update
        from telegram.ext import Application, CommandHandler, ContextTypes
    except ImportError:
        print("ERROR: python-telegram-bot is not installed.")
        raise

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("news", news_command))

    print("Telegram polling started.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
