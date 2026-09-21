import os
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

RSS_URLS = [
    "https://www.theguardian.com/football/rss",
    "https://feeds.bbci.co.uk/sport/football/rss.xml",
]


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

            with urllib.request.urlopen(request, timeout=15) as response:
                data = response.read()

            root = ET.fromstring(data)

            for item in root.findall(".//item"):
                title = item.findtext("title", "")
                link = item.findtext("link", "")

                if title and link:
                    news.append((title.strip(), link.strip()))

        except Exception as e:
            print(f"RSS xatosi: {e}")

    # Bir xil yangiliklarni olib tashlash
    unique_news = []
    seen = set()

    for title, link in news:
        if link not in seen:
            seen.add(link)
            unique_news.append((title, link))

    return unique_news[:10]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ FUTBOL PULSE\n\n"
        "Bot muvaffaqiyatli ishlayapti! ✅\n\n"
        "/news — so‘nggi futbol yangiliklarini olish"
    )


async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    articles = get_news()

    if not articles:
        await update.message.reply_text(
            "❌ Hozircha yangilik topilmadi."
        )
        return

    message = "⚽ FUTBOL PULSE — SO‘NGGI YANGILIKLAR\n\n"

    for i, (title, link) in enumerate(articles, 1):
        message += f"{i}. {title}\n{link}\n\n"

    # Telegram xabar limiti
    await update.message.reply_text(message[:4000])


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news))

    print("⚽ Futbol Pulse bot ishga tushdi!")

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
