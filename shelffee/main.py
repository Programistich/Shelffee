import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web

from shelffee.config import settings
from shelffee.handlers import router
from shelffee.webapp import setup_routes


async def run_web(bot_username: str) -> None:
    app = web.Application(client_max_size=4 * 1024 * 1024)
    app["bot_username"] = bot_username
    setup_routes(app)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.web_host, settings.web_port)
    await site.start()
    logging.info("Web app listening on %s:%s", settings.web_host, settings.web_port)
    await asyncio.Event().wait()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.me()
    await asyncio.gather(dp.start_polling(bot), run_web(me.username))


if __name__ == "__main__":
    asyncio.run(main())
