import logging
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters
from config.settings import TELEGRAM_TOKEN
from db.database import init_db
from bot.handlers import handle_message
from bot.commands import cmd_help, cmd_list, cmd_search
import asyncio

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def main():
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(lambda _: init_db())
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
