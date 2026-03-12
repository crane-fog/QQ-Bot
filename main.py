import asyncio

from src.Bot import Bot


async def main():
    bot = Bot(configs_path="configs", plugins_path="plugins")
    await bot.run()


asyncio.run(main())
