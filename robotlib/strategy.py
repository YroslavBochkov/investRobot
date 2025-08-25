import datetime
import math
import random

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from tinkoff.invest import (
    Candle,
    HistoricCandle,
    Instrument,
    MarketDataResponse,
    OrderType,
    OrderDirection,
    OrderState,
    Quotation,
    SubscriptionInterval,
)
from robotlib.money import Money
from robotlib.vizualization import Visualizer


@dataclass
class TradeStrategyParams:
    instrument_balance: int
    currency_balance: float
    pending_orders: list[OrderState]


@dataclass
class RobotTradeOrder:
    quantity: int
    direction: OrderDirection
    price: Money | None = None
    order_type: OrderType = OrderType.ORDER_TYPE_MARKET


@dataclass
class StrategyDecision:
    robot_trade_order: RobotTradeOrder | None = None
    cancel_orders: list[OrderState] = field(default_factory=list)


class TradeStrategyBase(ABC):
    instrument_info: Instrument

    @property
    @abstractmethod
    def candle_subscription_interval(self) -> SubscriptionInterval:
        return SubscriptionInterval.SUBSCRIPTION_INTERVAL_ONE_MINUTE

    @property
    @abstractmethod
    def order_book_subscription_depth(self) -> int | None:  # set not None to subscribe robot to order book
        return None

    @property
    @abstractmethod
    def trades_subscription(self) -> bool:  # set True to subscribe robot to trades stream
        return False

    @property
    @abstractmethod
    def strategy_id(self) -> str:
        """
        string representing short strategy name for logger
        """
        raise NotImplementedError()

    def load_instrument_info(self, instrument_info: Instrument):
        self.instrument_info = instrument_info

    def load_candles(self, candles: list[HistoricCandle]) -> None:
        """
        Method used by robot to load historic data
        """
        pass

    @abstractmethod
    def decide(self, market_data: MarketDataResponse, params: TradeStrategyParams) -> StrategyDecision:
        if market_data.candle:
            return self.decide_by_candle(market_data.candle, params)
        return StrategyDecision()

    @abstractmethod
    def decide_by_candle(self, candle: Candle | HistoricCandle, params: TradeStrategyParams) -> StrategyDecision:
        pass


class RandomStrategy(TradeStrategyBase):
    request_candles: bool = True
    strategy_id: str = 'random'

    low: int
    high: int

    def __init__(self, low: int, high: int):
        self.low = low
        self.high = high

    def decide(self, market_data: MarketDataResponse, params: TradeStrategyParams) -> StrategyDecision:
        return self.decide_by_candle(market_data.candle, params)

    def decide_by_candle(self, candle: Candle | HistoricCandle, params: TradeStrategyParams) -> StrategyDecision:
        low = max(self.low, -params.instrument_balance)
        high = min(self.high, math.floor(params.currency_balance / self.convert_quotation(candle.close)))

        quantity = random.randint(low, high)
        direction = OrderDirection.ORDER_DIRECTION_BUY if quantity > 0 else OrderDirection.ORDER_DIRECTION_SELL

        return StrategyDecision(RobotTradeOrder(quantity=quantity, direction=direction))

    @staticmethod
    def convert_quotation(amount: Quotation) -> float | None:
        if amount is None:
            return None
        return amount.units + amount.nano / (10 ** 9)


