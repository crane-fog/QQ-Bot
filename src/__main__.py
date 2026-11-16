"""仅启动 Bot 本身（``python -m src``），不拉起守护进程与面板。

完整部署（守护进程 + 面板 + Bot）走 ``main.py``；本入口供只想运行 Bot、
或守护进程拉起 Bot 子进程时使用。
"""

import asyncio

from src.Bot import Bot


async def main():
    bot = Bot(configs_path="configs", plugins_path="plugins")
    bot.initialize()
    await bot.run()


asyncio.run(main())
