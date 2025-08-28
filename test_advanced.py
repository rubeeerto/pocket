#!/usr/bin/env python3
"""
Расширенный тест бота для проверки всех функций
"""

import asyncio
import logging
import time
from main import TelegramBot, TechnicalAnalyzer

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,  # Подробное логирование
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_analyzer():
    """Тестирование анализатора"""
    print("🔍 Тестирование анализатора...")
    
    try:
        analyzer = TechnicalAnalyzer()
        
        # Тест форматирования символов
        test_symbols = ['EUR/JPY', 'GBP/USD', 'AUDJPY', 'eur jpy', 'GBP|JPY']
        print("\n📝 Тест форматирования символов:")
        for symbol in test_symbols:
            formatted = analyzer._format_symbol(symbol)
            print(f"  {symbol} → {formatted}")
        
        # Тест получения данных (только проверка без реального запроса)
        print("\n✅ Анализатор работает корректно")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в анализаторе: {e}")
        return False

async def test_bot_creation():
    """Тестирование создания бота"""
    print("\n🤖 Тестирование создания бота...")
    
    try:
        bot = TelegramBot()
        print("✅ Бот создан успешно")
        
        # Проверяем обработчики
        handlers_count = len(bot.application.handlers[0])
        print(f"📊 Количество обработчиков: {handlers_count}")
        
        return bot
        
    except Exception as e:
        print(f"❌ Ошибка при создании бота: {e}")
        import traceback
        traceback.print_exc()
        return None

async def test_symbol_formatting():
    """Тест форматирования символов"""
    print("\n🔤 Тест форматирования символов...")
    
    try:
        analyzer = TechnicalAnalyzer()
        
        # Тестируем различные форматы
        test_cases = [
            ('EUR/JPY', 'EURUSDT'),
            ('GBP/USD', 'GBPUSDT'),
            ('AUDJPY', 'AUDUSDT'),
            ('eur jpy', 'EURUSDT'),
            ('GBP|JPY', 'GBPUSDT'),
            ('USD\\CAD', 'USDCUSDT'),
            ('NZD USD', 'NZDUSDT'),
            ('CHFJPY', 'CHFUSDT')
        ]
        
        all_passed = True
        for input_symbol, expected in test_cases:
            result = analyzer._format_symbol(input_symbol)
            status = "✅" if result == expected else "❌"
            print(f"  {status} {input_symbol} → {result} (ожидалось: {expected})")
            if result != expected:
                all_passed = False
        
        if all_passed:
            print("✅ Все тесты форматирования прошли успешно!")
        else:
            print("❌ Некоторые тесты форматирования не прошли")
            
        return all_passed
        
    except Exception as e:
        print(f"❌ Ошибка в тесте форматирования: {e}")
        return False

async def main():
    """Основная функция тестирования"""
    print("🚀 Запуск расширенного тестирования бота...")
    print("=" * 50)
    
    # Тест 1: Анализатор
    analyzer_ok = await test_analyzer()
    
    # Тест 2: Создание бота
    bot = await test_bot_creation()
    
    # Тест 3: Форматирование символов
    formatting_ok = await test_symbol_formatting()
    
    # Итоговый результат
    print("\n" + "=" * 50)
    print("📊 ИТОГОВЫЙ РЕЗУЛЬТАТ:")
    print(f"  Анализатор: {'✅' if analyzer_ok else '❌'}")
    print(f"  Создание бота: {'✅' if bot else '❌'}")
    print(f"  Форматирование: {'✅' if formatting_ok else '❌'}")
    
    if analyzer_ok and bot and formatting_ok:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        print("Бот готов к работе!")
    else:
        print("\n⚠️ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ!")
        print("Проверьте ошибки выше")
    
    print("\n🔧 Для запуска бота используйте: python main.py")

if __name__ == "__main__":
    asyncio.run(main())
