"""
Умная фильтрация аномалий с учетом множества факторов
Снижает количество ложных срабатываний
"""

from typing import Dict, Optional
from datetime import datetime, timezone, timedelta
from collections import deque
import math

from src.services.logging_service import get_logger

logger = get_logger(__name__)


class AnomalyScore:
    """Результат оценки аномалии"""
    
    def __init__(
        self,
        is_significant: bool,
        score: float,
        reasons: list,
        z_score: float,
        delta_pct: float
    ):
        self.is_significant = is_significant
        self.score = score
        self.reasons = reasons
        self.z_score = z_score
        self.delta_pct = delta_pct
    
    def to_dict(self) -> Dict:
        return {
            "is_significant": self.is_significant,
            "score": self.score,
            "reasons": self.reasons,
            "z_score": self.z_score,
            "delta_pct": self.delta_pct
        }


class AnomalyFilter:
    """Умная фильтрация аномалий"""
    
    def __init__(self):
        # История аномалий для каждого тикера
        self._anomaly_history: Dict[str, deque] = {}
        # Максимальное время хранения истории
        self._history_window = timedelta(hours=6)
        # Максимум аномалий в истории
        self._max_history_size = 50
    
    def evaluate_anomaly(
        self,
        ticker: str,
        z_score: float,
        delta: float,
        price: float,
        timestamp: str,
        timeframe: str,
        volume: Optional[float] = None
    ) -> AnomalyScore:
        """
        Оценка значимости аномалии с учетом множества факторов
        
        Args:
            ticker: Тикер
            z_score: Z-score значение
            delta: Изменение цены (close - open)
            price: Текущая цена
            timestamp: Время аномалии
            timeframe: Таймфрейм (M1, M5, M30)
            volume: Объём торгов (опционально)
            
        Returns:
            AnomalyScore с оценкой значимости
        """
        reasons = []
        score = 0.0
        
        # Парсим timestamp
        try:
            anomaly_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except:
            anomaly_time = datetime.now(timezone.utc)
        
        # Вычисляем процентное изменение
        delta_pct = (delta / price * 100) if price > 0 else 0
        
        # 1. Базовая оценка Z-score (вес 30%)
        z_score_abs = abs(z_score)
        if z_score_abs > 10:
            score += 30
            reasons.append(f"Очень высокий Z-score: {z_score_abs:.1f}")
        elif z_score_abs > 7:
            score += 20
            reasons.append(f"Высокий Z-score: {z_score_abs:.1f}")
        elif z_score_abs > 5:
            score += 10
            reasons.append(f"Средний Z-score: {z_score_abs:.1f}")
        else:
            score += 5
            reasons.append(f"Низкий Z-score: {z_score_abs:.1f}")
        
        # 2. Оценка изменения цены (вес 25%)
        delta_abs_pct = abs(delta_pct)
        if delta_abs_pct > 5:
            score += 25
            reasons.append(f"Сильное изменение цены: {delta_abs_pct:.2f}%")
        elif delta_abs_pct > 2:
            score += 15
            reasons.append(f"Умеренное изменение цены: {delta_abs_pct:.2f}%")
        elif delta_abs_pct > 0.5:
            score += 5
            reasons.append(f"Слабое изменение цены: {delta_abs_pct:.2f}%")
        
        # 3. Оценка времени (вес 15%)
        if self._is_trading_hours(anomaly_time):
            score += 15
            reasons.append("Время торговой сессии")
        else:
            score += 5
            reasons.append("Внерыночное время (низкая ликвидность)")
        
        # 4. Оценка таймфрейма (вес 10%)
        timeframe_scores = {
            'M1': 5,   # M1 - низкий вес (много шума)
            'M5': 10,  # M5 - средний вес
            'M30': 15, # M30 - высокий вес (более значимо)
            'H1': 15
        }
        tf_score = timeframe_scores.get(timeframe, 5)
        score += tf_score
        reasons.append(f"Таймфрейм {timeframe}")
        
        # 5. Проверка частоты аномалий (вес 20%)
        frequency_penalty = self._check_anomaly_frequency(ticker, anomaly_time)
        score += frequency_penalty
        if frequency_penalty < 10:
            reasons.append(f"Частые аномалии (penalty: {20-frequency_penalty})")
        else:
            reasons.append("Нормальная частота аномалий")
        
        # 6. Комбинированные факторы (бонусы)
        # Сильный Z-score + сильное изменение цены = значительная аномалия
        if z_score_abs > 8 and delta_abs_pct > 2:
            score += 10
            reasons.append("Комбо: сильный Z-score + сильное изменение")
        
        # Рыночное время + M30 + сильный сигнал
        if self._is_trading_hours(anomaly_time) and timeframe in ['M30', 'H1'] and z_score_abs > 7:
            score += 10
            reasons.append("Комбо: торговое время + значимый таймфрейм + сильный сигнал")
        
        # Сохраняем аномалию в историю
        self._add_to_history(ticker, anomaly_time)
        
        # Определяем порог значимости
        # Шкала: 0-100
        # 0-40: не значимо
        # 40-60: умеренно значимо
        # 60-80: значимо
        # 80-100: очень значимо
        
        is_significant = score >= 50  # Порог 50 баллов
        
        logger.info(
            f"Аномалия {ticker}: score={score:.1f}, significant={is_significant}, "
            f"z={z_score:.2f}, delta={delta_pct:.2f}%, reasons={len(reasons)}"
        )
        
        return AnomalyScore(
            is_significant=is_significant,
            score=score,
            reasons=reasons,
            z_score=z_score,
            delta_pct=delta_pct
        )
    
    def _is_trading_hours(self, dt: datetime) -> bool:
        """
        Проверка, является ли время торговым
        Московская биржа: 10:00-18:45 MSK (понедельник-пятница)
        """
        # Конвертируем в MSK (UTC+3)
        msk_time = dt + timedelta(hours=3)
        
        # Проверка дня недели (0=понедельник, 6=воскресенье)
        if msk_time.weekday() >= 5:  # Суббота или воскресенье
            return False
        
        # Проверка времени (10:00 - 18:45)
        hour = msk_time.hour
        minute = msk_time.minute
        
        if hour < 10:
            return False
        if hour > 18:
            return False
        if hour == 18 and minute > 45:
            return False
        
        return True
    
    def _check_anomaly_frequency(self, ticker: str, current_time: datetime) -> float:
        """
        Проверка частоты аномалий для тикера
        Возвращает штраф 0-20 баллов (чем чаще, тем меньше баллов)
        """
        if ticker not in self._anomaly_history:
            return 20  # Первая аномалия - полные баллы
        
        history = self._anomaly_history[ticker]
        
        # Очищаем старые записи
        cutoff_time = current_time - self._history_window
        while history and history[0] < cutoff_time:
            history.popleft()
        
        # Подсчитываем аномалии за последний час
        hour_ago = current_time - timedelta(hours=1)
        recent_count = sum(1 for t in history if t > hour_ago)
        
        # Штраф за частоту
        # 0-1 аномалий в час: 20 баллов
        # 2-3 аномалии в час: 15 баллов
        # 4-5 аномалий в час: 10 баллов
        # 6+ аномалий в час: 5 баллов
        if recent_count <= 1:
            return 20
        elif recent_count <= 3:
            return 15
        elif recent_count <= 5:
            return 10
        else:
            return 5
    
    def _add_to_history(self, ticker: str, timestamp: datetime):
        """Добавить аномалию в историю"""
        if ticker not in self._anomaly_history:
            self._anomaly_history[ticker] = deque(maxlen=self._max_history_size)
        
        self._anomaly_history[ticker].append(timestamp)
    
    def get_ticker_stats(self, ticker: str) -> Dict:
        """Получить статистику по тикеру"""
        if ticker not in self._anomaly_history:
            return {
                "ticker": ticker,
                "total_anomalies": 0,
                "last_anomaly": None
            }
        
        history = self._anomaly_history[ticker]
        now = datetime.now(timezone.utc)
        
        # Очищаем старые
        cutoff_time = now - self._history_window
        while history and history[0] < cutoff_time:
            history.popleft()
        
        return {
            "ticker": ticker,
            "total_anomalies": len(history),
            "last_anomaly": history[-1].isoformat() if history else None,
            "anomalies_last_hour": sum(1 for t in history if t > now - timedelta(hours=1))
        }


# Глобальный фильтр
_anomaly_filter: Optional[AnomalyFilter] = None


def get_anomaly_filter() -> AnomalyFilter:
    """Получить глобальный фильтр аномалий (singleton)"""
    global _anomaly_filter
    
    if _anomaly_filter is None:
        _anomaly_filter = AnomalyFilter()
    
    return _anomaly_filter