class MAEStrategy(TradeStrategyBase):
    request_candles: bool = True
    strategy_id: str = 'mae'

    candle_subscription_interval: SubscriptionInterval = SubscriptionInterval.SUBSCRIPTION_INTERVAL_ONE_MINUTE
    order_book_subscription_depth = None
    trades_subscription = None

    short_len: int
    long_len: int
    trade_count: int
    prices = dict[datetime.datetime, Money]
    prev_sign: bool

    def __init__(self, short_len: int = 5, long_len: int = 20, trade_count: int = 1, visualizer: Visualizer = None):
        assert long_len > short_len
        self.short_len = short_len
        self.long_len = long_len
        self.trade_count = trade_count
        self.prices = {}
        self.visualizer = visualizer

    def load_candles(self, candles: list[HistoricCandle]) -> None:
        self.prices = {candle.time.replace(second=0, microsecond=0): Money(candle.close)
                       for candle in candles[-self.long_len:]}
        self.prev_sign = self._short_avg() > self._long_avg()

    def decide(self, market_data: MarketDataResponse, params: TradeStrategyParams) -> StrategyDecision:
        return self.decide_by_candle(market_data.candle, params)

    def decide_by_candle(self, candle: Candle | HistoricCandle, params: TradeStrategyParams) -> StrategyDecision:
        time: datetime = candle.time.replace(second=0, microsecond=0)
        order: RobotTradeOrder | None = None
        # Добавляем цену в историю для расчёта средних
        self.prices[time] = Money(candle.close)
        # Делаем сделки только если накоплено достаточно данных
        if len(self.prices) >= self.long_len:
            short_avg = self._short_avg()
            long_avg = self._long_avg()
            min_diff = 0.1  # минимальная разница между средними для сигнала
            sign = short_avg > long_avg
            # Фильтр: не торгуем, если разница между средними слишком мала
            if abs(short_avg - long_avg) < min_diff:
                if self.visualizer:
                    self.visualizer.add_price(time, Money(candle.close).to_float())
                    self.visualizer.update_plot()
                return StrategyDecision(robot_trade_order=None)
            # Покупка: короткая пересекает длинную снизу вверх
            if sign and not self.prev_sign:
                # ФИЛЬТР: не покупать, если уже есть позиция
                if params.instrument_balance == 0:
                    lot_price = Money(candle.close).to_float() * self.instrument_info.lot
                    lots_available = int(params.currency_balance / lot_price)
                    if lots_available > 0:
                        order = RobotTradeOrder(quantity=min(self.trade_count, lots_available),
                                                direction=OrderDirection.ORDER_DIRECTION_BUY)
                        if self.visualizer:
                            self.visualizer.add_buy(time)
            # Продажа: короткая пересекает длинную сверху вниз
            elif not sign and self.prev_sign:
                # ФИЛЬТР: не продавать, если позиции нет
                if params.instrument_balance > 0:
                    order = RobotTradeOrder(quantity=min(self.trade_count, params.instrument_balance),
                                            direction=OrderDirection.ORDER_DIRECTION_SELL)
                    if self.visualizer:
                        self.visualizer.add_sell(time)
            self.prev_sign = sign
        if self.visualizer:
            self.visualizer.add_price(time, Money(candle.close).to_float())
            self.visualizer.update_plot()

        return StrategyDecision(robot_trade_order=order)

    def get_prices_list(self) -> list[Money]:
        # sort by keys and then convert to a list of values
        return list(map(lambda x: x[1], sorted(self.prices.items(), key=lambda x: x[0])))

    def _long_avg(self):
        prices = self.get_prices_list()
        if len(prices) < self.long_len:
            return 0
        return sum(float(price) for price in prices[-self.long_len:]) / self.long_len

    def _short_avg(self):
        prices = self.get_prices_list()
        if len(prices) < self.short_len:
            return 0
        return sum(float(price) for price in prices[-self.short_len:]) / self.short_len

