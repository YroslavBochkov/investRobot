import os
import datetime
import uuid
import logging
from dotenv import load_dotenv

from robotlib.stats import TradeStatisticsAnalyzer
from tinkoff.invest import OrderState, OrderDirection, OrderExecutionReportStatus, MoneyValue, OrderType

from robotlib.robot import TradingRobotFactory

# === ИНСТРУКЦИЯ ===
# 1. Заполни список manual_trades своими реальными позициями (тикер, цена, количество, валюта, figi).
#    figi можно узнать через taccount.py или get_real_accounts.py, либо в терминале Тинькофф.
# 2. Запусти этот скрипт: python add_manual_trades.py
# 3. После этого файл stats_<тикер>.pickle появится, и робот будет видеть эти бумаги как купленные.

load_dotenv()
token = os.environ.get('TINKOFF_TOKEN')
account_id = os.environ.get('TINKOFF_ACCOUNT')

manual_trades = [
    # (тикер, цена, количество, валюта, figi)
    ("VKCO", 332.6, 2, "RUB", "BBG00Y91R9T3"),
    ("GAZP", 133.21, 3, "RUB", "BBG004S68507"),
    ("MOEX", 177.37, 2, "RUB", "BBG004730RP0"),
    ("NVTK", 1237.6, 2, "RUB", "BBG00475KKY8"),
    ("CHMF", 1073.4, 2, "RUB", "BBG004S683W7"),
    ("TATN", 659.8, 2, "RUB", "BBG004S68507"),
    ("OZON", 4331.5, 1, "RUB", "BBG00QPYJ5H0"),
]

for ticker, price, lots, currency, figi in manual_trades:
    stats_path = f'/Users/yaroslav/Петпроект/investRobot/stats_{ticker}.pickle'
    try:
        # Получаем корректный Instrument через TradingRobotFactory (без DummyInstrument)
        robot_factory = TradingRobotFactory(
            token=token,
            account_id=account_id,
            figi=figi,
            ticker=ticker,
            class_code="TQBR",
            logger_level='WARNING'
        )
        instrument = robot_factory.instrument_info
    except Exception as e:
        print(f"Ошибка получения инструмента для {ticker} ({figi}): {e}")
        continue

    stats = TradeStatisticsAnalyzer(
        positions=lots,
        money=0.0,
        instrument_info=instrument,
        logger=logging.getLogger(f"manual_stats.{ticker}")
    )

    order_id = str(uuid.uuid4())
    now = datetime.datetime.now()
    price_money = MoneyValue(currency, int(price), int((price - int(price)) * 1e9))
    stats.add_trade(OrderState(
        order_id=order_id,
        execution_report_status=OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL,
        lots_requested=lots,
        lots_executed=lots,
        initial_order_price=price_money,
        executed_order_price=price_money,
        total_order_amount=price_money,
        average_position_price=price_money,
        initial_commission=MoneyValue(currency, 0, 0),
        executed_commission=MoneyValue(currency, 0, 0),
        figi=figi,
        direction=OrderDirection.ORDER_DIRECTION_BUY,
        initial_security_price=price_money,
        stages=[],
        service_commission=MoneyValue(currency, 0, 0),
        currency=price_money.currency,
        order_type=OrderType.ORDER_TYPE_MARKET,
        order_date=now
    ))
    stats.save_to_file(stats_path)
    print(f"Добавлена покупка: {ticker} — {lots} лотов по {price}")

    # Проверка: выводим все сделки в файле после добавления
    try:
        loaded = TradeStatisticsAnalyzer.load_from_file(stats_path)
        print(f"Проверка: сделки в stats_{ticker}.pickle:")
        for trade in loaded.trades.values():
            print(f"  {trade.figi} {trade.lots_executed} лотов по {trade.executed_order_price.units + trade.executed_order_price.nano / 1e9}")
    except Exception as e:
        print(f"Ошибка проверки файла stats_{ticker}.pickle: {e}")

print("Готово! Теперь робот будет видеть эти сделки в статистике.")