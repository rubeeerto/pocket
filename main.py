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
import yfinance as yf

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
        """Получение OHLCV данных с поддержкой Binance и Yahoo Finance"""
        try:
            # Преобразуем символ для совместимости с Binance
            formatted_symbol = self._format_symbol(symbol)
            logger.info(f"Запрос данных для {formatted_symbol} на {timeframe}")
            # Проверяем, поддерживается ли пара на Binance
            if self._is_binance_symbol(formatted_symbol):
                ohlcv = self.exchange.fetch_ohlcv(formatted_symbol, timeframe, limit=limit)
                if not ohlcv or len(ohlcv) == 0:
                    raise Exception(f"Нет данных для {formatted_symbol} на {timeframe}")
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                logger.info(f"Получено {len(df)} свечей для {formatted_symbol} (Binance)")
                return df
            # Если не Binance — пробуем через Yahoo Finance
            yf_symbol = self._format_yahoo_symbol(symbol)
            interval = self._yahoo_timeframe_to_interval(timeframe)
            period = self._yahoo_period_for_interval(interval)
            data = yf.download(yf_symbol, period=period, interval=interval, progress=False)
            # Если пусто — пробуем реверсную пару (например, USDUAH вместо UAHUSD)
            if data.empty:
                # Пытаемся поменять местами базу и котировку
                normalized = symbol.upper().replace('/', '').replace(' ', '')
                if len(normalized) >= 6:
                    base = normalized[:3]
                    quote = normalized[3:6]
                    reversed_symbol = f"{quote}{base}=X"
                    rev_data = yf.download(reversed_symbol, period=period, interval=interval, progress=False)
                    if not rev_data.empty:
                        # Переименуем и инвертируем OHLC
                        rev = rev_data.rename(columns={'Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'})
                        # Привести к float
                        for c in ['open','high','low','close']:
                            rev[c] = pd.to_numeric(rev[c], errors='coerce')
                        inv = pd.DataFrame(index=rev.index)
                        inv['open'] = 1.0 / rev['open']
                        inv['high'] = 1.0 / rev['low']
                        inv['low'] = 1.0 / rev['high']
                        inv['close'] = 1.0 / rev['close']
                        inv['volume'] = rev.get('volume', 0)
                        data = inv
            # Синтетический кросс через USD, если прямой и обратный отсутствуют
            if data.empty:
                normalized = symbol.upper().replace('/', '').replace(' ', '')
                if len(normalized) >= 6:
                    base = normalized[:3]
                    quote = normalized[3:6]
                    def _yf_load_pair(ticker: str) -> pd.DataFrame:
                        dfp = yf.download(ticker, period=period, interval=interval, progress=False)
                        if dfp.empty:
                            return dfp
                        if isinstance(dfp.columns, pd.MultiIndex):
                            dfp.columns = [col[0] for col in dfp.columns]
                        dfp = dfp.rename(columns={'Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'})
                        for c in ['open','high','low','close']:
                            if c in dfp:
                                dfp[c] = pd.to_numeric(dfp[c], errors='coerce')
                        return dfp[['open','high','low','close','volume']].dropna()
                    def _usd_per(code: str) -> pd.DataFrame:
                        # Пытаемся получить USD/CODE, иначе CODE/USD и инвертируем
                        direct = _yf_load_pair(f"USD{code}=X")
                        if not direct.empty:
                            return direct
                        inverse = _yf_load_pair(f"{code}USD=X")
                        if not inverse.empty:
                            inv = pd.DataFrame(index=inverse.index)
                            inv['open'] = 1.0 / inverse['open']
                            inv['high'] = 1.0 / inverse['low']
                            inv['low'] = 1.0 / inverse['high']
                            inv['close'] = 1.0 / inverse['close']
                            inv['volume'] = inverse.get('volume', 0)
                            return inv
                        return pd.DataFrame()
                    usd_per_base = _usd_per(base)
                    usd_per_quote = _usd_per(quote) if quote != 'CNH' else (_usd_per('CNY') if _usd_per('CNH').empty else _usd_per('CNH'))
                    if not usd_per_base.empty and not usd_per_quote.empty:
                        idx = usd_per_base.index.intersection(usd_per_quote.index)
                        if len(idx) > 0:
                            ub = usd_per_base.loc[idx]
                            uq = usd_per_quote.loc[idx]
                            syn = pd.DataFrame(index=idx)
                            # BASE/QUOTE = (USD/QUOTE) / (USD/BASE)
                            syn['open'] = uq['open'] / ub['open']
                            syn['high'] = uq['high'] / ub['high']
                            syn['low'] = uq['low'] / ub['low']
                            syn['close'] = uq['close'] / ub['close']
                            syn['volume'] = 0
                            data = syn.dropna()
            if data.empty:
                raise Exception(f"Yahoo Finance не вернул данные для {yf_symbol}")
            # Исправление для MultiIndex (yfinance для форекс)
            if isinstance(data.columns, pd.MultiIndex):
                # Берём только значения для тикера (обычно первый уровень)
                data.columns = [col[0].lower() for col in data.columns]
            # Исправление: если столбцы имеют shape (N, 1), преобразуем их в Series
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in data.columns and hasattr(data[col], 'values') and len(data[col].values.shape) > 1:
                    data[col] = data[col].values.reshape(-1)
            data = data.rename(columns={
                'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'
            })
            # Очистка NaN и проверка достаточности данных
            data = data[['open','high','low','close','volume']].dropna()
            logger.info(f"Получено {len(data)} свечей для {yf_symbol} (Yahoo Finance)")
            return data.tail(limit)
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
    
    def _is_binance_symbol(self, formatted_symbol: str) -> bool:
        try:
            markets = self.exchange.load_markets()
            return formatted_symbol in markets
        except Exception:
            return False

    def _format_yahoo_symbol(self, symbol: str) -> str:
        # Преобразует EUR/USD → EURUSD=X, USDJPY → JPY=X, BTC/USDT → BTC-USD и т.д.
        normalized = symbol.upper().replace('/', '').replace(' ', '')
        if normalized.endswith('USD') and len(normalized) == 6:
            return normalized[:3] + normalized[3:] + '=X'
        if normalized.endswith('JPY') and len(normalized) == 6:
            return normalized[:3] + normalized[3:] + '=X'
        if 'BTC' in normalized or 'ETH' in normalized:
            return normalized.replace('USDT', '-USD')
        return normalized + '=X'

    def _yahoo_timeframe_to_interval(self, timeframe: str) -> str:
        # Упрощённый маппинг интервалов Yahoo: поддерживает 1m, 2m, 5m, 15m, 30m, 60m/1h, 90m, 1d
        mapping = {
            '1m': '1m',
            '2m': '2m',
            '3m': '5m',
            '4m': '5m',
            '5m': '5m',
            '6m': '5m',
            '7m': '15m',
            '8m': '15m',
            '9m': '15m',
            '10m': '15m',
            '15m': '15m',
            '30m': '30m',
            '1h': '1h',
            '4h': '1h',
            '1d': '1d'
        }
        return mapping.get(timeframe, '1h')

    def _yahoo_period_for_interval(self, interval: str) -> str:
        # Ограничения yfinance по максимуму периода для мелких интервалов
        if interval == '1m':
            return '7d'
        if interval in ['2m', '5m', '15m', '30m', '1h']:
            return '60d'
        return '1y'
    
    def calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Расчет технических индикаторов"""
        indicators = {}
        
        # SMA и EMA
        indicators['sma'] = df['close'].rolling(window=INDICATOR_CONFIG['sma_period']).mean()
        indicators['ema'] = df['close'].ewm(span=INDICATOR_CONFIG['ema_period']).mean()
        # Дополнительные долгосрочные средние как прокси старшего ТФ
        indicators['sma200'] = df['close'].rolling(window=200, min_periods=50).mean()
        indicators['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        
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
        
        # ATR (Average True Range) и волатильность в % от цены
        tr2 = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                np.abs(df['high'] - df['close'].shift(1)),
                np.abs(df['low'] - df['close'].shift(1))
            )
        )
        indicators['atr'] = pd.Series(tr2).rolling(window=INDICATOR_CONFIG['atr_period']).mean()
        indicators['atr_pct'] = (indicators['atr'] / df['close']) * 100
        
        # OBV (On Balance Volume)
        obv = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        indicators['obv'] = obv.rolling(window=INDICATOR_CONFIG['obv_period']).mean()
        
        # Уже добавленные ранее индикаторы: Parabolic SAR, Momentum, ROC, MFI, Ichimoku — оставляем как есть
        # (логика их вычисления находится выше по коду в этом методе)
        
        # Свечные паттерны (простые)
        try:
            body = (df['close'] - df['open']).abs()
            range_ = (df['high'] - df['low']).replace(0, np.nan)
            upper_wick = (df[['open','close']].max(axis=1) - df['high']).abs()
            lower_wick = (df['low'] - df[['open','close']].min(axis=1)).abs()
            indicators['is_doji'] = (body / range_) < 0.1
            # Пин-бар: длинный хвост снизу или сверху
            indicators['is_bull_pin'] = (lower_wick > body * 2) & (df['close'] > df['open'])
            indicators['is_bear_pin'] = (upper_wick > body * 2) & (df['close'] < df['open'])
            # Поглощение
            prev_open = df['open'].shift(1)
            prev_close = df['close'].shift(1)
            bull_engulf = (df['close'] > df['open']) & (prev_close < prev_open) & (df['close'] >= prev_open) & (df['open'] <= prev_close)
            bear_engulf = (df['close'] < df['open']) & (prev_close > prev_open) & (df['close'] <= prev_open) & (df['open'] >= prev_close)
            indicators['bull_engulf'] = bull_engulf
            indicators['bear_engulf'] = bear_engulf
        except Exception:
            indicators['is_doji'] = pd.Series(False, index=df.index)
            indicators['is_bull_pin'] = pd.Series(False, index=df.index)
            indicators['is_bear_pin'] = pd.Series(False, index=df.index)
            indicators['bull_engulf'] = pd.Series(False, index=df.index)
            indicators['bear_engulf'] = pd.Series(False, index=df.index)
        
        return indicators
    
    def analyze_signals(self, df: pd.DataFrame, indicators: Dict, trade_type: Optional[str] = None) -> Dict:
        """Анализ сигналов и принятие решения"""
        try:
            # Проверяем, что у нас достаточно данных
            if len(df) < 50:
                raise Exception("Недостаточно данных для анализа (нужно минимум 50 свечей)")
            
            # Сформировать таблицу ключевых индикаторов и выбрать последнюю валидную строку
            key_df = pd.DataFrame({
                'price': df['close'],
                'sma': indicators['sma'],
                'rsi': indicators['rsi'],
                'macd_histogram': indicators['macd_histogram'],
                'bb_upper': indicators['bb_upper'],
                'bb_lower': indicators['bb_lower']
            })
            key_df = key_df.dropna()
            if key_df.empty:
                raise Exception("Недостаточно валидных данных индикаторов (все NaN). Подождите больше истории или измените таймфрейм.")
            last_idx = key_df.index[-1]
            
            # Текущие значения по последней валидной свече
            current_price = df.loc[last_idx, 'close']
            current_sma = indicators['sma'].loc[last_idx]
            current_sma200 = indicators.get('sma200', pd.Series([np.nan], index=[last_idx])).loc[last_idx]
            current_ema50 = indicators.get('ema50', pd.Series([np.nan], index=[last_idx])).loc[last_idx]
            current_rsi = indicators['rsi'].loc[last_idx]
            current_macd_hist = indicators['macd_histogram'].loc[last_idx]
            current_bb_upper = indicators['bb_upper'].loc[last_idx]
            current_bb_lower = indicators['bb_lower'].loc[last_idx]
            current_stoch_rsi = indicators['stoch_rsi'].loc[last_idx] if 'stoch_rsi' in indicators else np.nan
            current_williams_r = indicators['williams_r'].loc[last_idx] if 'williams_r' in indicators else np.nan
            current_cci = indicators['cci'].loc[last_idx] if 'cci' in indicators else np.nan
            current_adx = indicators['adx'].loc[last_idx] if 'adx' in indicators else np.nan
            current_plus_di = indicators['plus_di'].loc[last_idx] if 'plus_di' in indicators else np.nan
            current_minus_di = indicators['minus_di'].loc[last_idx] if 'minus_di' in indicators else np.nan
            current_atr = indicators['atr'].loc[last_idx] if 'atr' in indicators else np.nan
            current_atr_pct = indicators.get('atr_pct', pd.Series([np.nan], index=[last_idx])).loc[last_idx]
            current_obv = indicators['obv'].loc[last_idx] if 'obv' in indicators else np.nan
            
            # Проверка NaN ключевых значений
            if pd.isna(current_price) or pd.isna(current_sma) or pd.isna(current_rsi):
                raise Exception("Недостаточно валидных данных индикаторов на последней свече. Измените таймфрейм или дождитесь новых данных.")
            
            # Адаптивные веса под рынки
            is_otc = (trade_type or '').lower() == 'otc'
            w_trend = 2.0 if not is_otc else 1.5
            w_momentum = 1.5 if is_otc else 1.2
            w_volatility = 1.0
            w_patterns = 1.0
            
            score = 0.0
            signals = []
            
            # Фильтр низкой волатильности (снижаем уверенность)
            if not pd.isna(current_atr_pct) and current_atr_pct < 0.05:
                signals.append("Низкая волатильность ATR% (<0.05%) (-0.5)")
                score -= 0.5
            
            # Старший тренд (SMA200 / EMA50)
            if not pd.isna(current_sma200):
                if current_price > current_sma200:
                    score += w_trend
                    signals.append(f"Цена > SMA200 (+{w_trend})")
                else:
                    score -= w_trend
                    signals.append(f"Цена < SMA200 (-{w_trend})")
            if not pd.isna(current_ema50):
                if current_price > current_ema50:
                    score += 1.0
                    signals.append("Цена > EMA50 (+1)")
                else:
                    score -= 1.0
                    signals.append("Цена < EMA50 (-1)")
            
            # Базовый тренд (SMA50)
            if current_price > current_sma:
                score += w_trend
                signals.append(f"Цена > SMA50 (+{w_trend})")
            else:
                score -= w_trend
                signals.append(f"Цена < SMA50 (-{w_trend})")
            
            # RSI
            if 50 < current_rsi < 80:
                score += w_momentum
                signals.append(f"RSI: {current_rsi:.1f} (+{w_momentum})")
            elif 20 < current_rsi < 50:
                score -= w_momentum
                signals.append(f"RSI: {current_rsi:.1f} (-{w_momentum})")
            elif current_rsi >= 80:
                score -= 1
                signals.append(f"RSI перекуплен: {current_rsi:.1f} (-1)")
            elif current_rsi <= 20:
                score += 1
                signals.append(f"RSI перепродан: {current_rsi:.1f} (+1)")
            
            # MACD
            if current_macd_hist > 0:
                score += w_momentum
                signals.append(f"MACD > 0 (+{w_momentum})")
            else:
                score -= w_momentum
                signals.append(f"MACD < 0 (-{w_momentum})")
            
            # Полосы Боллинджера
            if current_price <= current_bb_lower:
                score += 1
                signals.append("Цена у нижней BB (+1)")
            elif current_price >= current_bb_upper:
                score -= 1
                signals.append("Цена у верхней BB (-1)")
            
            # Stochastic RSI
            if current_stoch_rsi < 20:
                score += 1
                signals.append(f"Stoch RSI: {current_stoch_rsi:.1f} (+1)")
            elif current_stoch_rsi > 80:
                score -= 1
                signals.append(f"Stoch RSI: {current_stoch_rsi:.1f} (-1)")
            
            # Williams %R
            if current_williams_r < -80:
                score += 1
                signals.append(f"Williams %R: {current_williams_r:.1f} (+1)")
            elif current_williams_r > -20:
                score -= 1
                signals.append(f"Williams %R: {current_williams_r:.1f} (-1)")
            
            # CCI
            if current_cci > 100:
                score += 1
                signals.append(f"CCI: {current_cci:.1f} (+1)")
            elif current_cci < -100:
                score -= 1
                signals.append(f"CCI: {current_cci:.1f} (-1)")
            
            # ADX тренд
            if current_adx > 20:
                if current_plus_di > current_minus_di:
                    score += 1
                    signals.append(f"ADX тренд вверх: {current_adx:.1f} (+1)")
                else:
                    score -= 1
                    signals.append(f"ADX тренд вниз: {current_adx:.1f} (-1)")
            
            # ATR волатильность
            atr_avg = indicators['atr'].rolling(window=20).mean().iloc[-1]
            if current_atr > atr_avg * 1.2:
                score += w_volatility * 0.5
                signals.append(f"Высокая волатильность (+{0.5 * w_volatility})")
            elif current_atr < atr_avg * 0.8:
                score -= w_volatility * 0.5
                signals.append(f"Низкая волатильность (-{0.5 * w_volatility})")
            
            # OBV направление (приблизительное)
            obv_slope = indicators['obv'].iloc[-1] - indicators['obv'].iloc[-5] if len(indicators['obv']) > 5 else 0
            if obv_slope > 0:
                score += 0.5
                signals.append("OBV растет (+0.5)")
            elif obv_slope < 0:
                score -= 0.5
                signals.append("OBV падает (-0.5)")
            
            # Паттерны свечей
            if indicators.get('bull_engulf', pd.Series([False])).iloc[-1]:
                score += w_patterns
                signals.append(f"Бычье поглощение (+{w_patterns})")
            if indicators.get('bear_engulf', pd.Series([False])).iloc[-1]:
                score -= w_patterns
                signals.append(f"Медвежье поглощение (-{w_patterns})")
            if indicators.get('is_bull_pin', pd.Series([False])).iloc[-1]:
                score += 0.5
                signals.append("Пин-бар бычий (+0.5)")
            if indicators.get('is_bear_pin', pd.Series([False])).iloc[-1]:
                score -= 0.5
                signals.append("Пин-бар медвежий (-0.5)")
            if indicators.get('is_doji', pd.Series([False])).iloc[-1]:
                signals.append("Доджи (нейтрально)")
            
            # Результат и сила
            strength = "СИЛЬНЫЙ БЫЧИЙ" if score >= SIGNAL_THRESHOLDS['strong_bull'] else \
                       "СЛАБЫЙ БЫЧИЙ" if score >= SIGNAL_THRESHOLDS['weak_bull'] else \
                       "СЛАБЫЙ МЕДВЕЖИЙ" if score <= SIGNAL_THRESHOLDS['weak_bear'] else \
                       "СИЛЬНЫЙ МЕДВЕЖИЙ" if score <= SIGNAL_THRESHOLDS['strong_bear'] else "НЕЙТРАЛЬНЫЙ"
            if strength in ["СИЛЬНЫЙ БЫЧИЙ", "СЛАБЫЙ БЫЧИЙ"]:
                sticker = "🟢 ВВЕРХ ▲"
            elif strength in ["СЛАБЫЙ МЕДВЕЖИЙ", "СИЛЬНЫЙ МЕДВЕЖИЙ"]:
                sticker = "🔴 ВНИЗ ▼"
            else:
                sticker = "🟡 НЕЙТРАЛЬНО ➡️"
            
            return {
                'signal': sticker,
                'strength': strength,
                'score': round(float(score), 2),
                'signals': signals,
                'current_price': current_price,
                'values': {
                    'RSI': round(float(current_rsi), 2),
                    'MACD_hist': round(float(current_macd_hist), 6),
                    'Williams %R': round(float(current_williams_r), 1) if not pd.isna(current_williams_r) else None,
                    'CCI': round(float(current_cci), 1) if not pd.isna(current_cci) else None,
                    'ADX': round(float(current_adx), 1) if not pd.isna(current_adx) else None,
                    'ATR': round(float(current_atr), 5) if not pd.isna(current_atr) else None,
                    'ATR%': round(float(current_atr_pct), 3) if not pd.isna(current_atr_pct) else None,
                    'SMA200': round(float(current_sma200), 5) if not pd.isna(current_sma200) else None,
                    'EMA50': round(float(current_ema50), 5) if not pd.isna(current_ema50) else None
                }
            }
        except Exception as e:
            logger.error(f"Ошибка при анализе сигналов: {e}")
            raise Exception(f"Ошибка анализа: {str(e)}")

    def check_all_symbols(self):
        # Список всех валютных пар из клавиатуры и маппинга
        all_symbols = [
            'EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'NZD/USD', 'USD/CAD', 'USD/CHF',
            'AUD/JPY', 'EUR/JPY', 'GBP/JPY', 'CAD/JPY', 'CHF/JPY', 'EUR/GBP', 'AUD/CAD',
            'NZD/JPY', 'EURAUD', 'GBPAUD', 'AUDNZD', 'EURNZD', 'GBPNZD', 'GBPCHF', 'EURCHF', 'AUDCHF', 'CADCHF', 'NZDCHF',
            'BTC/USDT', 'ETH/USDT'
        ]
        available = []
        unavailable = []
        for symbol in all_symbols:
            try:
                # Пробуем получить хотя бы одну свечу (1h)
                self.get_ohlcv_data(symbol, '1h', limit=1)
                available.append(symbol)
            except Exception as e:
                unavailable.append(f"{symbol} ({e})")
        logger.info(f"Доступные пары: {', '.join(available)}")
        if unavailable:
            logger.warning(f"Недоступные пары: {', '.join(unavailable)}")

PO_FOREX_SYMBOLS = {
    'EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'NZD/USD', 'USD/CAD', 'USD/CHF',
    'AUD/JPY', 'EUR/JPY', 'GBP/JPY', 'CAD/JPY', 'CHF/JPY',
    'EUR/CAD'
}
# Нормализованный вид разрешенных форекс-пар (без разделителей)
PO_FOREX_SYMBOLS_NORMALIZED = {s.replace('/', '').upper() for s in PO_FOREX_SYMBOLS}

PO_ALL_SYMBOLS = [
    'EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'NZD/USD', 'USD/CAD', 'USD/CHF',
    'AUD/JPY', 'EUR/JPY', 'GBP/JPY', 'CAD/JPY', 'CHF/JPY', 'EUR/GBP', 'AUD/CAD',
    'NZD/JPY', 'EURAUD', 'GBPAUD', 'AUDNZD', 'EURNZD', 'GBPNZD', 'GBPCHF', 'EURCHF', 'AUDCHF', 'CADCHF', 'NZDCHF',
    'BTC/USDT', 'ETH/USDT'
]

def _normalize_pair_text(pair: str) -> str:
    return pair.upper().replace('/', '').replace(' ', '')

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
        # Задачи анализа по user_id
        self.analysis_tasks = {}
        # Доступные пары (динамически)
        self.available_symbols = set()
        # Проверка всех валютных пар при старте
        self.refresh_symbols()
    
    def setup_handlers(self):
        """Регистрация всех обработчиков бота"""
        # Инлайн-кнопки
        self.application.add_handler(CallbackQueryHandler(self.cancel_analysis_during, pattern="^cancel_analysis$"))
        self.application.add_handler(CallbackQueryHandler(self.show_analysis_details, pattern="^show_details:"))
        self.application.add_handler(CallbackQueryHandler(self.hide_analysis_details, pattern="^hide_details:"))
        
        # Команды
        self.application.add_handler(CommandHandler('help', self.help_command))
        self.application.add_handler(CommandHandler('upd', self.update_symbols_command))
        self.application.add_handler(CommandHandler('search', self.search_command))
        
        # Основной диалог анализа
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
    
    def refresh_symbols(self):
        available = set()
        for sym in PO_ALL_SYMBOLS:
            try:
                # Пробуем получить хотя бы одну свечу
                self.analyzer.get_ohlcv_data(sym, '1h', limit=1)
                available.add(sym)
            except Exception:
                continue
        self.available_symbols = available
    
    async def update_symbols_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("⏳ Обновляю список доступных пар...")
        self.refresh_symbols()
        if not self.available_symbols:
            await update.message.reply_text("❌ Не удалось определить доступные пары сейчас. Попробуйте позже.")
            return
        lst = sorted(list(self.available_symbols))
        text = "✅ Доступные пары (по данным источников):\n" + ", ".join(lst)
        await update.message.reply_text(text[:4000])

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для поиска лучшего прогноза среди всех пар"""
        await update.message.reply_text("🔍 Поиск лучшего прогноза среди всех пар...\n\n⏳ Обновление списка доступных пар...")
        
        # Сначала обновляем список символов
        self.refresh_symbols()
        
        if not self.available_symbols:
            await update.message.reply_text("❌ Не удалось найти доступные пары для анализа.")
            return
        
        await update.message.reply_text(f"📊 Найдено {len(self.available_symbols)} пар. Начинаю анализ...")
        
        # Анализируем все доступные пары
        best_prediction = await self.analyze_all_pairs()
        
        if best_prediction:
            # Форматируем результат лучшего прогноза
            result_text = f"🏆 ЛУЧШИЙ ПРОГНОЗ НАЙДЕН!\n\n"
            result_text += f"💱 Пара: {best_prediction['symbol']}\n"
            result_text += f"⏰ Таймфрейм: {best_prediction['timeframe']}\n"
            result_text += f"📈 Прогноз: {best_prediction['prediction']}\n"
            result_text += f"🎯 Уверенность: {best_prediction['confidence']:.1f}%\n"
            result_text += f"💰 Текущая цена: {best_prediction['current_price']}\n\n"
            result_text += f"📋 Обоснование:\n{best_prediction['justification']}\n\n"
            result_text += f"⚠️ Предупреждение:\nТолько для информационных целей\nНе является финансовой рекомендацией\nТорговля связана с рисками"
            
            await update.message.reply_text(result_text)
        else:
            await update.message.reply_text("❌ Не удалось найти подходящий прогноз среди всех пар.")

    async def analyze_all_pairs(self) -> Dict:
        """Анализ всех доступных пар и выбор лучшего прогноза"""
        best_prediction = None
        best_score = -float('inf')
        
        # Анализируем каждую пару на разных таймфреймах
        timeframes = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
        
        for symbol in self.available_symbols:
            for timeframe in timeframes:
                try:
                    # Выполняем анализ
                    result = await self.perform_analysis(symbol, timeframe, "Forex")
                    
                    if result and result.get('prediction') and result['prediction'] != "НЕЙТРАЛЬНО":
                        # Рассчитываем общий балл уверенности
                        confidence = result.get('confidence', 0)
                        score = result.get('total_score', 0)
                        
                        # Комбинированный балл: уверенность + общий балл
                        combined_score = confidence + (score * 0.1)
                        
                        if combined_score > best_score:
                            best_score = combined_score
                            best_prediction = {
                                'symbol': symbol,
                                'timeframe': timeframe,
                                'prediction': result['prediction'],
                                'confidence': confidence,
                                'current_price': result.get('current_price', 'N/A'),
                                'justification': result.get('justification', ''),
                                'total_score': score,
                                'combined_score': combined_score
                            }
                            
                except Exception as e:
                    logger.debug(f"Ошибка анализа {symbol} {timeframe}: {e}")
                    continue
        
        return best_prediction
    
    def _build_symbols_keyboard(self, trade_type_text: str) -> InlineKeyboardMarkup:
        # Используем динамически доступные пары, если есть; иначе показываем дефолтный список
        symbols = sorted(list(self.available_symbols)) if self.available_symbols else PO_ALL_SYMBOLS
        # Формируем клавиатуру 2 кнопки в ряд
        rows = []
        row = []
        for s in symbols:
            row.append(InlineKeyboardButton(s, callback_data=s))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        rows.append([InlineKeyboardButton("✏️ Ввести вручную", callback_data="manual_input")])
        return InlineKeyboardMarkup(rows)
    
    async def trade_type_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора типа торговли"""
        query = update.callback_query
        await query.answer()
        
        trade_type = query.data
        context.user_data['trade_type'] = trade_type
        
        trade_text = "ОТС (Бинарные опционы)" if trade_type == "otc" else "Обычная торговля"
        context.user_data['trade_type_text'] = trade_text
        
        # Клавиатура для выбора валютной пары с учетом доступности на Pocket Option
        reply_markup = self._build_symbols_keyboard(trade_text)
        
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
        
        # Клавиатура для выбора таймфрейма + отмена
        keyboard = [
            [InlineKeyboardButton("1m", callback_data="1m"), InlineKeyboardButton("2m", callback_data="2m"), InlineKeyboardButton("3m", callback_data="3m")],
            [InlineKeyboardButton("4m", callback_data="4m"), InlineKeyboardButton("5m", callback_data="5m"), InlineKeyboardButton("6m", callback_data="6m")],
            [InlineKeyboardButton("7m", callback_data="7m"), InlineKeyboardButton("8m", callback_data="8m"), InlineKeyboardButton("9m", callback_data="9m")],
            [InlineKeyboardButton("10m", callback_data="10m"), InlineKeyboardButton("15m", callback_data="15m")],
            [InlineKeyboardButton("❌ Отменить", callback_data="cancel_analysis")]
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
        # Без жёсткой блокировки: пробуем работать с тем, что ввёл пользователь
        context.user_data['symbol'] = symbol
        
        # Клавиатура для выбора таймфрейма + отмена
        keyboard = [
            [InlineKeyboardButton("1m", callback_data="1m"), InlineKeyboardButton("2m", callback_data="2m"), InlineKeyboardButton("3m", callback_data="3m")],
            [InlineKeyboardButton("4m", callback_data="4m"), InlineKeyboardButton("5m", callback_data="5m"), InlineKeyboardButton("6m", callback_data="6m")],
            [InlineKeyboardButton("7m", callback_data="7m"), InlineKeyboardButton("8m", callback_data="8m"), InlineKeyboardButton("9m", callback_data="9m")],
            [InlineKeyboardButton("10m", callback_data="10m"), InlineKeyboardButton("15m", callback_data="15m")],
            [InlineKeyboardButton("❌ Отменить", callback_data="cancel_analysis")]
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
            user_id = update.effective_user.id
            # Если уже есть задача анализа для пользователя — отменяем её
            prev_task = self.analysis_tasks.get(user_id)
            if prev_task and not prev_task.done():
                prev_task.cancel()
            # Запускаем новую задачу анализа
            analysis_task = asyncio.create_task(self.perform_analysis(symbol, timeframe, context.user_data.get('trade_type')))
            self.analysis_tasks[user_id] = analysis_task
            result = await analysis_task
            
            logger.info(f"Анализ {symbol} завершен успешно")
            
            # Формируем подробности и определяем нейтральность
            details = self.format_analysis_details(result)
            is_neutral = 'НЕЙТРАЛЬНО' in result['signal'].upper()
            forecast_id = None
            
            # Если прогноз не нейтральный — сохраняем прогноз и тексты для переключения
            if not is_neutral:
                forecast_id = f"{symbol}_{timeframe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                # Формируем краткую сводку и клавиатуру
                summary_text, reply_markup = self.format_analysis_result(symbol, timeframe, result, trade_type, forecast_id, details)
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
                    'message_id': query.message.message_id,
                    'details': details,
                    'summary': summary_text
                }
                await query.edit_message_text(summary_text, parse_mode='Markdown', reply_markup=reply_markup)
                # Автопроверка только для не нейтральных
                await self.schedule_forecast_check(forecast_id, timeframe, update.effective_user.id)
            else:
                # Для нейтральных — без forecast_id, без кнопки и без автопроверки
                summary_text, _ = self.format_analysis_result(symbol, timeframe, result, trade_type, None, details)
                await query.edit_message_text(summary_text, parse_mode='Markdown', reply_markup=None)
            
            # Лог
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
            # Мягкое сообщение без деталей исключения
            error_message = (
                "❌ *Не удалось выполнить анализ*\n\n"
                "Пара может быть временно недоступна. Попробуйте другую пару или повторите позже.\n\n"
                "🔄 /analyze - Попробовать снова\n"
                "📚 /help - Справка"
            )
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
            # Получаем текущие данные (последняя валидная свеча на момент проверки)
            current_df = self.analyzer.get_ohlcv_data(forecast['symbol'], forecast['timeframe'], limit=5)
            current_df = current_df.dropna()
            if current_df.empty:
                raise Exception("Нет валидных данных для проверки")
            current_close = current_df['close'].iloc[-1]
            
            # Цена открытия из момента прогноза
            open_price = float(forecast['current_price'])
            close_price = float(current_close)
            
            # Единые правила пунктов без исключений: вычисляем динамически по масштабу цены
            # Если цена крупная (>= 20), шаг пункта 0.01, иначе 0.0001 (универсально и просто)
            pip_size = 0.01 if max(open_price, close_price) >= 20 else 0.0001
            points_abs = abs(close_price - open_price) / pip_size
            
            # Определение результата согласно направлению
            direction_up = "ВВЕРХ" in (forecast['prediction'] or "")
            direction_down = "ВНИЗ" in (forecast['prediction'] or "")
            went_up = close_price > open_price
            
            if direction_up:
                prediction_correct = went_up
            elif direction_down:
                prediction_correct = not went_up
            else:
                # Нейтральный прогноз не оцениваем как плюс/минус
                prediction_correct = False
            
            result = "✅ ПЛЮС" if prediction_correct else ("❌ МИНУС" if (direction_up or direction_down) else "➡️ НЕЙТРАЛЬНО")
            
            return {
                'result': result,
                'open_price': open_price,
                'close_price': close_price,
                'points': round(points_abs, 2),
                'prediction_correct': prediction_correct
            }
            
        except Exception as e:
            logger.error(f"Ошибка при проверке прогноза: {e}")
            # Возвращаем мягкий результат без падения
            return {
                'result': "⚠️ НЕТ ДАННЫХ",
                'open_price': forecast.get('current_price', None),
                'close_price': None,
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
    
    async def perform_analysis(self, symbol: str, timeframe: str, trade_type: Optional[str] = None) -> Dict:
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
                asyncio.to_thread(self.analyzer.analyze_signals, df, indicators, trade_type),
                timeout=10.0  # 10 секунд таймаут
            )
            
            return analysis_result
        except asyncio.CancelledError:
            logger.info(f"Анализ {symbol} на {timeframe} отменён пользователем")
            raise
        except Exception as e:
            logger.error(f"Ошибка при анализе {symbol}: {e}")
            raise
    
    def format_analysis_result(self, symbol: str, timeframe: str, result: Dict, trade_type: str, forecast_id: str = None, details: str = None) -> (str, InlineKeyboardMarkup):
        # Краткий результат
        main = f"📊 *РЕЗУЛЬТАТ АНАЛИЗА*\n\n"
        main += f"🎯 Актив: {symbol}\n⏰ Таймфрейм: {timeframe}\nТип: {trade_type}\n\n"
        main += f"🚨 ПРОГНОЗ: {result['signal']}\n💪 Сила сигнала: {result['strength']}\n📈 Общий балл: {result['score']}\n\n"
        if forecast_id:
            main += f"⏰ Автоматическая проверка через {timeframe}\n\n"
        main += "⚠️ Только для информационных целей\nНе является финансовой рекомендацией\nТорговля связана с рисками\n\n"
        main += "🔄 /analyze - Новый анализ\n"
        reply_markup = None
        if forecast_id:
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Подробнее", callback_data=f"show_details:{forecast_id}")]])
        return main, reply_markup

    def format_analysis_details(self, result: Dict) -> str:
        # Формирует подробное обоснование и значения индикаторов
        details = "📋 Обоснование:\n" + "\n".join([f"• {s}" for s in result.get('signals', [])])
        details += "\n\n📊 Значения:\n"
        for k, v in result.get('values', {}).items():
            details += f"• {k}: {v}\n"
        details += "\n========================="
        return details
    
    async def show_analysis_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        forecast_id = query.data.split(':')[1] if ':' in query.data else None
        forecast = self.forecasts.get(forecast_id)
        if not forecast:
            await query.answer("Детали недоступны", show_alert=True)
            return
        details = forecast.get('details')
        if not details:
            await query.answer("Нет подробностей", show_alert=True)
            return
        close_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Закрыть", callback_data=f"hide_details:{forecast_id}")]])
        await query.edit_message_text(details, parse_mode='Markdown', reply_markup=close_markup)

    async def hide_analysis_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        forecast_id = query.data.split(':')[1] if ':' in query.data else None
        forecast = self.forecasts.get(forecast_id)
        if not forecast:
            await query.answer("Нет данных", show_alert=True)
            return
        summary = forecast.get('summary')
        if not summary:
            await query.answer("Сводка недоступна", show_alert=True)
            return
        more_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Подробнее", callback_data=f"show_details:{forecast_id}")]])
        await query.edit_message_text(summary, parse_mode='Markdown', reply_markup=more_markup)
    
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
            # Отменяем задачу анализа, если есть
            user_id = update.effective_user.id
            analysis_task = self.analysis_tasks.get(user_id)
            if analysis_task and not analysis_task.done():
                analysis_task.cancel()
            if user_id in self.analysis_tasks:
                del self.analysis_tasks[user_id]
            
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
    
    async def check_symbols_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        all_symbols = [
            'EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'NZD/USD', 'USD/CAD', 'USD/CHF',
            'AUD/JPY', 'EUR/JPY', 'GBP/JPY', 'CAD/JPY', 'CHF/JPY', 'EUR/GBP', 'AUD/CAD',
            'NZD/JPY', 'EURAUD', 'GBPAUD', 'AUDNZD', 'EURNZD', 'GBPNZD', 'GBPCHF', 'EURCHF', 'AUDCHF', 'CADCHF', 'NZDCHF',
            'BTC/USDT', 'ETH/USDT'
        ]
        available = []
        unavailable = []
        for symbol in all_symbols:
            try:
                self.analyzer.get_ohlcv_data(symbol, '1h', limit=1)
                available.append(symbol)
            except Exception as e:
                unavailable.append(f"{symbol} ({str(e)[:40]})")
        msg = f"✅ Доступные пары ({len(available)}):\n" + ", ".join(available)
        if unavailable:
            msg += f"\n\n❌ Недоступные пары ({len(unavailable)}):\n" + "\n".join(unavailable)
        await update.message.reply_text(msg[:4000])
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        help_text = (
            "📚 Справка\n\n"
            "Команды:\n"
            "• /start — начать\n"
            "• /analyze — анализ\n"
            "• /search — найти лучший прогноз среди всех пар\n"
            "• /upd — обновить список доступных пар\n"
            "• /cancel — отменить текущий анализ\n\n"
            "Подсказки:\n"
            "— Выберите тип торговли (ОТС/Обычная).\n"
            "— Введите или выберите валютную пару и таймфрейм.\n"
            "— Итог можно раскрыть кнопкой ‘Подробнее’."
        )
        await update.message.reply_text(help_text)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start — предлагает выбор типа торговли"""
        keyboard = [[
            InlineKeyboardButton("ОТС (Бинарные опционы)", callback_data="otc"),
            InlineKeyboardButton("Обычная торговля", callback_data="regular")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.message:
            await update.message.reply_text(
                "📈 *Выберите тип торговли:*",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            # fallback для callback
            await self.application.bot.send_message(
                chat_id=update.effective_chat.id,
                text="📈 *Выберите тип торговли:*",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        return TRADE_TYPE

    async def start_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /analyze — аналог /start, начинает выбор типа торговли"""
        return await self.start_command(update, context)
    
    def run(self):
        """Запуск бота"""
        logger.info("Бот запущен")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    bot = TelegramBot()
    bot.run()
