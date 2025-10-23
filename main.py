import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from bot.handlers import dp, bot


async def main():
    try:
        print("Bot starting...")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
