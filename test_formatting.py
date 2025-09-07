#!/usr/bin/env python3
"""
Test formatting with current bot setup
"""
import asyncio
import os
import sys
from aiogram import Bot
from aiogram.enums import ParseMode

async def test_send():
    bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
    
    # Simple test message
    test_msg = """🤖 <b>Тест HTML форматирования</b>
<i>Курсивный текст</i>
<u>Подчеркнутый текст</u>

<b>Жирный список:</b>
• Пункт 1
• Пункт 2

<blockquote>Обычный блок-цитата
Вторая строка блока</blockquote>

<blockquote expandable>Расширяемый блок
Скрытый контент
Много текста внутри</blockquote>

<code>код в строке</code>

🔗 <i>Тест завершен</i>"""

    try:
        # Get chat ID from command line or use a default
        chat_id = sys.argv[1] if len(sys.argv) > 1 else "YOUR_CHAT_ID"
        
        if chat_id == "YOUR_CHAT_ID":
            print("Usage: python test_formatting.py <chat_id>")
            print("Example: python test_formatting.py 123456789")
            return
            
        result = await bot.send_message(
            chat_id=int(chat_id),
            text=test_msg,
            parse_mode=ParseMode.HTML
        )
        
        print(f"✅ Message sent successfully! Message ID: {result.message_id}")
        
    except Exception as e:
        print(f"❌ Error sending message: {e}")
    
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_send())