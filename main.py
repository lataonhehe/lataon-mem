import logging
import asyncpg
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters
from config.settings import TELEGRAM_TOKEN
from db.database import get_pool, init_db
from bot.handlers import handle_message
from bot.commands import cmd_help, cmd_list, cmd_search

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


async def on_startup(app):
    pool = await get_pool()
    await init_db(pool)
    app.bot_data["pool"] = pool
    logging.info("Database kết nối thành công.")


async def on_shutdown(app):
    pool = app.bot_data.get("pool")
    if pool:
        await pool.close()
        logging.info("Database pool đã đóng.")


def main():
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Bot đang chạy...")
    app.run_polling()


if __name__ == "__main__":
    main()
