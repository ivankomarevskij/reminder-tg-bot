import re
import uuid
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

TOKEN = "8649152490:AAHwNUIRlJvhbaVdBP68qy4uI54PaSxdZns"

reminders = {}

# ------------------ 🧠 ПАРСИНГ ------------------

# через пів години
def parse_half_hour(text):
    if "пів години" in text:
        return 30 * 60
    return None


# 🔥 оновлений парсер (підтримка 2.5)
def parse_relative_time(text):
    pattern = r'(\d+(?:[.,]\d+)?)\s*(сек|хв|год|годин|хвилин)'
    matches = re.findall(pattern, text)

    if not matches:
        return None

    total_seconds = 0

    for value, unit in matches:
        value = float(value.replace(",", "."))

        if "сек" in unit:
            total_seconds += value
        elif "хв" in unit:
            total_seconds += value * 60
        elif "год" in unit:
            total_seconds += value * 3600

    return int(total_seconds)


def parse_tomorrow(text):
    match = re.search(r'завтра о (\d{1,2})(?::(\d{2}))?', text)
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2)) if match.group(2) else 0

    now = datetime.now()
    target = now + timedelta(days=1)
    target = target.replace(hour=hour, minute=minute, second=0, microsecond=0)

    return target


def parse_daytime(text):
    now = datetime.now()

    if "зранку" in text:
        target = now.replace(hour=9, minute=0, second=0, microsecond=0)
    elif "ввечері" in text:
        target = now.replace(hour=19, minute=0, second=0, microsecond=0)
    else:
        return None

    if target <= now:
        target += timedelta(days=1)

    return target


# ------------------ 🔔 НАГАДУВАННЯ ------------------

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    data = job.data

    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=f"🔔 Нагадування: {data['text']}",
    )

    reminders.pop(data["id"], None)


# ------------------ 📋 СПИСОК ------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Привіт! Я бот-нагадувач\n\n"

        "📌 Я допомагаю ставити нагадування простими словами\n\n"

        "🧠 Я РОЗУМІЮ:\n"
        "• чай через 10 сек\n"
        "• перерва через 5 хв\n"
        "• відпочити через 2 години\n"
        "• піти гуляти через 1 год 20 хв\n"
        "• чай через пів години\n"
        "• перерва через 2.5 години\n\n"

        "📅 Також:\n"
        "• зробити дз завтра о 10\n"
        "• піти гуляти завтра о 18:30\n\n"

        "🌅 Також слова:\n"
        "• зранку (≈09:00)\n"
        "• ввечері (≈19:00)\n\n"

        "📋 Команди:\n"
        "/list — список нагадувань\n\n"

        "❌ Я НЕ розумію:\n"
        "• 'через трохи'\n"
        "• 'якось потім'\n"
        "• 'десь ввечері завтра' (поки що 😅)\n\n"

        "👉 Просто напиши мені, що треба — і я нагадаю 🔔"
    )

    await update.message.reply_text(text)
async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    user_reminders = [
        r for r in reminders.values() if r["user_id"] == user_id
    ]

    if not user_reminders:
        await update.message.reply_text("📭 Немає активних нагадувань")
        return

    text = "📋 Твої нагадування:\n\n"

    for r in user_reminders:
        text += f"• {r['text']} (ID: {r['id']})\n"

    await update.message.reply_text(text)


# ------------------ 🧠 HANDLE ------------------

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    reminder_id = str(uuid.uuid4())[:8]

    # 1️⃣ через пів години
    seconds = parse_half_hour(text)
    if seconds:
        task = re.sub(r'через.*', '', text).strip() or "без тексту 😅"

        context.job_queue.run_once(
            send_reminder,
            when=seconds,
            data={"chat_id": chat_id, "text": task, "id": reminder_id},
        )

        reminders[reminder_id] = {"id": reminder_id, "text": task, "user_id": user_id}

        await update.message.reply_text("⏳ Нагадаю через 30 хв")
        return

    # 2️⃣ завтра
    target_time = parse_tomorrow(text)
    if target_time:
        seconds = (target_time - datetime.now()).total_seconds()

        task = re.sub(r'завтра.*', '', text).strip() or "без тексту 😅"

        context.job_queue.run_once(
            send_reminder,
            when=seconds,
            data={"chat_id": chat_id, "text": task, "id": reminder_id},
        )

        reminders[reminder_id] = {"id": reminder_id, "text": task, "user_id": user_id}

        await update.message.reply_text(
            f"⏰ Нагадаю завтра о {target_time.strftime('%H:%M')}"
        )
        return

    # 3️⃣ зранку / ввечері
    target_time = parse_daytime(text)
    if target_time:
        seconds = (target_time - datetime.now()).total_seconds()

        task = re.sub(r'(зранку|ввечері).*', '', text).strip() or "без тексту 😅"

        context.job_queue.run_once(
            send_reminder,
            when=seconds,
            data={"chat_id": chat_id, "text": task, "id": reminder_id},
        )

        reminders[reminder_id] = {"id": reminder_id, "text": task, "user_id": user_id}

        await update.message.reply_text(
            f"⏰ Нагадаю о {target_time.strftime('%H:%M')}"
        )
        return

    # 4️⃣ через (включно з 2.5 години)
    if "через" in text:
        seconds = parse_relative_time(text)

        if not seconds:
            await update.message.reply_text("❌ Не зрозумів час")
            return

        task = re.sub(r'через.*', '', text).strip() or "без тексту 😅"

        context.job_queue.run_once(
            send_reminder,
            when=seconds,
            data={"chat_id": chat_id, "text": task, "id": reminder_id},
        )

        reminders[reminder_id] = {"id": reminder_id, "text": task, "user_id": user_id}

        await update.message.reply_text(f"⏳ Нагадаю через {seconds} сек")
        return


# ------------------ 🚀 ЗАПУСК ------------------

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("list", list_reminders))
app.add_handler(MessageHandler(filters.TEXT, handle))

app.run_polling()