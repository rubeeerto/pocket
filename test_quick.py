#!/usr/bin/env python3
"""
Быстрый тест бота для проверки работы
"""

import asyncio
import logging
from main import TelegramBot

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_bot():
    """Тестирование бота"""
    try:
        print("🚀 Запуск теста бота...")
        
        # Создаем экземпляр бота
        bot = TelegramBot()
        print("✅ Бот создан успешно")
        
        # Тестируем форматирование символов
        analyzer = bot.analyzer
        test_symbols = ['EUR/JPY', 'GBP/USD', 'AUDJPY', 'eur jpy']
        
        print("\n🔍 Тестирование форматирования символов:")
        for symbol in test_symbols:
            try:
                formatted = analyzer._format_symbol(symbol)
                print(f"  {symbol} → {formatted}")
            except Exception as e:
                print(f"  ❌ {symbol}: {e}")
        
        print("\n✅ Тест завершен успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_bot())
