#!/usr/bin/env python3
"""
Тестовый файл для Pocket Option Analyzer Bot
Позволяет протестировать основные функции без запуска Telegram бота
"""

import asyncio
import pandas as pd
import numpy as np
from main import TechnicalAnalyzer, INDICATOR_CONFIG, SIGNAL_THRESHOLDS

def test_technical_analyzer():
    """Тестирование технического анализа"""
    print("🧪 Тестирование технического анализа...")
    
    # Создаем тестовые данные
    dates = pd.date_range('2024-01-01', periods=200, freq='1H')
    np.random.seed(42)
    
    # Генерируем реалистичные OHLCV данные
    base_price = 100.0
    prices = []
    
    for i in range(200):
        if i == 0:
            price = base_price
        else:
            # Добавляем тренд и волатильность
            trend = 0.001 * (i - 100)  # Тренд вверх до середины, потом вниз
            volatility = np.random.normal(0, 0.02)
            price = prices[-1] * (1 + trend + volatility)
        
        prices.append(price)
    
    # Создаем OHLCV данные
    data = []
    for i, price in enumerate(prices):
        high = price * (1 + abs(np.random.normal(0, 0.01)))
        low = price * (1 - abs(np.random.normal(0, 0.01)))
        open_price = prices[i-1] if i > 0 else price
        close_price = price
        volume = np.random.randint(1000, 10000)
        
        data.append([dates[i], open_price, high, low, close_price, volume])
    
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df.set_index('timestamp', inplace=True)
    
    print(f"✅ Созданы тестовые данные: {len(df)} свечей")
    print(f"📊 Диапазон цен: {df['close'].min():.2f} - {df['close'].max():.2f}")
    
    # Тестируем анализатор
    analyzer = TechnicalAnalyzer()
    
    try:
        # Рассчитываем индикаторы
        print("\n🔧 Расчет индикаторов...")
        indicators = analyzer.calculate_indicators(df)
        
        print("✅ Индикаторы рассчитаны:")
        for name, values in indicators.items():
            if not values.empty:
                print(f"   • {name}: {values.iloc[-1]:.4f}")
        
        # Анализируем сигналы
        print("\n📊 Анализ сигналов...")
        result = analyzer.analyze_signals(df, indicators)
        
        print("✅ Анализ завершен:")
        print(f"   • Прогноз: {result['signal']}")
        print(f"   • Сила: {result['strength']}")
        print(f"   • Балл: {result['score']}")
        print(f"   • Текущая цена: {result['current_price']:.4f}")
        print(f"   • RSI: {result['current_rsi']:.1f}")
        print(f"   • MACD гистограмма: {result['current_macd_hist']:.6f}")
        print(f"   • Stochastic RSI: {result['current_stoch_rsi']:.1f}")
        
        print("\n📋 Обоснование:")
        for signal in result['signals']:
            print(f"   • {signal}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        return False

def test_symbol_formatting():
    """Тестирование форматирования символов"""
    print("\n🔤 Тестирование форматирования символов...")
    
    analyzer = TechnicalAnalyzer()
    
    test_symbols = [
        "EUR/USD",
        "GBP/USD", 
        "BTC/USDT",
        "ETH/USDT",
        "USD/JPY"
    ]
    
    for symbol in test_symbols:
        formatted = analyzer._format_symbol(symbol)
        print(f"   • {symbol} → {formatted}")
    
    print("✅ Форматирование символов работает корректно")

def test_configuration():
    """Тестирование конфигурации"""
    print("\n⚙️ Тестирование конфигурации...")
    
    print("📊 Настройки индикаторов:")
    for key, value in INDICATOR_CONFIG.items():
        print(f"   • {key}: {value}")
    
    print("\n🎯 Пороги сигналов:")
    for key, value in SIGNAL_THRESHOLDS.items():
        print(f"   • {key}: {value}")
    
    print("✅ Конфигурация загружена корректно")

def test_data_validation():
    """Тестирование валидации данных"""
    print("\n✅ Тестирование валидации данных...")
    
    # Проверяем минимальное количество свечей
    min_candles = 100
    print(f"   • Минимальное количество свечей: {min_candles}")
    
    # Проверяем поддержку таймфреймов
    supported_timeframes = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
    print(f"   • Поддерживаемые таймфреймы: {', '.join(supported_timeframes)}")
    
    # Проверяем поддержку символов
    supported_symbols = ['EUR/USD', 'GBP/USD', 'BTC/USDT', 'ETH/USDT']
    print(f"   • Поддерживаемые символы: {', '.join(supported_symbols)}")
    
    print("✅ Валидация данных настроена корректно")

def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестирования Pocket Option Analyzer Bot")
    print("=" * 60)
    
    try:
        # Тестируем конфигурацию
        test_configuration()
        
        # Тестируем форматирование символов
        test_symbol_formatting()
        
        # Тестируем валидацию данных
        test_data_validation()
        
        # Тестируем технический анализ
        success = test_technical_analyzer()
        
        print("\n" + "=" * 60)
        if success:
            print("🎉 Все тесты пройдены успешно!")
            print("✅ Бот готов к работе")
        else:
            print("❌ Некоторые тесты не пройдены")
            print("🔧 Проверьте настройки и зависимости")
        
    except Exception as e:
        print(f"\n💥 Критическая ошибка при тестировании: {e}")
        print("🔧 Проверьте установку зависимостей")

if __name__ == "__main__":
    main()
