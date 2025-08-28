#!/usr/bin/env python3
"""
Production запуск Pocket Option Analyzer Bot
Включает дополнительные настройки для production окружения
"""

import os
import sys
import logging
from pathlib import Path

# Добавляем текущую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

# Настройка логирования для production
def setup_logging():
    """Настройка логирования для production"""
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Создаем директорию для логов
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # Настройка форматирования
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Настройка логирования в файл
    file_handler = logging.FileHandler(log_dir / 'bot.log', encoding='utf-8')
    file_handler.setLevel(getattr(logging, log_level))
    file_handler.setFormatter(logging.Formatter(log_format, date_format))
    
    # Настройка логирования в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Настройка логгера для основного приложения
    app_logger = logging.getLogger('pocket_option_bot')
    app_logger.setLevel(getattr(logging, log_level))
    
    return app_logger

def check_environment():
    """Проверка окружения"""
    logger = logging.getLogger(__name__)
    
    # Проверяем обязательные переменные
    required_vars = ['TELEGRAM_TOKEN']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
        return False
    
    # Проверяем опциональные переменные
    optional_vars = {
        'SMA_PERIOD': '50',
        'EMA_PERIOD': '21',
        'RSI_PERIOD': '14',
        'BB_PERIOD': '20',
        'BB_STD': '2',
        'MACD_FAST': '12',
        'MACD_SLOW': '26',
        'MACD_SIGNAL': '9',
        'STOCH_PERIOD': '14'
    }
    
    for var, default_value in optional_vars.items():
        if not os.getenv(var):
            logger.info(f"Переменная {var} не установлена, используется значение по умолчанию: {default_value}")
    
    return True

def main():
    """Основная функция запуска"""
    # Настройка логирования
    logger = setup_logging()
    
    logger.info("🚀 Запуск Pocket Option Analyzer Bot в production режиме")
    
    # Проверка окружения
    if not check_environment():
        logger.error("❌ Ошибка конфигурации окружения")
        sys.exit(1)
    
    try:
        # Импортируем и запускаем бота
        from main import TelegramBot
        
        logger.info("✅ Все проверки пройдены успешно")
        logger.info("🤖 Инициализация Telegram бота...")
        
        bot = TelegramBot()
        logger.info("🚀 Бот запущен и готов к работе")
        
        # Запускаем бота
        bot.run()
        
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта модулей: {e}")
        logger.error("Проверьте установку зависимостей: pip install -r requirements.txt")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"💥 Критическая ошибка при запуске: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
