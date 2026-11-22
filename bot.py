# -*- coding: utf-8 -*-
"""
Телеграм-бот для приёма заявок.

Что умеет:
  1. Здоровается и задаёт 3 вопроса: имя, телефон, задача.
  2. Сохраняет заявку в файл leads.csv (открывается в Excel).
  3. Присылает уведомление тебе в Телеграм.

Сторонние библиотеки НЕ нужны — только Python.
Запуск: двойной клик по файлу "запустить.bat"
"""

import csv
import json
import os
import time
import traceback
import urllib.parse
import urllib.request
from datetime import datetime

# ---------- настройки ----------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.txt")
LEADS_FILE = os.path.join(BASE_DIR, "leads.csv")
LOG_FILE = os.path.join(BASE_DIR, "log.txt")


def log(text):
    """Пишет сообщение и в окно, и в файл log.txt (чтобы можно было разобраться, что случилось)."""
    line = datetime.now().strftime("%H:%M:%S") + "  " + str(text)
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

GREETING = (
    "Здравствуйте! Это бот для заявок.\n\n"
    "Ответьте на 3 коротких вопроса — и я передам заявку менеджеру.\n\n"
    "Как вас зовут?"
)

THANKS = (
    "Спасибо! Заявка принята.\n\n"
    "Менеджер свяжется с вами в ближайшее время."
)

# ---------- конфиг ----------


def load_config():
    """Читает config.txt вида:  TOKEN=123:abc  /  OWNER_ID=123456789"""
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                cfg[key.strip()] = value.strip()
    return cfg


CFG = load_config()
TOKEN = CFG.get("TOKEN", "")
try:
    OWNER_ID = int(CFG.get("OWNER_ID", "0") or 0)
except ValueError:
    OWNER_ID = 0

API = "https://api.telegram.org/bot" + TOKEN + "/"


# ---------- общение с Телеграмом ----------


def api_call(method, **params):
    """Отправляет запрос в Телеграм и возвращает ответ."""
    data = urllib.parse.urlencode(params).encode("utf-8")
    request = urllib.request.Request(API + method, data=data)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def send_message(chat_id, text):
    try:
        api_call("sendMessage", chat_id=chat_id, text=text)
    except Exception as error:
        log(f"[!] Не смог отправить сообщение: {error}")


def notify_owner(lead):
    """Уведомление владельцу бота."""
    if not OWNER_ID:
        return
    text = (
        "Новая заявка\n\n"
        f"Имя: {lead['name']}\n"
        f"Телефон: {lead['phone']}\n"
        f"Задача: {lead['task']}\n"
    )
    if lead.get("username"):
        text += f"Телеграм: @{lead['username']}\n"
    send_message(OWNER_ID, text)


# ---------- сохранение заявок ----------


def save_lead(lead):
    """Дописывает заявку в leads.csv. Если файла нет — создаёт с заголовком."""
    headers = ["Дата", "Имя", "Телефон", "Задача", "Telegram", "ID чата"]

    if not os.path.exists(LEADS_FILE):
        # utf-8-sig — чтобы Excel правильно понял русские буквы
        with open(LEADS_FILE, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(headers)

    with open(LEADS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            lead["name"],
            lead["phone"],
            lead["task"],
            ("@" + lead["username"]) if lead.get("username") else "",
            lead["chat_id"],
        ])


# ---------- логика диалога ----------

# chat_id -> {"step": "...", "name": ..., "phone": ...}
users = {}

# шаги: name -> phone -> task -> готово


def is_phone(text):
    digits = "".join(ch for ch in text if ch.isdigit())
    return len(digits) >= 10


def handle_message(message):
    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    username = message["chat"].get("username") or ""

    if not text:
        send_message(chat_id, "Пожалуйста, ответьте текстом.")
        return

    # команды работают в любой момент
    if text.startswith("/"):
        cmd = text.split()[0].lower()

        if cmd == "/start":
            users[chat_id] = {"step": "name"}
            send_message(chat_id, GREETING)

        elif cmd == "/myid":
            send_message(chat_id, f"Твой ID: {chat_id}\nВпиши его в config.txt → OWNER_ID=")

        elif cmd == "/cancel":
            users.pop(chat_id, None)
            send_message(chat_id, "Отменено. Начать заново — /start")

        elif cmd == "/help":
            send_message(chat_id, "Команды:\n/start — оставить заявку\n/cancel — отменить\n/myid — узнать свой ID")

        else:
            send_message(chat_id, "Не знаю такую команду. Начать заново — /start")

        return

    state = users.get(chat_id)

    if not state:
        send_message(chat_id, "Чтобы оставить заявку, отправьте /start")
        return

    step = state.get("step")

    if step == "name":
        state["name"] = text
        state["step"] = "phone"
        send_message(chat_id, "Приятно познакомиться! Ваш телефон для связи?")

    elif step == "phone":
        if not is_phone(text):
            send_message(chat_id, "Похоже, это не телефон. Введите номер, например: +7 900 123-45-67")
            return
        state["phone"] = text
        state["step"] = "task"
        send_message(chat_id, "Отлично. Что нужно сделать? Опишите задачу в двух словах.")

    elif step == "task":
        lead = {
            "name": state["name"],
            "phone": state["phone"],
            "task": text,
            "username": username,
            "chat_id": chat_id,
        }
        save_lead(lead)
        notify_owner(lead)
        users.pop(chat_id, None)
        send_message(chat_id, THANKS)
        log(f"[+] Заявка сохранена: {lead['name']} / {lead['phone']} / {lead['task']}")


# ---------- запуск ----------


def main():
    if not TOKEN or TOKEN.startswith("ВСТАВЬ"):
        log("=" * 60)
        log("  НЕ НАСТРОЕН ТОКЕН")
        log("=" * 60)
        log("  1. Открой config.txt (правой кнопкой -> Блокнот)")
        log("  2. Впиши токен, который выдал @BotFather")
        log("  3. Сохрани файл и запусти снова")
        log("=" * 60)
        return

    log("Бот запущен. Это окно не закрывай.")
    log("Открой Телеграм и напиши своему боту /start")
    log("Чтобы остановить — закрой окно или нажми Ctrl+C")

    offset = 0
    while True:
        try:
            updates = api_call("getUpdates", offset=offset, timeout=50)["result"]
            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message")
                if message:
                    try:
                        handle_message(message)
                    except Exception as error:
                        log("[!] Ошибка в обработке сообщения: " + str(error))
        except KeyboardInterrupt:
            log("Бот остановлен.")
            break
        except Exception as error:
            log("[!] Нет связи с Телеграмом: " + str(error))
            time.sleep(3)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("=" * 60)
        log("БОТ УПАЛ. Текст ошибки ниже:")
        log(traceback.format_exc())
        log("=" * 60)
