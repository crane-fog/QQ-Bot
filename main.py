import asyncio

from src.Bot import Bot


async def main():
    bot = Bot(configs_path="configs", plugins_path="plugins")
    bot.initialize()
    await bot.run()


asyncio.run(main())
