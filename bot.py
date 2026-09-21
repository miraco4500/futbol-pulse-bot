import os
import json
import re
import html
import io
import base64
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


# =========================================================
# FUTBOL PULSE BOT
# =========================================================

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

CHANNEL_USERNAME = "@Futbol_Pulse24"
CHANNEL_LINK = "https://t.me/Futbol_Pulse24"

# Ishlayotgan Gemini text modeli
GEMINI_MODEL = "gemini-3.1-flash-lite"

# AI rasm modeli
GEMINI_IMAGE_MODEL = "gemini-3.1-flash-image"

# Toshkent vaqti
TASHKENT_TZ = ZoneInfo("Asia/Tashkent")


# =========================================================
# RSS MANBALAR
# =========================================================

RSS_FEEDS = [
    "https://www.theguardian.com/football/rss",
    "https://feeds.bbci.co.uk/sport/football/rss.xml",
]


# =========================================================
# ASOSIY KLUBLAR
# =========================================================

MAJOR_CLUBS = [
    "real madrid",
    "barcelona",
    "manchester united",
    "manchester city",
    "liverpool",
    "arsenal",
    "chelsea",
    "tottenham",
    "bayern munich",
    "bayern",
    "borussia dortmund",
    "psg",
    "paris saint-germain",
    "juventus",
    "inter milan",
    "inter",
    "ac milan",
    "milan",
    "atletico madrid",
    "napoli",
    "roma",
    "newcastle",
    "aston villa",
    "al hilal",
    "al nassr",
    "al ahly",
    "galatasaray",
    "fenerbahce",
    "ajax",
    "benfica",
    "porto",
]


# =========================================================
# MASHHUR FUTBOLCHILAR
# =========================================================

MAJOR_PLAYERS = [
    "mbappe",
    "kylian mbappe",
    "vinicius",
    "vinicius junior",
    "bellingham",
    "jude bellingham",
    "haaland",
    "erling haaland",
    "salah",
    "mohamed salah",
    "lionel messi",
    "messi",
    "cristiano ronaldo",
    "ronaldo",
    "lewandowski",
    "robert lewandowski",
    "de bruyne",
    "kevin de bruyne",
    "rodri",
    "yamal",
    "lamine yamal",
    "pedri",
    "saka",
    "bukayo saka",
    "rashford",
    "bruno fernandes",
    "kane",
    "harry kane",
    "son heung-min",
    "neymar",
    "viktor gyokeres",
    "osimhen",
    "lautaro martinez",
    "griezmann",
    "foden",
    "phil foden",
    "palmer",
    "cole palmer",
    "musiala",
    "wirtz",
]


# =========================================================
# KATTA MUSOBAQALAR
# =========================================================

MAJOR_COMPETITIONS = [
    "champions league",
    "uefa champions league",
    "europa league",
    "conference league",
    "premier league",
    "english premier league",
    "la liga",
    "laliga",
    "serie a",
    "bundesliga",
    "ligue 1",
    "world cup",
    "world cup 2026",
    "fifa world cup",
    "euro",
    "european championship",
    "copa america",
    "afcon",
    "fa cup",
    "carabao cup",
    "copa del rey",
    "super cup",
]


# =========================================================
# YORDAMCHI FUNKSIYALAR
# =========================================================

def clean_text(text):
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def safe_json(text):
    """
    Gemini JSON qaytarishda ba'zida ```json ... ``` ishlatadi.
    Shuni tozalaydi.
    """

    text = text.strip()

    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # JSON massivini topishga harakat
    start = text.find("[")
    end = text.rfind("]")

    if start != -1 and end != -1:
        text = text[start:end + 1]

    return json.loads(text)


def contains_major_topic(text):
    """
    Yangilik katta klub, mashhur futbolchi yoki katta
    musobaqaga tegishlimi?
    """

    text = text.lower()

    for item in MAJOR_CLUBS:
        if item in text:
            return True

    for item in MAJOR_PLAYERS:
        if item in text:
            return True

    for item in MAJOR_COMPETITIONS:
        if item in text:
            return True

    return False


# =========================================================
# GEMINI TEXT API
# =========================================================