class BreakoutStrategy(TradeStrategyBase):
    request_candles: bool = True
    strategy_id: str = 'breakout'

    candle_subscription_interval: SubscriptionInterval = SubscriptionInterval.SUBSCRIPTION_INTERVAL_ONE_MINUTE
    order_book_subscription_depth = None
    trades_subscription = None

    def __init__(self, window: int = 60, trade_count: int = 1, min_range: float = 0.0005, visualizer: Visualizer = None):
        self.window = window
        self.trade_count = trade_count
        self.min_range = min_range  # минимальный диапазон для фильтрации "пилы"
        self.visualizer = visualizer
        self.prices = []

    def load_candles(self, candles: list[HistoricCandle]) -> None:
        self.prices = [float(candle.close.units + candle.close.nano / 1e9) for candle in candles[-self.window:]]

    def decide(self, market_data: MarketDataResponse, params: TradeStrategyParams) -> StrategyDecision:
        return self.decide_by_candle(market_data.candle, params)

    def decide_by_candle(self, candle: Candle | HistoricCandle, params: TradeStrategyParams) -> StrategyDecision:
        import pytz
        msk = pytz.timezone('Europe/Moscow')
        msk_time = candle.time.astimezone(msk)
        price = float(candle.close.units + candle.close.nano / 1e9)
        self.prices.append(price)
        if len(self.prices) > self.rsi_len + 1:
            self.prices.pop(0)
        order = None
        if len(self.prices) == self.rsi_len + 1:
            # Фильтр по волатильности: не торгуем, если диапазон слишком мал
            max_price = max(self.prices)
            min_price = min(self.prices)
            if (max_price - min_price) / price < self.min_range:
                if self.visualizer:
                    self.visualizer.add_candle(
                        msk_time,
                        float(candle.open.units + candle.open.nano / 1e9),
                        float(candle.high.units + candle.high.nano / 1e9),
                        float(candle.low.units + candle.low.nano / 1e9),
                        float(candle.close.units + candle.close.nano / 1e9)
                    )
                    self.visualizer.update_plot()
                return StrategyDecision(robot_trade_order=None)
            rsi = self._calc_rsi(self.prices)
            # Покупка по RSI < 25, если нет позиции
            if rsi < 25 and params.instrument_balance == 0:
                lot_price = price * self.instrument_info.lot
                lots_available = int(params.currency_balance / lot_price)
                if lots_available > 0:
                    order = RobotTradeOrder(quantity=min(self.trade_count, lots_available),
                                            direction=OrderDirection.ORDER_DIRECTION_BUY)
                    self.entry_price = price  # Запоминаем цену входа
                    if self.visualizer:
                        self.visualizer.add_buy(msk_time)
            # Продажа по RSI > 75, если есть позиция
            elif rsi > 75 and params.instrument_balance > 0:
                order = RobotTradeOrder(quantity=min(self.trade_count, params.instrument_balance),
                                        direction=OrderDirection.ORDER_DIRECTION_SELL)
                self.entry_price = None  # Сбросить цену входа
                if self.visualizer:
                    self.visualizer.add_sell(msk_time)
            # Take-profit/Stop-loss: если есть позиция и цена ушла достаточно далеко
            elif params.instrument_balance > 0 and self.entry_price is not None:
                price_change = (price - self.entry_price) / self.entry_price
                if price_change >= self.take_profit:
                    # Take-profit
                    order = RobotTradeOrder(quantity=min(self.trade_count, params.instrument_balance),
                                            direction=OrderDirection.ORDER_DIRECTION_SELL)
                    self.entry_price = None
                    if self.visualizer:
                        self.visualizer.add_sell(msk_time)
                elif price_change <= -self.stop_loss:
                    # Stop-loss
                    order = RobotTradeOrder(quantity=min(self.trade_count, params.instrument_balance),
                                            direction=OrderDirection.ORDER_DIRECTION_SELL)
                    self.entry_price = None
                    if self.visualizer:
                        self.visualizer.add_sell(msk_time)
        if self.visualizer:
            self.visualizer.add_candle(
                msk_time,
                float(candle.open.units + candle.open.nano / 1e9),
                float(candle.high.units + candle.high.nano / 1e9),
                float(candle.low.units + candle.low.nano / 1e9),
                float(candle.close.units + candle.close.nano / 1e9)
            )
            self.visualizer.update_plot()
        return StrategyDecision(robot_trade_order=order)


