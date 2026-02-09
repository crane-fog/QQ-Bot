import asyncio

from src.Bot import Bot


async def main():
    config_file = "configs/bot.ini"

    bot = Bot(
        config_file=config_file,
    )
    await bot.initialize()
    # bot.runWebCtrler()
    bot.run()


asyncio.run(main())
