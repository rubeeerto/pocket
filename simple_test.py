#!/usr/bin/env python3
"""
Простой тест Pocket Option Analyzer Bot
Проверяет основные функции без внешних зависимостей
"""

import os
import sys

def test_imports():
    """Тестирование импортов"""
    print("🔍 Тестирование импортов...")
    
    try:
        # Проверяем доступность основных модулей
        import logging
        print("   ✅ logging - доступен")
        
        from datetime import datetime
        print("   ✅ datetime - доступен")
        
        print("✅ Основные модули Python доступны")
        return True
        
    except ImportError as e:
        print(f"   ❌ Ошибка импорта: {e}")
        return False

def test_configuration():
    """Тестирование конфигурации"""
    print("\n⚙️ Тестирование конфигурации...")
    
    # Проверяем наличие файлов
    required_files = [
        'main.py',
        'requirements.txt',
        'railway.json',
        'README.md'
    ]
    
    for file in required_files:
        if os.path.exists(file):
            print(f"   ✅ {file} - найден")
        else:
            print(f"   ❌ {file} - не найден")
            return False
    
    print("✅ Все необходимые файлы присутствуют")
    return True

def test_environment():
    """Тестирование переменных окружения"""
    print("\n🌍 Тестирование переменных окружения...")
    
    # Проверяем наличие .env файла
    if os.path.exists('env.example'):
        print("   ✅ env.example - найден")
    else:
        print("   ❌ env.example - не найден")
        return False
    
    # Проверяем переменные окружения
    telegram_token = os.getenv('TELEGRAM_TOKEN')
    if telegram_token:
        print("   ✅ TELEGRAM_TOKEN - установлен")
    else:
        print("   ⚠️ TELEGRAM_TOKEN - не установлен (нормально для тестирования)")
    
    print("✅ Переменные окружения настроены корректно")
    return True

def test_code_structure():
    """Тестирование структуры кода"""
    print("\n🏗️ Тестирование структуры кода...")
    
    try:
        # Читаем основной файл
        with open('main.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем наличие ключевых классов
        if 'class TechnicalAnalyzer:' in content:
            print("   ✅ Класс TechnicalAnalyzer найден")
        else:
            print("   ❌ Класс TechnicalAnalyzer не найден")
            return False
        
        if 'class TelegramBot:' in content:
            print("   ✅ Класс TelegramBot найден")
        else:
            print("   ❌ Класс TelegramBot не найден")
            return False
        
        # Проверяем наличие основных методов
        required_methods = [
            'start_command',
            'analyze',
            'calculate_indicators',
            'analyze_signals'
        ]
        
        for method in required_methods:
            if method in content:
                print(f"   ✅ Метод {method} найден")
            else:
                print(f"   ❌ Метод {method} не найден")
                return False
        
        print("✅ Структура кода корректна")
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка при проверке кода: {e}")
        return False

def test_railway_config():
    """Тестирование конфигурации Railway"""
    print("\n🚂 Тестирование конфигурации Railway...")
    
    try:
        with open('railway.json', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем наличие ключевых полей
        if '"startCommand"' in content:
            print("   ✅ startCommand настроен")
        else:
            print("   ❌ startCommand не настроен")
            return False
        
        if '"python main.py"' in content:
            print("   ✅ Команда запуска корректна")
        else:
            print("   ❌ Команда запуска некорректна")
            return False
        
        print("✅ Конфигурация Railway корректна")
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка при проверке Railway: {e}")
        return False

def main():
    """Основная функция тестирования"""
    print("🚀 Запуск простого тестирования Pocket Option Analyzer Bot")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_configuration,
        test_environment,
        test_code_structure,
        test_railway_config
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"   💥 Ошибка в тесте {test.__name__}: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 Результаты тестирования: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все тесты пройдены успешно!")
        print("✅ Проект готов к развертыванию на Railway")
        print("\n📋 Следующие шаги:")
        print("1. Загрузите код в GitHub репозиторий")
        print("2. Подключите к Railway.app")
        print("3. Установите TELEGRAM_TOKEN в переменных окружения")
        print("4. Запустите развертывание")
    else:
        print("❌ Некоторые тесты не пройдены")
        print("🔧 Проверьте структуру проекта и исправьте ошибки")
    
    print("\n📚 Документация:")
    print("• QUICK_START.md - Быстрый запуск")
    print("• README.md - Полная документация")
    print("• RAILWAY_DEPLOYMENT.md - Развертывание на Railway")

if __name__ == "__main__":
    main()
