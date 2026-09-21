import os
import json
import urllib.request
import urllib.parse

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN topilmadi")


def telegram(method, data=None):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"

    if data:
        data = urllib.parse.urlencode(data).encode()

    request = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode())


def send_message(chat_id, text):
    telegram(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text
        }
    )


def main():
    offset = 0

    print("⚽ Futbol Pulse bot ishga tushdi!")

    while True:
        result = telegram(
            "getUpdates",
            {
                "offset": offset,
                "timeout": 30
            }
        )

        for update in result.get("result", []):
            offset = update["update_id"] + 1

            message = update.get("message")

            if not message:
                continue

            chat_id = message["chat"]["id"]
            text = message.get("text", "")

            if text == "/start":
                send_message(
                    chat_id,
                    "⚽ FUTBOL PULSE\n\n"
                    "Bot muvaffaqiyatli ishga tushdi! ✅\n\n"
                    "Tez orada futbol yangiliklari, "
                    "transferlar, o‘yinlar va statistikalar avtomatik chiqadi."
                )

            elif text == "/test":
                send_message(
                    chat_id,
                    "✅ Futbol Pulse bot ishlayapti!"
                )


if __name__ == "__main__":
    main()
