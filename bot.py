import os
import urllib.request
import xml.etree.ElementTree as ET

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

RSS_URL = "https://www.theguardian.com/football/rss"


def get_news():
    request = urllib.request.Request(
        RSS_URL,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        data = response.read()

    root = ET.fromstring(data)

    news = []

    for item in root.findall(".//item")[:5]:
        title = item.findtext("title", "")
        link = item.findtext("link", "")

        if title and link:
            news.append((title, link))

    return news


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ FUTBOL PULSE\n\n"
        "Bot muvaffaqiyatli ishlayapti! ✅\n\n"
        "/news — so‘nggi futbol yangiliklari"
    )


async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        articles = get_news()

        if not articles:
            await update.message.reply_text(
                "Hozircha yangilik topilmadi."
            )
            return

        message = "⚽ FUTBOL PULSE — SO‘NGGI YANGILIKLAR\n\n"

        for i, (title
