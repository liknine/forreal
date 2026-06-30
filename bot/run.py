import asyncio

import uvicorn

from api import app
from config import config
from main import main as bot_main


async def api_main() -> None:
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=config.api_host,
            port=config.api_port,
            log_level="info",
        )
    )
    await server.serve()


async def main() -> None:
    await asyncio.gather(
        bot_main(),
        api_main(),
    )


if __name__ == "__main__":
    asyncio.run(main())
