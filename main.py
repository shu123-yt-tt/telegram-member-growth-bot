
import os
import sqlite3
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ChatJoinRequestHandler,
    ContextTypes
)

TOKEN = os.environ["BOT_TOKEN"]
DB = "members.db"

def setup():
    con = sqlite3.connect(DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS groups_data (
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            owner_id INTEGER,
            target INTEGER DEFAULT 0
        )
    """)
    con.commit()
    con.close()

def save_group(chat_id, title, owner):
    con = sqlite3.connect(DB)
    con.execute(
        "INSERT OR REPLACE INTO groups_data "
        "(chat_id,title,owner_id,target) "
        "VALUES (?, ?, ?, COALESCE("
        "(SELECT target FROM groups_data WHERE chat_id=?),0))",
        (chat_id, title, owner, chat_id)
    )
    con.commit()
    con.close()

def get_group(chat_id):
    con = sqlite3.connect(DB)
    result = con.execute(
        "SELECT * FROM groups_data WHERE chat_id=?",
        (chat_id,)
    ).fetchone()
    con.close()
    return result

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to Member Growth Bot!\n\n"
        "/register - Register a group (inside group)\n"
        "/groups - Your registered groups\n"
        "/invite CHAT_ID - Generate invite link\n"
        "/target CHAT_ID NUMBER - Set target\n"
        "/stats CHAT_ID - View statistics"
    )

async def register(update: Update, context):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        return await update.message.reply_text(
            "Use /register inside your group."
        )

    member = await context.bot.get_chat_member(
        chat.id, user.id
    )

    if member.status not in ("administrator", "creator"):
        return await update.message.reply_text(
            "Only group admins can register this group."
        )

    bot_member = await context.bot.get_chat_member(
        chat.id, context.bot.id
    )

    if bot_member.status != "administrator":
        return await update.message.reply_text(
            "Please make me a group admin first."
        )

    save_group(chat.id, chat.title, user.id)

    await update.message.reply_text(
        f"Group registered successfully: {chat.title}"
    )

async def groups(update: Update, context):
    user_id = update.effective_user.id
    con = sqlite3.connect(DB)

    rows = con.execute(
        "SELECT chat_id,title FROM groups_data "
        "WHERE owner_id=?", (user_id,)
    ).fetchall()

    con.close()

    if not rows:
        return await update.message.reply_text(
            "No registered groups found."
        )

    msg = "Your registered groups:\n\n"
    for chat_id, title in rows:
        msg += f"{title}\nID: {chat_id}\n\n"

    await update.message.reply_text(msg)

async def invite(update: Update, context):
    if len(context.args) != 1:
        return await update.message.reply_text(
            "Usage: /invite CHAT_ID"
        )

    try:
        chat_id = int(context.args[0])
    except ValueError:
        return await update.message.reply_text("Invalid group ID.")

    group = get_group(chat_id)

    if not group or group[2] != update.effective_user.id:
        return await update.message.reply_text(
            "Group not registered by you."
        )

    link = await context.bot.create_chat_invite_link(
        chat_id=chat_id,
        creates_join_request=True,
        name="Member Growth Campaign"
    )

    await update.message.reply_text(
        f"Your invite link:\n{link.invite_link}\n\n"
        "Users can request to join using this link."
    )

async def target(update: Update, context):
    if len(context.args) != 2:
        return await update.message.reply_text(
            "Usage: /target CHAT_ID NUMBER"
        )

    try:
        chat_id = int(context.args[0])
        number = int(context.args[1])
        if number < 1:
            raise ValueError
    except ValueError:
        return await update.message.reply_text("Invalid numbers.")

    group = get_group(chat_id)

    if not group or group[2] != update.effective_user.id:
        return await update.message.reply_text(
            "Group not registered by you."
        )

    con = sqlite3.connect(DB)
    con.execute(
        "UPDATE groups_data SET target=? WHERE chat_id=?",
        (number, chat_id)
    )
    con.commit()
    con.close()

    await update.message.reply_text(
        f"Member target set to {number}."
    )

async def stats(update: Update, context):
    if len(context.args) != 1:
        return await update.message.reply_text(
            "Usage: /stats CHAT_ID"
        )

    try:
        chat_id = int(context.args[0])
    except ValueError:
        return await update.message.reply_text("Invalid group ID.")

    group = get_group(chat_id)

    if not group or group[2] != update.effective_user.id:
        return await update.message.reply_text(
            "Group not registered by you."
        )

    count = await context.bot.get_chat_member_count(chat_id)
    target_count = group[3]
    remaining = max(0, target_count - count)

    await update.message.reply_text(
        f"Group: {group[1]}\n"
        f"Current total members: {count}\n"
        f"Target: {target_count}\n"
        f"Remaining: {remaining}"
    )

async def approve_request(update: Update, context):
    request = update.chat_join_request
    group = get_group(request.chat.id)

    if not group:
        return

    try:
        await context.bot.approve_chat_join_request(
            request.chat.id,
            request.from_user.id
        )
    except Exception as e:
        print("Approval error:", e)

def main():
    setup()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("groups", groups))
    app.add_handler(CommandHandler("invite", invite))
    app.add_handler(CommandHandler("target", target))
    app.add_handler(CommandHandler("stats", stats))

    app.add_handler(
        ChatJoinRequestHandler(approve_request)
    )

    print("Member Growth Bot is running!")
    app.run_polling()

if __name__ == "__main__":
    main()
