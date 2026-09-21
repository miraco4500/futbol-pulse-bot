import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


# =========================
# SETTINGS
# =========================

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

CHANNEL_USERNAME = "@Futbol_Pulse24"
CHANNEL_LINK = "https://t.me/Futbol_Pulse24"

GEMINI_MODEL = "gemini-3.1-flash"

RSS_URLS = [
    "https://www.theguardian.com/football/rss",
    "https://feeds.bbci.co.uk/sport/football/rss.xml",
]


# =========================
# RSS NEWS
# =========================

def get_news():
    news = []

    for rss_url in RSS_URLS:
        try:
            request = urllib.request.Request(
                rss_url,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            with urllib.request.urlopen(
                request,
                timeout=20
            ) as response:
                data = response.read()

            root = ET.fromstring(data)

            for item in root.findall(".//item"):
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                description = item.findtext(
                    "description",
                    ""
                ).strip()

                if title and link:
                    news.append({
                        "title": title,
                        "link": link,
                        "description": description
                    })

        except Exception as e:
            print(f"RSS xatosi: {e}")

    # Duplicate yangiliklarni olib tashlash
    unique_news = []
    seen = set()

    for item in news:
        key = item["title"].lower()

        if key not in seen:
            seen.add(key)
            unique_news.append(item)

    return unique_news[:30]


# =========================
# GEMINI
# =========================

def ask_gemini(prompt):
    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{GEMINI_MODEL}:generateContent"
    )

    body = {
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
            "temperature": 0.3,
            "maxOutputTokens": 4096
        }
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        },
        method="POST"
    )

    with urllib.request.urlopen(
        request,
        timeout=60
    ) as response:
        result = json.loads(
            response.read().decode("utf-8")
        )

    try:
        return (
            result["candidates"][0]
            ["content"]["parts"][0]["text"]
        )
    except Exception:
        print("Gemini javobi:")
        print(result)
        return ""


# =========================
# AI NEWS SELECTION
# =========================

def select_news_with_ai(news):
    if not news:
        return []

    news_text = ""

    for i, item in enumerate(news, 1):
        news_text += (
            f"{i}. {item['title']}\n"
            f"DESCRIPTION: {item['description']}\n\n"
        )

    prompt = f"""
You are the editor of a professional Uzbek football Telegram channel.

Channel:
Futbol Pulse

Your task:

1. Read the football news below.
2. Select ONLY the most interesting and important stories.
3. Do NOT select routine or boring stories.
4. Prioritize:
   - famous footballers
   - major clubs
   - Champions League
   - important transfers
   - major injuries
   - managers
   - derbies
   - big match results
   - breaking news
   - important player records
5. Maximum 5 stories.
6. Do not invent facts.
7. Use only information contained in the provided news.

For every selected story create:

- title_uz
- text_uz
- category

Categories:
player
transfer
match
result
injury
manager
breaking
other

The title must be attractive but factual.

The text must be 2-4 short Uzbek sentences.

Do NOT include the original source URL.

Return ONLY valid JSON.

Format:

[
  {{
    "title_uz": "...",
    "text_uz": "...",
    "category": "player"
  }}
]

NEWS:

{news_text}
"""

    response = ask_gemini(prompt)

    if not response:
        return []

    # Gemini ba'zida ```json ... ``` qaytarishi mumkin
    response = response.strip()

    if response.startswith("```"):
        response = response.replace(
            "```json",
            ""
        ).replace(
            "```",
            ""
        ).strip()

    try:
        data = json.loads(response)

        if isinstance(data, list):
            return data[:5]

    except Exception as e:
        print(f"JSON xatosi: {e}")
        print(response)

    return []


# =========================
# FORMAT TELEGRAM POST
# =========================

def create_post(item):
    title = item.get(
        "title_uz",
        "Futbol yangiligi"
    )

    text = item.get(
        "text_uz",
        ""
    )

    category = item.get(
        "category",
        "other"
    )

    emoji = {
        "player": "⭐",
        "transfer": "🔥",
        "match": "⚔️",
        "result": "🏆",
        "injury": "🚑",
        "manager": "🎙️",
        "breaking": "🚨",
        "other": "⚽"
    }.get(category, "⚽")

    post = (
        f"{emoji} <b>{title}</b>\n\n"
        f"{text}\n\n"
        f"📲 <a href=\"{CHANNEL_LINK}\">"
        f"Futbol Pulse</a>"
    )

    return post


# =========================
# /START
# =========================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        "⚽ <b>FUTBOL PULSE</b>\n\n"
        "Bot muvaffaqiyatli ishlayapti! ✅\n\n"
        "/news — eng qiziqarli futbol yangiliklari",
        parse_mode="HTML"
    )


# =========================
# /NEWS
# =========================

async def news_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "⚽ Yangiliklar tekshirilmoqda...\n"
        "🤖 Gemini eng muhimlarini tanlamoqda."
    )

    news = get_news()

    if not news:
        await update.message.reply_text(
            "❌ Hozircha yangilik topilmadi."
        )
        return

    selected = select_news_with_ai(news)

    if not selected:
        await update.message.reply_text(
            "❌ Gemini yangiliklarni qayta ishlay olmadi."
        )
        return

    for item in selected:
        post = create_post(item)

        await update.message.reply_text(
            post,
            parse_mode="HTML",
            disable_web_page_preview=True
        )


# =========================
# MAIN
# =========================

def main():

    app = (
        Application
        .builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "news",
            news_command
        )
    )

    print(
        "⚽ Futbol Pulse AI bot ishga tushdi!"
    )

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
