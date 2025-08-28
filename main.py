import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

import pandas as pd
import numpy as np
import ccxt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ConversationHandler, MessageHandler, filters, ContextTypes
)
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
TRADE_TYPE, SYMBOL, TIMEFRAME = range(3)

# Конфигурация
TELEGRAM_TOKEN = "8441180312:AAHWDQ9esuAAj3E121AP1bzrlObShgYuxpk"

# Настройки индикаторов
INDICATOR_CONFIG = {
    'sma_period': 50,
    'ema_period': 21,
    'rsi_period': 14,
    'bb_period': 20,
    'bb_std': 2,
    'macd_fast': 12,
    'macd_slow': 26,
    'macd_signal': 9,
    'stoch_period': 14,
    'williams_r_period': 14,
    'cci_period': 20,
    'adx_period': 14,
    'atr_period': 14,
    'obv_period': 20
}

# Пороги для принятия решений
SIGNAL_THRESHOLDS = {
    'strong_bull': 8,
    'weak_bull': 4,
    'weak_bear': -4,
    'strong_bear': -8
}

class TechnicalAnalyzer:
    """Класс для технического анализа"""
    
    def __init__(self):
        self.exchange = ccxt.binance({
            'apiKey': '',
            'secret': '',
            'sandbox': False,
            'enableRateLimit': True
        })
    
    def get_ohlcv_data(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        """Получение OHLCV данных"""
        try:
            # Преобразуем символ для совместимости с Binance
            formatted_symbol = self._format_symbol(symbol)
            logger.info(f"Запрос данных для {formatted_symbol} на {timeframe}")
            
            # Получаем данные с таймаутом
            ohlcv = self.exchange.fetch_ohlcv(formatted_symbol, timeframe, limit=limit)
            
            if not ohlcv or len(ohlcv) == 0:
                raise Exception(f"Нет данных для {formatted_symbol} на {timeframe}")
            
            # Создаем DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            logger.info(f"Получено {len(df)} свечей для {formatted_symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Ошибка при получении данных для {symbol}: {e}")
            raise Exception(f"Не удалось получить данные для {symbol}: {str(e)}")
    
    def _format_symbol(self, symbol: str) -> str:
        """Форматирование символа для API"""
        # Нормализуем символ - убираем все разделители и приводим к верхнему регистру
        normalized = symbol.upper().replace('/', '').replace('\\', '').replace('|', '').replace(' ', '')
        
        # Прямой маппинг для всех валютных пар
        # Все кросс-пары конвертируем в USDT пары
        symbol_mapping = {
            'EURUSD': 'EURUSDT',
            'GBPUSD': 'GBPUSDT',
            'USDJPY': 'USDJPY',
            'AUDUSD': 'AUDUSDT',
            'NZDUSD': 'NZDUSDT',
            'USDCAD': 'USDCUSDT',
            'USDCHF': 'USDCHF',
            'AUDJPY': 'AUDUSDT',  # AUD/JPY → AUDUSDT
            'EURJPY': 'EURUSDT',  # EUR/JPY → EURUSDT
            'GBPJPY': 'GBPUSDT',  # GBP/JPY → GBPUSDT
            'EURGBP': 'EURUSDT',  # EUR/GBP → EURUSDT
            'AUDCAD': 'AUDUSDT',  # AUD/CAD → AUDUSDT
            'NZDJPY': 'NZDUSDT',  # NZD/JPY → NZDUSDT
            'CADJPY': 'CADUSDT',  # CAD/JPY → CADUSDT
            'CHFJPY': 'CHFUSDT',  # CHF/JPY → CHFUSDT
            'EURAUD': 'EURUSDT',  # EUR/AUD → EURUSDT
            'GBPAUD': 'GBPUSDT',  # GBP/AUD → GBPUSDT
            'AUDNZD': 'AUDUSDT',  # AUD/NZD → AUDUSDT
            'EURNZD': 'EURUSDT',  # EUR/NZD → EURUSDT
            'GBPNZD': 'GBPUSDT',  # GBP/NZD → GBPUSDT
            'GBPCHF': 'GBPUSDT',  # GBP/CHF → GBPUSDT
            'EURCHF': 'EURUSDT',  # EUR/CHF → EURUSDT
            'AUDCHF': 'AUDUSDT',  # AUD/CHF → AUDUSDT
            'CADCHF': 'CADUSDT',  # CAD/CHF → CADUSDT
            'NZDCHF': 'NZDUSDT'   # NZD/CHF → NZDUSDT
        }
        
        # Проверяем, есть ли символ в маппинге
        if normalized in symbol_mapping:
            return symbol_mapping[normalized]
        
        # Если нет в маппинге, пробуем добавить USDT
        if len(normalized) == 6:  # Например, EURJPY
            base = normalized[:3]
            quote = normalized[3:]
            if base in ['EUR', 'GBP', 'AUD', 'NZD', 'CAD', 'CHF'] and quote in ['JPY', 'CHF', 'CAD', 'AUD', 'NZD']:
                # Для кросс-пар используем USDT как промежуточную валюту
                return f"{base}USDT"
        
        # Финальная проверка для всех возможных случаев
        if normalized == 'EURJPY':
            return 'EURUSDT'
        elif normalized == 'GBPJPY':
            return 'GBPUSDT'
        elif normalized == 'AUDJPY':
            return 'AUDUSDT'
        elif normalized == 'NZDJPY':
            return 'NZDUSDT'
        elif normalized == 'CADJPY':
            return 'CADUSDT'
        elif normalized == 'CHFJPY':
            return 'CHFUSDT'
        elif normalized == 'EURGBP':
            return 'EURUSDT'
        elif normalized == 'GBPAUD':
            return 'GBPUSDT'
        elif normalized == 'EURAUD':
            return 'EURUSDT'
        elif normalized == 'AUDNZD':
            return 'AUDUSDT'
        elif normalized == 'EURNZD':
            return 'EURUSDT'
        elif normalized == 'GBPNZD':
            return 'GBPUSDT'
        elif normalized == 'GBPCHF':
            return 'GBPUSDT'
        elif normalized == 'EURCHF':
            return 'EURUSDT'
        elif normalized == 'AUDCHF':
            return 'AUDUSDT'
        elif normalized == 'CADCHF':
            return 'CADUSDT'
        elif normalized == 'NZDCHF':
            return 'NZDUSDT'
        
        return normalized
    
    def calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Расчет технических индикаторов"""
        indicators = {}
        
        # SMA и EMA
        indicators['sma'] = df['close'].rolling(window=INDICATOR_CONFIG['sma_period']).mean()
        indicators['ema'] = df['close'].ewm(span=INDICATOR_CONFIG['ema_period']).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=INDICATOR_CONFIG['rsi_period']).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=INDICATOR_CONFIG['rsi_period']).mean()
        rs = gain / loss
        indicators['rsi'] = 100 - (100 / (1 + rs))
        
        # Bollinger Bands
        bb_sma = df['close'].rolling(window=INDICATOR_CONFIG['bb_period']).mean()
        bb_std = df['close'].rolling(window=INDICATOR_CONFIG['bb_period']).std()
        indicators['bb_upper'] = bb_sma + (bb_std * INDICATOR_CONFIG['bb_std'])
        indicators['bb_lower'] = bb_sma - (bb_std * INDICATOR_CONFIG['bb_std'])
        indicators['bb_middle'] = bb_sma
        
        # MACD
        ema_fast = df['close'].ewm(span=INDICATOR_CONFIG['macd_fast']).mean()
        ema_slow = df['close'].ewm(span=INDICATOR_CONFIG['macd_slow']).mean()
        indicators['macd'] = ema_fast - ema_slow
        indicators['macd_signal'] = indicators['macd'].ewm(span=INDICATOR_CONFIG['macd_signal']).mean()
        indicators['macd_histogram'] = indicators['macd'] - indicators['macd_signal']
        
        # Stochastic RSI
        rsi = indicators['rsi']
        stoch_rsi = (rsi - rsi.rolling(window=INDICATOR_CONFIG['stoch_period']).min()) / \
                   (rsi.rolling(window=INDICATOR_CONFIG['stoch_period']).max() - 
                    rsi.rolling(window=INDICATOR_CONFIG['stoch_period']).min())
        indicators['stoch_rsi'] = stoch_rsi * 100
        
        # Williams %R
        high_max = df['high'].rolling(window=INDICATOR_CONFIG['williams_r_period']).max()
        low_min = df['low'].rolling(window=INDICATOR_CONFIG['williams_r_period']).min()
        indicators['williams_r'] = -100 * (high_max - df['close']) / (high_max - low_min)
        
        # CCI (Commodity Channel Index)
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        sma_tp = typical_price.rolling(window=INDICATOR_CONFIG['cci_period']).mean()
        mad = typical_price.rolling(window=INDICATOR_CONFIG['cci_period']).apply(lambda x: np.mean(np.abs(x - x.mean())))
        indicators['cci'] = (typical_price - sma_tp) / (0.015 * mad)
        
        # ADX (Average Directional Index)
        high_diff = df['high'].diff()
        low_diff = df['low'].diff()
        
        plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
        minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), -low_diff, 0)
        
        tr = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                np.abs(df['high'] - df['close'].shift(1)),
                np.abs(df['low'] - df['close'].shift(1))
            )
        )
        
        plus_di = 100 * pd.Series(plus_dm).rolling(window=INDICATOR_CONFIG['adx_period']).mean() / \
                  pd.Series(tr).rolling(window=INDICATOR_CONFIG['adx_period']).mean()
        minus_di = 100 * pd.Series(minus_dm).rolling(window=INDICATOR_CONFIG['adx_period']).mean() / \
                   pd.Series(tr).rolling(window=INDICATOR_CONFIG['adx_period']).mean()
        
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        indicators['adx'] = pd.Series(dx).rolling(window=INDICATOR_CONFIG['adx_period']).mean()
        indicators['plus_di'] = plus_di
        indicators['minus_di'] = minus_di
        
        # ATR (Average True Range)
        tr = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                np.abs(df['high'] - df['close'].shift(1)),
                np.abs(df['low'] - df['close'].shift(1))
            )
        )
        indicators['atr'] = pd.Series(tr).rolling(window=INDICATOR_CONFIG['atr_period']).mean()
        
        # OBV (On Balance Volume)
        obv = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        indicators['obv'] = obv.rolling(window=INDICATOR_CONFIG['obv_period']).mean()
        
        return indicators
    
    def analyze_signals(self, df: pd.DataFrame) -> Dict:
        """Анализ сигналов и принятие решения"""
        try:
            # Проверяем, что у нас достаточно данных
            if len(df) < 50:
                raise Exception("Недостаточно данных для анализа (нужно минимум 50 свечей)")
            
            # Получаем текущие значения индикаторов
            current_price = df['close'].iloc[-1]
            current_sma = indicators['sma'].iloc[-1]
            current_rsi = indicators['rsi'].iloc[-1]
            current_macd_hist = indicators['macd_histogram'].iloc[-1]
            current_bb_upper = indicators['bb_upper'].iloc[-1]
            current_bb_lower = indicators['bb_lower'].iloc[-1]
            current_stoch_rsi = indicators['stoch_rsi'].iloc[-1]
            current_williams_r = indicators['williams_r'].iloc[-1]
            current_cci = indicators['cci'].iloc[-1]
            current_adx = indicators['adx'].iloc[-1]
            current_plus_di = indicators['plus_di'].iloc[-1]
            current_minus_di = indicators['minus_di'].iloc[-1]
            current_atr = indicators['atr'].iloc[-1]
            current_obv = indicators['obv'].iloc[-1]
            
            # Проверяем, что все значения не NaN
            if pd.isna(current_price) or pd.isna(current_sma) or pd.isna(current_rsi):
                raise Exception("Получены некорректные данные индикаторов")
            
            # Система баллов
            score = 0
            signals = []
            
            # Трендовые сигналы (вес: 2)
            if current_price > current_sma:
                score += 2
                signals.append("Цена > SMA50 (+2)")
            else:
                score -= 2
                signals.append("Цена < SMA50 (-2)")
            
            # RSI сигналы (вес: 1.5)
            if 50 < current_rsi < 80:
                score += 1.5
                signals.append(f"RSI: {current_rsi:.1f} (+1.5)")
            elif 20 < current_rsi < 50:
                score -= 1.5
                signals.append(f"RSI: {current_rsi:.1f} (-1.5)")
            elif current_rsi >= 80:
                score -= 1
                signals.append(f"RSI перекуплен: {current_rsi:.1f} (-1)")
            elif current_rsi <= 20:
                score += 1
                signals.append(f"RSI перепродан: {current_rsi:.1f} (+1)")
            
            # MACD сигналы (вес: 1.5)
            if current_macd_hist > 0:
                score += 1.5
                signals.append("MACD > 0 (+1.5)")
            else:
                score -= 1.5
                signals.append("MACD < 0 (-1.5)")
            
            # Bollinger Bands сигналы (вес: 1)
            if current_price <= current_bb_lower:
                score += 1
                signals.append("Цена у нижней BB (+1)")
            elif current_price >= current_bb_upper:
                score -= 1
                signals.append("Цена у верхней BB (-1)")
            
            # Stochastic RSI сигналы (вес: 1)
            if current_stoch_rsi < 20:
                score += 1
                signals.append(f"Stoch RSI: {current_stoch_rsi:.1f} (+1)")
            elif current_stoch_rsi > 80:
                score -= 1
                signals.append(f"Stoch RSI: {current_stoch_rsi:.1f} (-1)")
            
            # Williams %R сигналы (вес: 1)
            if current_williams_r < -80:
                score += 1
                signals.append(f"Williams %R: {current_williams_r:.1f} (+1)")
            elif current_williams_r > -20:
                score -= 1
                signals.append(f"Williams %R: {current_williams_r:.1f} (-1)")
            
            # CCI сигналы (вес: 1)
            if current_cci > 100:
                score += 1
                signals.append(f"CCI: {current_cci:.1f} (+1)")
            elif current_cci < -100:
                score -= 1
                signals.append(f"CCI: {current_cci:.1f} (-1)")
            
            # ADX сигналы (вес: 1)
            if current_adx > 25:
                if current_plus_di > current_minus_di:
                    score += 1
                    signals.append(f"ADX тренд вверх: {current_adx:.1f} (+1)")
                else:
                    score -= 1
                    signals.append(f"ADX тренд вниз: {current_adx:.1f} (-1)")
            
            # ATR сигналы (вес: 0.5)
            atr_avg = indicators['atr'].rolling(window=20).mean().iloc[-1]
            if current_atr > atr_avg * 1.2:
                score += 0.5
                signals.append("Высокая волатильность (+0.5)")
            elif current_atr < atr_avg * 0.8:
                score -= 0.5
                signals.append("Низкая волатильность (-0.5)")
            
            # OBV сигналы (вес: 0.5)
            obv_avg = indicators['obv'].rolling(window=20).mean().iloc[-1]
            if current_obv > obv_avg:
                score += 0.5
                signals.append("OBV растет (+0.5)")
            else:
                score -= 0.5
                signals.append("OBV падает (-0.5)")
            
            # Определение итогового сигнала
            if score >= SIGNAL_THRESHOLDS['strong_bull']:
                signal = "ВВЕРХ 🚀"
                strength = "СИЛЬНЫЙ"
                sticker = "🟢"
            elif score >= SIGNAL_THRESHOLDS['weak_bull']:
                signal = "ВВЕРХ 📈"
                strength = "СЛАБЫЙ"
                sticker = "🟢"
            elif score <= SIGNAL_THRESHOLDS['strong_bear']:
                signal = "ВНИЗ 🐻"
                strength = "СИЛЬНЫЙ"
                sticker = "🔴"
            elif score <= SIGNAL_THRESHOLDS['weak_bear']:
                signal = "ВНИЗ 📉"
                strength = "СЛАБЫЙ"
                sticker = "🔴"
            else:
                signal = "НЕЙТРАЛЬНО ➡️"
                strength = "НЕЙТРАЛЬНЫЙ"
                sticker = "🟡"
            
            return {
                'signal': signal,
                'strength': strength,
                'score': score,
                'signals': signals,
                'current_price': current_price,
                'current_rsi': current_rsi,
                'current_macd_hist': current_macd_hist,
                'current_stoch_rsi': current_stoch_rsi,
                'current_williams_r': current_williams_r,
                'current_cci': current_cci,
                'current_adx': current_adx,
                'current_atr': current_atr,
                'current_obv': current_obv,
                'sticker': sticker
            }
            
        except Exception as e:
            logger.error(f"Ошибка при анализе сигналов: {e}")
            raise Exception(f"Ошибка анализа: {str(e)}")

class TelegramBot:
    """Основной класс Telegram бота"""
    
    def __init__(self):
        self.analyzer = TechnicalAnalyzer()
        self.application = Application.builder().token(TELEGRAM_TOKEN).build()
        self.setup_handlers()
        # Хранилище для прогнозов
        self.forecasts = {}
        # Задачи для автоматической проверки
        self.check_tasks = {}
        # Путь к папке с изображениями
        self.images_path = "images/"
    
    def setup_handlers(self):
        """Настройка обработчиков команд"""
        
        # Обработчик для отмены анализа во время выполнения (должен быть ПЕРЕД ConversationHandler)
        self.application.add_handler(CallbackQueryHandler(self.cancel_analysis_during, pattern="^cancel_analysis$"))
        
        # ConversationHandler для анализа
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start_command), CommandHandler('analyze', self.start_analysis)],
            states={
                TRADE_TYPE: [CallbackQueryHandler(self.trade_type_selected)],
                SYMBOL: [CallbackQueryHandler(self.symbol_selected), MessageHandler(filters.TEXT & ~filters.COMMAND, self.symbol_entered)],
                TIMEFRAME: [CallbackQueryHandler(self.timeframe_selected)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel_analysis)],
            per_message=False,
            per_chat=True
        )
        
        self.application.add_handler(conv_handler)
        self.application.add_handler(CommandHandler('help', self.help_command))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start - сразу предлагает выбор валюты"""
        # Клавиатура для выбора типа торговли
        keyboard = [
            [
                InlineKeyboardButton("ОТС (Бинарные опционы)", callback_data="otc"),
                InlineKeyboardButton("Обычная торговля", callback_data="regular")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📈 *Выберите тип торговли:*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return TRADE_TYPE
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
📚 *Справка*

🔍 *Анализ:*
1. /start или /analyze - Выберите тип торговли
2. Выберите валютную пару или введите вручную
3. Выберите таймфрейм

💡 *Ввод валютной пары:*
Любой формат: EUR/USD, EURUSD, eurusd, EUR USD, EUR|USD

📊 *Индикаторы:*
• SMA (50) - Тренд
• RSI (14) - Моментум  
• MACD - Тренд + моментум
• Bollinger Bands - Волатильность
• Stochastic RSI - Доп. моментум
• Williams %R - Перекупленность/перепроданность
• CCI - Тренд + моментум
• ADX - Сила тренда
• ATR - Волатильность
• OBV - Объем

🎯 *Сигналы:*
• 🟢 ВВЕРХ - Покупка
• 🔴 ВНИЗ - Продажа
• 🟡 НЕЙТРАЛЬНО - Ожидание

⏰ *Автоматическая проверка:*
Бот автоматически проверит результат через выбранное время

⚠️ Не является финансовой рекомендацией
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def start_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало процесса анализа"""
        # Клавиатура для выбора типа торговли
        keyboard = [
            [
                InlineKeyboardButton("ОТС (Бинарные опционы)", callback_data="otc"),
                InlineKeyboardButton("Обычная торговля", callback_data="regular")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📈 *Выберите тип торговли:*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return TRADE_TYPE
    
    async def trade_type_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора типа торговли"""
        query = update.callback_query
        await query.answer()
        
        trade_type = query.data
        context.user_data['trade_type'] = trade_type
        
        trade_text = "ОТС (Бинарные опционы)" if trade_type == "otc" else "Обычная торговля"
        context.user_data['trade_type_text'] = trade_text
        
        # Клавиатура для выбора валютной пары
        keyboard = [
            [
                InlineKeyboardButton("EUR/USD", callback_data="EUR/USD"),
                InlineKeyboardButton("GBP/USD", callback_data="GBP/USD")
            ],
            [
                InlineKeyboardButton("USD/JPY", callback_data="USD/JPY"),
                InlineKeyboardButton("AUD/USD", callback_data="AUD/USD")
            ],
            [
                InlineKeyboardButton("NZD/USD", callback_data="NZD/USD"),
                InlineKeyboardButton("USD/CAD", callback_data="USD/CAD")
            ],
            [
                InlineKeyboardButton("USD/CHF", callback_data="USD/CHF"),
                InlineKeyboardButton("AUD/JPY", callback_data="AUD/JPY")
            ],
            [
                InlineKeyboardButton("EUR/JPY", callback_data="EUR/JPY"),
                InlineKeyboardButton("GBP/JPY", callback_data="GBP/JPY")
            ],
            [
                InlineKeyboardButton("CAD/JPY", callback_data="CAD/JPY"),
                InlineKeyboardButton("CHF/JPY", callback_data="CHF/JPY")
            ],
            [
                InlineKeyboardButton("EUR/AUD", callback_data="EUR/AUD"),
                InlineKeyboardButton("GBP/AUD", callback_data="GBP/AUD")
            ],
            [
                InlineKeyboardButton("AUD/NZD", callback_data="AUD/NZD"),
                InlineKeyboardButton("EUR/NZD", callback_data="EUR/NZD")
            ],
            [
                InlineKeyboardButton("GBP/NZD", callback_data="GBP/NZD"),
                InlineKeyboardButton("GBP/CHF", callback_data="GBP/CHF")
            ],
            [
                InlineKeyboardButton("EUR/CHF", callback_data="EUR/CHF"),
                InlineKeyboardButton("AUD/CHF", callback_data="AUD/CHF")
            ],
            [
                InlineKeyboardButton("✏️ Ввести вручную", callback_data="manual_input")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🎯 *Выберите валютную пару:*\n\nТип: {trade_text}\n\nИли введите вручную в любом формате:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return SYMBOL
    
    async def symbol_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора символа из кнопок"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "manual_input":
            await query.edit_message_text(
                "✏️ *Введите валютную пару:*\n\n"
                "Любой формат:\n"
                "• EUR/USD\n"
                "• EURUSD\n"
                "• eurusd\n"
                "• EUR USD\n"
                "• EUR|USD\n\n"
                "Отправьте сообщение с валютной парой:",
                parse_mode='Markdown'
            )
            return SYMBOL
        
        symbol = query.data
        context.user_data['symbol'] = symbol
        
        # Клавиатура для выбора таймфрейма
        keyboard = [
            [
                InlineKeyboardButton("1m", callback_data="1m"),
                InlineKeyboardButton("2m", callback_data="2m"),
                InlineKeyboardButton("3m", callback_data="3m")
            ],
            [
                InlineKeyboardButton("4m", callback_data="4m"),
                InlineKeyboardButton("5m", callback_data="5m"),
                InlineKeyboardButton("6m", callback_data="6m")
            ],
            [
                InlineKeyboardButton("7m", callback_data="7m"),
                InlineKeyboardButton("8m", callback_data="8m"),
                InlineKeyboardButton("9m", callback_data="9m")
            ],
            [
                InlineKeyboardButton("10m", callback_data="10m"),
                InlineKeyboardButton("15m", callback_data="15m")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"⏰ *Выберите таймфрейм для {symbol}:*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return TIMEFRAME
    
    async def symbol_entered(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ввода символа вручную"""
        symbol = update.message.text.strip()
        context.user_data['symbol'] = symbol
        
        # Клавиатура для выбора таймфрейма
        keyboard = [
            [
                InlineKeyboardButton("1m", callback_data="1m"),
                InlineKeyboardButton("2m", callback_data="2m"),
                InlineKeyboardButton("3m", callback_data="3m")
            ],
            [
                InlineKeyboardButton("4m", callback_data="4m"),
                InlineKeyboardButton("5m", callback_data="5m"),
                InlineKeyboardButton("6m", callback_data="6m")
            ],
            [
                InlineKeyboardButton("7m", callback_data="7m"),
                InlineKeyboardButton("8m", callback_data="8m"),
                InlineKeyboardButton("9m", callback_data="9m")
            ],
            [
                InlineKeyboardButton("10m", callback_data="10m"),
                InlineKeyboardButton("15m", callback_data="15m")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"⏰ *Выберите таймфрейм для {symbol}:*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return TIMEFRAME
    
    async def timeframe_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора таймфрейма и выполнение анализа"""
        query = update.callback_query
        await query.answer()
        
        timeframe = query.data
        symbol = context.user_data['symbol']
        trade_type = context.user_data['trade_type_text']
        
        # Клавиатура для отмены анализа
        cancel_keyboard = [
            [InlineKeyboardButton("❌ Отменить анализ", callback_data="cancel_analysis")]
        ]
        cancel_markup = InlineKeyboardMarkup(cancel_keyboard)
        
        await query.edit_message_text(
            f"🔍 *Анализ...*\n\n"
            f"Брокер: Pocket Option\n"
            f"Тип: {trade_type}\n"
            f"Валютная пара: {symbol}\n"
            f"Таймфрейм: {timeframe}\n\n"
            f"⏳ Подождите...\n\n"
            f"⏱️ Максимальное время: 1 минута",
            reply_markup=cancel_markup,
            parse_mode='Markdown'
        )
        
        try:
            logger.info(f"Начинаем анализ {symbol} на {timeframe} для пользователя {update.effective_user.id}")
            
            # Выполняем анализ
            result = await self.perform_analysis(symbol, timeframe)
            
            logger.info(f"Анализ {symbol} завершен успешно")
            
            # Сохраняем прогноз для проверки
            forecast_id = f"{symbol}_{timeframe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.forecasts[forecast_id] = {
                'symbol': symbol,
                'timeframe': timeframe,
                'trade_type': trade_type,
                'prediction': result['signal'],
                'score': result['score'],
                'current_price': result['current_price'],
                'timestamp': datetime.now(),
                'user_id': update.effective_user.id,
                'chat_id': update.effective_chat.id,
                'message_id': query.message.message_id
            }
            
            # Формируем ответ
            response = self.format_analysis_result(symbol, timeframe, result, trade_type)
            
            # Получаем изображение для сигнала
            image_path = self.get_image_for_signal(result['signal'])
            
            if image_path and os.path.exists(image_path):
                # Отправляем с изображением
                with open(image_path, 'rb') as photo:
                    await query.edit_message_text(response, parse_mode='Markdown')
                    await self.application.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=photo,
                        caption="📊 Анализ завершен"
                    )
            else:
                # Отправляем без изображения
                await query.edit_message_text(response, parse_mode='Markdown')
            
            # Запускаем автоматическую проверку через время таймфрейма
            await self.schedule_forecast_check(forecast_id, timeframe, update.effective_user.id)
            
            logger.info(f"Результат анализа отправлен пользователю {update.effective_user.id}")
            
        except asyncio.TimeoutError:
            logger.warning(f"Таймаут при анализе {symbol} на {timeframe}")
            error_message = f"⏰ *Превышено время ожидания*\n\n"
            error_message += f"Анализ {symbol} на {timeframe} занял слишком много времени.\n\n"
            error_message += "🔄 /analyze - Попробовать снова\n"
            error_message += "📚 /help - Справка"
            await query.edit_message_text(error_message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Ошибка при анализе {symbol}: {e}")
            error_message = f"❌ *Ошибка:*\n\n{str(e)}\n\n"
            error_message += "🔄 /analyze - Попробовать снова\n"
            error_message += "📚 /help - Справка"
            await query.edit_message_text(error_message, parse_mode='Markdown')
        
        return ConversationHandler.END
    
    async def schedule_forecast_check(self, forecast_id: str, timeframe: str, user_id: int):
        """Планирование автоматической проверки прогноза"""
        # Конвертируем таймфрейм в секунды
        timeframe_seconds = self._timeframe_to_seconds(timeframe)
        
        # Создаем задачу для проверки
        task = asyncio.create_task(self.check_forecast_after_time(forecast_id, timeframe_seconds))
        self.check_tasks[forecast_id] = task
        
        logger.info(f"Запланирована проверка прогноза {forecast_id} через {timeframe}")
    
    async def check_forecast_after_time(self, forecast_id: str, delay_seconds: int):
        """Проверка прогноза через заданное время"""
        try:
            # Ждем указанное время
            await asyncio.sleep(delay_seconds)
            
            # Получаем прогноз
            forecast = self.forecasts.get(forecast_id)
            if not forecast:
                return
            
            # Проверяем результат
            result = await self.check_forecast_result(forecast)
            
            # Отправляем результат пользователю
            await self.send_forecast_result(forecast, result)
            
            # Удаляем прогноз из хранилища
            if forecast_id in self.forecasts:
                del self.forecasts[forecast_id]
            if forecast_id in self.check_tasks:
                del self.check_tasks[forecast_id]
                
        except Exception as e:
            logger.error(f"Ошибка при проверке прогноза {forecast_id}: {e}")
    
    async def check_forecast_result(self, forecast: Dict) -> Dict:
        """Проверка результата прогноза"""
        try:
            # Получаем текущие данные
            current_df = self.analyzer.get_ohlcv_data(forecast['symbol'], forecast['timeframe'], limit=1)
            current_price = current_df['close'].iloc[-1]
            
            # Цена открытия (когда был сделан прогноз)
            open_price = forecast['current_price']
            
            # Определяем результат
            if "ВВЕРХ" in forecast['prediction']:
                # Прогноз был на рост
                if current_price > open_price:
                    result = "✅ ПЛЮС"
                    points = current_price - open_price
                else:
                    result = "❌ МИНУС"
                    points = open_price - current_price
            elif "ВНИЗ" in forecast['prediction']:
                # Прогноз был на падение
                if current_price < open_price:
                    result = "✅ ПЛЮС"
                    points = open_price - current_price
                else:
                    result = "❌ МИНУС"
                    points = current_price - open_price
            else:
                result = "➡️ НЕЙТРАЛЬНО"
                points = 0
            
            return {
                'result': result,
                'open_price': open_price,
                'close_price': current_price,
                'points': points,
                'prediction_correct': "ПЛЮС" in result
            }
            
        except Exception as e:
            logger.error(f"Ошибка при проверке результата: {e}")
            return {
                'result': "❌ ОШИБКА",
                'open_price': forecast['current_price'],
                'close_price': 0,
                'points': 0,
                'prediction_correct': False
            }
    
    async def send_forecast_result(self, forecast: Dict, result: Dict):
        """Отправка результата прогноза пользователю"""
        try:
            # Формируем сообщение с результатом
            response = f"""
📊 *РЕЗУЛЬТАТ ПРОГНОЗА*

🎯 *Валютная пара:* {forecast['symbol']}
⏰ *Таймфрейм:* {forecast['timeframe']}
📈 *Тип:* {forecast['trade_type']}
🕐 *Время прогноза:* {forecast['timestamp'].strftime('%H:%M:%S')}

{'='*25}

🎯 *Прогноз был:* {forecast['prediction']}
📊 *Результат:* {result['result']}

{'='*25}

💰 *Детали:*
• Точка открытия: {result['open_price']:.5f}
• Точка закрытия: {result['close_price']:.5f}
• Пункты: {result['points']:.5f}

{'='*25}

⏰ *Время прошло:* {forecast['timeframe']}
🔄 /analyze - Новый анализ
            """
            
            # Получаем изображение для результата
            image_path = self.get_image_for_result(result['result'])
            
            if image_path and os.path.exists(image_path):
                # Отправляем с изображением
                with open(image_path, 'rb') as photo:
                    await self.application.bot.send_photo(
                        chat_id=forecast['chat_id'],
                        photo=photo,
                        caption=response,
                        parse_mode='Markdown'
                    )
            else:
                # Отправляем без изображения
                await self.application.bot.send_message(
                    chat_id=forecast['chat_id'],
                    text=response,
                    parse_mode='Markdown'
                )
            
        except Exception as e:
            logger.error(f"Ошибка при отправке результата: {e}")
    
    def _timeframe_to_seconds(self, timeframe: str) -> int:
        """Конвертация таймфрейма в секунды"""
        timeframe_map = {
            '1m': 60,
            '2m': 120,
            '3m': 180,
            '4m': 240,
            '5m': 300,
            '6m': 360,
            '7m': 420,
            '8m': 480,
            '9m': 540,
            '10m': 600,
            '15m': 900
        }
        return timeframe_map.get(timeframe, 60)
    
    def get_image_for_signal(self, signal: str) -> str:
        """Получение пути к изображению для сигнала"""
        try:
            if "ВВЕРХ" in signal:
                if "СИЛЬНЫЙ" in signal:
                    return f"{self.images_path}strong_bull.png"
                else:
                    return f"{self.images_path}weak_bull.png"
            elif "ВНИЗ" in signal:
                if "СИЛЬНЫЙ" in signal:
                    return f"{self.images_path}strong_bear.png"
                else:
                    return f"{self.images_path}weak_bear.png"
            else:
                return f"{self.images_path}neutral.png"
        except:
            return None
    
    def get_image_for_result(self, result: str) -> str:
        """Получение пути к изображению для результата"""
        try:
            if "ПЛЮС" in result:
                return f"{self.images_path}profit.png"
            elif "МИНУС" in result:
                return f"{self.images_path}loss.png"
            else:
                return f"{self.images_path}neutral.png"
        except:
            return None
    
    async def perform_analysis(self, symbol: str, timeframe: str) -> Dict:
        """Выполнение технического анализа"""
        try:
            # Получаем данные с таймаутом
            df = await asyncio.wait_for(
                asyncio.to_thread(self.analyzer.get_ohlcv_data, symbol, timeframe),
                timeout=30.0  # 30 секунд таймаут
            )
            
            # Рассчитываем индикаторы с таймаутом
            indicators = await asyncio.wait_for(
                asyncio.to_thread(self.analyzer.calculate_indicators, df),
                timeout=15.0  # 15 секунд таймаут
            )
            
            # Анализируем сигналы с таймаутом
            analysis_result = await asyncio.wait_for(
                asyncio.to_thread(self.analyzer.analyze_signals, df, indicators),
                timeout=10.0  # 10 секунд таймаут
            )
            
            return analysis_result
            
        except asyncio.TimeoutError:
            logger.error(f"Таймаут при анализе {symbol} на {timeframe}")
            raise Exception("Превышено время ожидания при анализе. Попробуйте позже.")
        except Exception as e:
            logger.error(f"Ошибка при анализе {symbol}: {e}")
            raise
    
    def format_analysis_result(self, symbol: str, timeframe: str, result: Dict, trade_type: str) -> str:
        """Форматирование результата анализа"""
        response = f"""
📊 *РЕЗУЛЬТАТ АНАЛИЗА*

🎯 *Валютная пара:* {symbol}
⏰ *Таймфрейм:* {timeframe}
📈 *Тип:* {trade_type}
🕐 *Время:* {datetime.now().strftime('%H:%M:%S')}

{'='*25}

{result['sticker']} *ПРОГНОЗ:* {result['signal']}
💪 *Сила:* {result['strength']}
📊 *Балл:* {result['score']}

{'='*25}

📋 *Обоснование:*
"""
        
        for signal in result['signals']:
            response += f"• {signal}\n"
        
        response += f"""

📊 *Значения:*
• Цена: {result['current_price']:.5f}
• RSI: {result['current_rsi']:.1f}
• MACD: {result['current_macd_hist']:.6f}
• Williams %R: {result['current_williams_r']:.1f}
• CCI: {result['current_cci']:.1f}
• ADX: {result['current_adx']:.1f}
• ATR: {result['current_atr']:.5f}

{'='*25}

⏰ *Автоматическая проверка через {timeframe}*

⚠️ *Предупреждение:*
Только для информационных целей
Не является финансовой рекомендацией
Торговля связана с рисками

🔄 /analyze - Новый анализ
        """
        
        return response
    
    async def cancel_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена анализа"""
        await update.message.reply_text(
            "❌ Анализ отменен\n\n/analyze - Новый анализ",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    async def cancel_analysis_during(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена анализа во время выполнения"""
        query = update.callback_query
        await query.answer()
        
        try:
            logger.info(f"Попытка отмены анализа пользователем {update.effective_user.id}")
            
            # Очищаем состояние пользователя
            if hasattr(context, 'user_data'):
                context.user_data.clear()
                logger.info("Состояние пользователя очищено")
            
            # Убираем клавиатуру
            await query.edit_message_text(
                "❌ *Анализ отменен пользователем*\n\n"
                "🔄 /analyze - Новый анализ\n"
                "📚 /help - Справка",
                parse_mode='Markdown',
                reply_markup=None
            )
            
            logger.info(f"Анализ успешно отменен пользователем {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"Ошибка при отмене анализа: {e}")
            try:
                await query.edit_message_text(
                    "❌ *Ошибка при отмене*\n\n"
                    "🔄 /analyze - Попробовать снова",
                    parse_mode='Markdown',
                    reply_markup=None
                )
            except:
                # Если не можем отредактировать, отправляем новое сообщение
                await self.application.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ *Ошибка при отмене*\n\n🔄 /analyze - Попробовать снова",
                    parse_mode='Markdown'
                )
        
        return ConversationHandler.END
    
    def run(self):
        """Запуск бота"""
        logger.info("Бот запущен")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    bot = TelegramBot()
    bot.run()