class RSIStrategy(TradeStrategyBase):
    request_candles: bool = True
    strategy_id: str = 'rsi'

    candle_subscription_interval: SubscriptionInterval = SubscriptionInterval.SUBSCRIPTION_INTERVAL_ONE_MINUTE
    order_book_subscription_depth = None
    trades_subscription = None

    def __init__(
        self,
        rsi_len: int = 14,
        trade_count: int = 1,
        min_range: float = 0.001,
        take_profit: float = 0.01,   # 1% профит
        stop_loss: float = 0.005,    # 0.5% убыток
        visualizer: Visualizer = None
    ):
        self.rsi_len = rsi_len
        self.trade_count = trade_count
        self.min_range = min_range  # минимальный диапазон для фильтрации "пилы"
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.visualizer = visualizer
        self.prices = []
        self.entry_price = None  # Цена входа для take-profit/stop-loss

    def load_candles(self, candles: list[HistoricCandle]) -> None:
        self.prices = [float(candle.close.units + candle.close.nano / 1e9) for candle in candles[-self.rsi_len-1:]]

    def decide(self, market_data: MarketDataResponse, params: TradeStrategyParams) -> StrategyDecision:
        return self.decide_by_candle(market_data.candle, params)

    def decide_by_candle(self, candle: Candle | HistoricCandle, params: TradeStrategyParams) -> StrategyDecision:
        import pytz
        msk = pytz.timezone('Europe/Moscow')
        msk_time = candle.time.astimezone(msk)
        price = float(candle.close.units + candle.close.nano / 1e9)
        self.prices.append(price)
        if len(self.prices) > self.rsi_len + 1:
            self.prices.pop(0)
        order = None
        if len(self.prices) == self.rsi_len + 1:
            # Фильтр по волатильности: не торгуем, если диапазон слишком мал
            max_price = max(self.prices)
            min_price = min(self.prices)
            if (max_price - min_price) / price < self.min_range:
                if self.visualizer:
                    self.visualizer.add_candle(
                        msk_time,
                        float(candle.open.units + candle.open.nano / 1e9),
                        float(candle.high.units + candle.high.nano / 1e9),
                        float(candle.low.units + candle.low.nano / 1e9),
                        float(candle.close.units + candle.close.nano / 1e9)
                    )
                    self.visualizer.update_plot()
                return StrategyDecision(robot_trade_order=None)
            rsi = self._calc_rsi(self.prices)
            # Покупка по RSI < 25, если нет позиции
            if rsi < 25 and params.instrument_balance == 0:
                lot_price = price * self.instrument_info.lot
                lots_available = int(params.currency_balance / lot_price)
                if lots_available > 0:
                    order = RobotTradeOrder(quantity=min(self.trade_count, lots_available),
                                            direction=OrderDirection.ORDER_DIRECTION_BUY)
                    self.entry_price = price  # Запоминаем цену входа
                    if self.visualizer:
                        self.visualizer.add_buy(msk_time)
            # Продажа по RSI > 75, если есть позиция
            elif rsi > 75 and params.instrument_balance > 0:
                order = RobotTradeOrder(quantity=min(self.trade_count, params.instrument_balance),
                                        direction=OrderDirection.ORDER_DIRECTION_SELL)
                self.entry_price = None  # Сбросить цену входа
                if self.visualizer:
                    self.visualizer.add_sell(msk_time)
            # Take-profit/Stop-loss: если есть позиция и цена ушла достаточно далеко
            elif params.instrument_balance > 0 and self.entry_price is not None:
                price_change = (price - self.entry_price) / self.entry_price
                if price_change >= self.take_profit:
                    # Take-profit
                    order = RobotTradeOrder(quantity=min(self.trade_count, params.instrument_balance),
                                            direction=OrderDirection.ORDER_DIRECTION_SELL)
                    self.entry_price = None
                    if self.visualizer:
                        self.visualizer.add_sell(msk_time)
                elif price_change <= -self.stop_loss:
                    # Stop-loss
                    order = RobotTradeOrder(quantity=min(self.trade_count, params.instrument_balance),
                                            direction=OrderDirection.ORDER_DIRECTION_SELL)
                    self.entry_price = None
                    if self.visualizer:
                        self.visualizer.add_sell(msk_time)
        if self.visualizer:
            self.visualizer.add_candle(
                msk_time,
                float(candle.open.units + candle.open.nano / 1e9),
                float(candle.high.units + candle.high.nano / 1e9),
                float(candle.low.units + candle.low.nano / 1e9),
                float(candle.close.units + candle.close.nano / 1e9)
            )
            self.visualizer.update_plot()
        return StrategyDecision(robot_trade_order=order)

    def _calc_rsi(self, prices: list[float]) -> float:
        gains = []
        losses = []
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i-1]
            if diff > 0:
                gains.append(diff)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(-diff)
        avg_gain = sum(gains[-self.rsi_len:]) / self.rsi_len
        avg_loss = sum(losses[-self.rsi_len:]) / self.rsi_len
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
