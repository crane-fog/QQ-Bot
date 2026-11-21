import asyncio

from src.deployment.runtime import launch

try:
    asyncio.run(launch())
except KeyboardInterrupt:
    # Windows 的 Ctrl+C 以取消/中断形式到达，进程树已在 launch 的清理中停止。
    pass