def ask_gemini(prompt):

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )

    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 5000
        }
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.loads(response.read().decode("utf-8"))

        candidates = result.get("candidates", [])

        if not candidates:
            print("Gemini javob bermadi.")
            return ""

        parts = candidates[0].get("content", {}).get("parts", [])

        text_parts = []

        for part in parts:
            if "text" in part:
                text_parts.append(part["text"])

        return "\n".join(text_parts).strip()

    except urllib.error.HTTPError as e:

        error_body = ""

        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            pass

        print("Gemini HTTP ERROR:", e.code)
        print(error_body)

        return ""

    except Exception as e:

        print("Gemini xatosi:", repr(e))

        return ""


# =========================================================
# RSS RASMLARINI TOPISH
# =========================================================

def get_image_from_item(item):

    # media:content
    for child in item:
        tag = child.tag.lower()

        if "content" in tag or "thumbnail" in tag:

            url = child.attrib.get("url")

            if url and url.startswith("http"):
                return url

    # enclosure
    for child in item:

        if child.tag.lower().endswith("enclosure"):

            url = child.attrib.get("url", "")
            content_type = child.attrib.get("type", "")

            if url and (
                content_type.startswith("image/")
                or re.search(r"\.(jpg|jpeg|png|webp)(\?|$)", url, re.I)
            ):
                return url

    # description ichidagi img
    for child in item:

        if child.tag.lower().endswith("description"):

            description = child.text or ""

            match = re.search(
                r'<img[^>]+src=["\']([^"\']+)["\']',
                description,
                re.I,
            )

            if match:
                return html.unescape(match.group(1))

    return None


# =========================================================
# ARTICLE SAHIFASIDAN ORIGINAL RASM
# =========================================================

def get_og_image(article_url):

    if not article_url:
        return None

    try:

        request = urllib.request.Request(
            article_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "Chrome/120 Safari/537.36"
                )
            }
        )

        with urllib.request.urlopen(request, timeout=20) as response:
            html_data = response.read().decode(
                "utf-8",
                errors="ignore"
            )

        patterns = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                html_data,
                re.I
            )

            if match:

                image_url = html.unescape(match.group(1))

                if image_url.startswith("http"):
                    return image_url

    except Exception as e:

        print("Original rasm topilmadi:", repr(e))

    return None


# =========================================================
# RSS YANGILIKLARNI OLISH
# =========================================================

def get_news():

    all_news = []

    for feed_url in RSS_FEEDS:

        try:

            request = urllib.request.Request(
                feed_url,
                headers={
                    "User-Agent": "FutbolPulseBot/1.0"
                }
            )

            with urllib.request.urlopen(
                request,
                timeout=30
            ) as response:

                xml_data = response.read()

            root = ET.fromstring(xml_data)

            for item in root.iter():

                if not item.tag.lower().endswith("item"):
                    continue

                title = ""
                link = ""
                description = ""

                for child in item:

                    tag = child.tag.lower()

                    if tag.endswith("title"):
                        title = child.text or ""

                    elif tag.endswith("link"):
                        link = child.text or ""

                    elif tag.endswith("description"):
                        description = child.text or ""

                title = clean_text(title)
                description = clean_text(description)

                if not title or not link:
                    continue

                image_url = get_image_from_item(item)

                # RSS ichida rasm bo'lmasa article'dan qidiramiz
                if not image_url:
                    image_url = get_og_image(link)

                combined = f"{title} {description}"

                # Juda oddiy va mavzusiz yangiliklarni oldindan kamaytirish
                if not contains_major_topic(combined):
                    continue

                all_news.append({
                    "title": title,
                    "description": description,
                    "link": link,
                    "image_url": image_url,
                })

        except Exception as e:

            print("RSS xatosi:", repr(e))

    # Duplicate olib tashlash
    unique = []
    seen = set()

    for item in all_news:

        key = item["title"].lower()

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    return unique[:30]


# =========================================================
# GEMINI YANGILIK TANLASH
# =========================================================

