import logging
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters
from config.settings import TELEGRAM_TOKEN
from db.database import get_pool, init_db
from bot.handlers import handle_message
from bot.commands import (
    cmd_help, cmd_list, cmd_today, cmd_cat,
    cmd_search, cmd_delete, cmd_edit,
    cmd_done, cmd_skip, cmd_save, cmd_cancel,
    cmd_deep, cmd_review, cmd_quiz,
    cmd_stats, cmd_summary, cmd_export,
    cmd_recall,
    cmd_soc, cmd_nosoc,
    cmd_mode,
)

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


def main():
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start",   cmd_help))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("list",    cmd_list))
    app.add_handler(CommandHandler("today",   cmd_today))
    app.add_handler(CommandHandler("cat",     cmd_cat))
    app.add_handler(CommandHandler("search",  cmd_search))
    app.add_handler(CommandHandler("delete",  cmd_delete))
    app.add_handler(CommandHandler("edit",    cmd_edit))
    app.add_handler(CommandHandler("done",    cmd_done))
    app.add_handler(CommandHandler("skip",    cmd_skip))
    app.add_handler(CommandHandler("save",    cmd_save))
    app.add_handler(CommandHandler("cancel",  cmd_cancel))
    app.add_handler(CommandHandler("recall",  cmd_recall))
    app.add_handler(CommandHandler("soc",     cmd_soc))
    app.add_handler(CommandHandler("nosoc",   cmd_nosoc))
    app.add_handler(CommandHandler("deep",    cmd_deep))
    app.add_handler(CommandHandler("review",  cmd_review))
    app.add_handler(CommandHandler("quiz",    cmd_quiz))
    app.add_handler(CommandHandler("stats",   cmd_stats))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(CommandHandler("export",  cmd_export))
    app.add_handler(CommandHandler("mode",    cmd_mode))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Bot đang chạy...")
    app.run_polling()


if __name__ == "__main__":
    main()