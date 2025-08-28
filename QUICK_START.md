# 🚀 Быстрый запуск Pocket Option Analyzer Bot

## ⚡ Минимальная настройка за 5 минут

### 1. Получите токен бота
- Напишите [@BotFather](https://t.me/BotFather) в Telegram
- Команда: `/newbot`
- Сохраните токен

### 2. Разверните на Railway
1. Загрузите код в GitHub
2. Подключите к [Railway.app](https://railway.app)
3. Добавьте переменную: `TELEGRAM_TOKEN=ваш_токен`
4. Готово! 🎉

### 3. Протестируйте
- Найдите бота в Telegram
- Отправьте `/start`
- Отправьте `/analyze`

## 📁 Структура проекта

```
pocket-option-analyzer-bot/
├── main.py              # Основной код бота
├── requirements.txt     # Зависимости Python
├── railway.json        # Конфигурация Railway
├── run.py              # Production запуск
├── test_bot.py         # Тестирование функций
├── README.md           # Полная документация
├── RAILWAY_DEPLOYMENT.md # Инструкция по развертыванию
├── env.example         # Пример переменных окружения
├── .gitignore          # Исключения Git
└── LICENSE             # Лицензия MIT
```

## 🔧 Основные команды

- `/start` - Приветствие
- `/analyze` - Анализ актива
- `/help` - Справка
- `/cancel` - Отмена анализа

## 📊 Поддерживаемые активы

- **Валюты:** EUR/USD, GBP/USD, USD/JPY
- **Крипто:** BTC/USDT, ETH/USDT
- **Таймфреймы:** 1m, 5m, 15m, 30m, 1h, 4h, 1d

## ⚠️ Важно

- Анализ только для информационных целей
- Не является финансовой рекомендацией
- Торговля связана с рисками

---

**Нужна помощь?** См. [README.md](README.md) или [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md)