def select_news_with_ai(news):

    if not news:
        return []

    news_text = []

    for index, item in enumerate(news):

        news_text.append(
            f"""
NEWS {index}

TITLE:
{item["title"]}

DESCRIPTION:
{item["description"]}

SOURCE:
{item["link"]}
"""
        )

    prompt = f"""
Sen Futbol Pulse uchun professional futbol muharririsan.

Vazifang: berilgan yangiliklardan faqat futbol muxlislarini
haqiqatan qiziqtiradigan eng muhimlarini tanlash.

QAT'IY FILTR:

1. Oddiy va ahamiyatsiz klublar haqidagi yangiliklarni tanlama.
2. Katta va mashhur klublarga ustuvorlik ber:
   Real Madrid, Barcelona, Manchester United, Manchester City,
   Liverpool, Arsenal, Chelsea, Bayern, PSG, Juventus,
   Inter, Milan, Atletico Madrid va boshqa katta klublar.
3. Mashhur futbolchilar haqidagi muhim yangiliklarga ustuvorlik ber.
4. Champions League, Premier League, La Liga, Serie A,
   Bundesliga, Ligue 1, World Cup, EURO kabi katta musobaqalarga
   ustuvorlik ber.
5. Katta transferlar, muhim jarohatlar, murabbiy almashinuvi,
   katta mojarolar yoki muhim rasmiy qarorlar qiziq.
6. Oddiy mashg'ulot, oddiy intervyu, kichik klubning oddiy
   yangiligi, past ahamiyatli statistikani tanlama.
7. Bir xil mazmundagi yangiliklardan faqat bittasini tanla.
8. Eng ko'p qiziqish uyg'otadigan yangiliklarni yuqoriga qo'y.
9. Maksimal 5 ta yangilik tanla.
10. Hech qanday faktni o'zingdan qo'shma.

O'YIN ANONSLARI UCHUN:

Faqat juda qiziqarli va ko'pchilik kutayotgan bo'lajak
o'yinlarni tanla.

Masalan:
- Real Madrid vs Barcelona
- Manchester City vs Liverpool
- Arsenal vs Manchester United
- Bayern vs PSG
- Champions League katta uchrashuvlari

Oddiy yoki kam qiziqishdagi o'yinlarni anons qilma.

image_mode:

"original" — oddiy yangilik, transfer, jarohat, natija va hokazo.

"ai" — faqat muhim BO'LAJAK o'yin/anons bo'lsa.

match_datetime_utc:

Faqat manbada o'yinning aniq sanasi va vaqti berilgan bo'lsa
uni UTC formatida yoz.

Agar manbada aniq vaqt bo'lmasa:
""

Juda muhim:
- Vaqtni taxmin qilma.
- Sana yoki vaqtni o'ylab topma.

JSON formatida javob ber:

[
  {{
    "title_uz": "O'zbekcha qisqa sarlavha",
    "text_uz": "O'zbekcha 2-4 gaplik mazmunli matn",
    "category": "player|transfer|match|result|injury|manager|breaking|other",
    "importance": 1,
    "image_mode": "original|ai",
    "match_datetime_utc": ""
  }}
]

importance 1 dan 10 gacha.

Faqat 7 yoki undan yuqori importance bo'lgan
yangiliklarni tanla.

YANGILIKLAR:

{''.join(news_text)}
"""

    response = ask_gemini(prompt)

    if not response:
        return []

    try:

        selected = safe_json(response)

    except Exception as e:

        print("Gemini JSON xatosi:", repr(e))
        print("Javob:", response)

        return []

    result = []

    for selected_item in selected:

        importance = selected_item.get("importance", 0)

        try:
            importance = int(importance)
        except Exception:
            importance = 0

        if importance < 7:
            continue

        title = selected_item.get("title_uz", "").strip()
        text = selected_item.get("text_uz", "").strip()

        if not title or not text:
            continue

        # Original newsni topamiz
        source_item = None

        selected_title = title.lower()

        for original in news:

            original_text = (
                original["title"] + " " +
                original["description"]
            ).lower()

            # AI sarlavhasida source title'dagi asosiy so'zlar
            # bilan bog'lashga harakat
            words = [
                w for w in re.findall(
                    r"[a-zA-ZÀ-ÿА-Яа-я0-9]+",
                    original["title"].lower()
                )
                if len(w) >= 5
            ]

            matches = sum(
                1 for word in words
                if word in selected_title
            )

            if matches >= 1:
                source_item = original
                break

        # Agar topilmasa, navbatdagi mos item
        if source_item is None and news:
            source_item = news[0]

        result.append({
            "title_uz": title,
            "text_uz": text,
            "category": selected_item.get(
                "category",
                "other"
            ),
            "importance": importance,
            "image_mode": selected_item.get(
                "image_mode",
                "original"
            ),
            "match_datetime_utc": selected_item.get(
                "match_datetime_utc",
                ""
            ),
            "image_url": (
                source_item.get("image_url")
                if source_item else None
            ),
            "source_link": (
                source_item.get("link")
                if source_item else ""
            ),
        })

    return result[:5]


# =========================================================
# AI MATCH POSTER
# =========================================================

def generate_ai_match_image(title, text):

    prompt = f"""
Create a professional football news poster for "Futbol Pulse".

FORMAT:
16:9 landscape.

SUBJECT:
{title}

STORY:
{text}

STYLE:
- premium modern football media design
- dramatic stadium atmosphere
- cinematic lighting
- realistic football photography style
- energetic match-day atmosphere
- two opposing teams facing each other
- visually show a dramatic player-versus-player duel
- use the clubs' recognizable colors and football identity
- if specific players are explicitly named in the story, visually represent those players
- otherwise use generic star footballers without claiming a specific identity
- strong composition suitable for Telegram football news
- no final score
- do not imply that the match has already happened
- do not create fake statistics
- do not add fake quotes

TEXT:
Keep text on the image minimal.
Do not add long paragraphs.
"""

    url = (
        "https://generativelanguage.googleapis.com/v1/models/"
        f"{GEMINI_IMAGE_MODEL}:generateContent"
    )

    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": [
                "IMAGE"
            ],
            "imageConfig": {
                "aspectRatio": "16:9"
            }
        }
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY,
        },
        method="POST",
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=180
        ) as response:

            result = json.loads(
                response.read().decode("utf-8")
            )

        candidates = result.get("candidates", [])

        if not candidates:
            print("AI rasm: candidate topilmadi.")
            return None

        parts = candidates[0].get(
            "content",
            {}
        ).get(
            "parts",
            []
        )

        for part in parts:

            # API turli naming qaytarishi mumkin
            image_data = part.get("inlineData")

            if not image_data:
                image_data = part.get("inline_data")

            if image_data:

                encoded = image_data.get("data")

                if encoded:

                    return base64.b64decode(
                        encoded
                    )

    except urllib.error.HTTPError as e:

        error_body = ""

        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            pass

        print("AI RASM HTTP ERROR:", e.code)
        print(error_body)

    except Exception as e:

        print("AI rasm xatosi:", repr(e))

    return None


# =========================================================
# ORIGINAL RASMNI YUKLASH
# =========================================================

def download_image(image_url):

    if not image_url:
        return None

    try:

        request = urllib.request.Request(
            image_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "Chrome/120 Safari/537.36"
                )
            }
        )

        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:

            data = response.read()

            content_type = response.headers.get(
                "Content-Type",
                ""
            ).lower()

            if (
                data
                and (
                    content_type.startswith("image/")
                    or data[:3] == b"\xff\xd8\xff"
                    or data[:8] == b"\x89PNG\r\n\x1a\n"
                )
            ):
                return data

    except Exception as e:

        print("Rasm yuklash xatosi:", repr(e))

    return None


# =========================================================
# VAQTNI TOSHKENT VAQTIGA O'GIRISH
# =========================================================

def convert_utc_to_tashkent(utc_string):

    if not utc_string:
        return ""

    try:

        value = utc_string.strip()

        if value.endswith("Z"):
            value = value[:-1] + "+00:00"

        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            return ""

        tashkent = dt.astimezone(TASHKENT_TZ)

        return tashkent.strftime(
            "%d.%m.%Y | %H:%M"
        )

    except Exception as e:

        print("Vaqt konvertatsiyasi xatosi:", repr(e))

        return ""


# =========================================================
# CATEGORY EMOJILAR
# =========================================================

CATEGORY_EMOJI = {
    "player": "⭐",
    "transfer": "🔄",
    "match": "🔥",
    "result": "⚽",
    "injury": "🚑",
    "manager": "🧠",
    "breaking": "🚨",
    "other": "📰",
}


# =========================================================
# TELEGRAM POST
# =========================================================

def create_post(item):

    category = item.get(
        "category",
        "other"
    )

    emoji = CATEGORY_EMOJI.get(
        category,
        "📰"
    )

    title = html.escape(
        item.get("title_uz", "")
    )

    text = html.escape(
        item.get("text_uz", "")
    )

    post = (
        f"{emoji} <b>{title}</b>\n\n"
        f"{text}"
    )

    # Bo'lajak muhim o'yin
    if item.get("image_mode") == "ai":

        match_time = convert_utc_to_tashkent(
            item.get(
                "match_datetime_utc",
                ""
            )
        )

        if match_time:

            post += (
                "\n\n"
                f"🕐 <b>Toshkent vaqti:</b> "
                f"{html.escape(match_time)}"
            )

        post += "\n\n🔥 <b>Muhim o'yin anonsi</b>"

    post += (
        "\n\n"
        f'⚽ <a href="{CHANNEL_LINK}">'
        f"Futbol Pulse</a>"
    )

    return post


# =========================================================
# /START
# =========================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "⚽ <b>FUTBOL PULSE</b>\n\n"
        "Bot muvaffaqiyatli ishlayapti! ✅\n\n"
        "/news — eng muhim futbol yangiliklari",
        parse_mode="HTML",
    )


# =========================================================
# /NEWS
# =========================================================

async def news_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    status_message = await update.message.reply_text(
        "⚽ Yangiliklar tekshirilmoqda...\n\n"
        "🤖 Muhim yangiliklar saralanmoqda..."
    )

    try:

        news = get_news()

        if not news:

            await status_message.edit_text(
                "Hozircha mos va muhim yangilik topilmadi. ⚽"
            )

            return

        selected = select_news_with_ai(news)

        if not selected:

            await status_message.edit_text(
                "Hozircha yetarlicha muhim yangilik topilmadi. ⚽"
            )

            return

        await status_message.edit_text(
            f"🔥 {len(selected)} ta muhim yangilik topildi.\n"
            "Postlar tayyorlanmoqda..."
        )

        for item in selected:

            image_bytes = None

            # ==========================================
            # BO'LAJAK MUHIM O'YIN
            # ==========================================

            if item.get("image_mode") == "ai":

                print(
                    "AI match poster yaratilmoqda:",
                    item["title_uz"]
                )

                image_bytes = generate_ai_match_image(
                    item["title_uz"],
                    item["text_uz"]
                )

            # ==========================================
            # ODDIY YANGILIK
            # ORIGINAL RASM
            # ==========================================

            if image_bytes is None:

                image_url = item.get(
                    "image_url"
                )

                if image_url:

                    print(
                        "Original rasm yuklanmoqda:",
                        image_url
                    )

                    image_bytes = download_image(
                        image_url
                    )

            post = create_post(item)

            # Telegram photo caption 1024 belgidan oshmasligi kerak
            if len(post) > 1000:

                post = post[:990] + "..."

            # ==========================================
            # RASM BILAN
            # ==========================================

            if image_bytes:

                photo = io.BytesIO(
                    image_bytes
                )

                photo.name = "futbol_pulse.jpg"

                try:

                    await update.message.reply_photo(
                        photo=photo,
                        caption=post,
                        parse_mode="HTML",
                        disable_notification=False,
                    )

                except Exception as e:

                    print(
                        "Rasmli post xatosi:",
                        repr(e)
                    )

                    await update.message.reply_text(
                        post,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )

            # ==========================================
            # RASMSIZ
            # ==========================================

            else:

                await update.message.reply_text(
                    post,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )

        await status_message.edit_text(
            "✅ Muhim yangiliklar yuborildi."
        )

    except Exception as e:

        print(
            "NEWS COMMAND ERROR:",
            repr(e)
        )

        await status_message.edit_text(
            "❌ Yangiliklarni olishda xatolik yuz berdi."
        )


# =========================================================
# MAIN
# =========================================================

def main():

    print("====================================")
    print("⚽ FUTBOL PULSE BOT")
    print("====================================")
    print("Bot ishga tushmoqda...")
    print("Gemini text:", GEMINI_MODEL)
    print("Gemini image:", GEMINI_IMAGE_MODEL)
    print("Toshkent timezone: Asia/Tashkent")
    print("====================================")

    app = (
        Application
        .builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start_command
        )
    )

    app.add_handler(
        CommandHandler(
            "news",
            news_command
        )
    )

    print("Bot polling rejimida ishlayapti...")

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
