import datetime
import os
from dotenv import load_dotenv

from robotlib.robot import TradingRobotFactory
from robotlib.strategy import TradeStrategyParams, MAEStrategy, BreakoutStrategy, RSIStrategy
from robotlib.vizualization import Visualizer

load_dotenv()
token = os.environ.get('TINKOFF_TOKEN')
account_id = os.environ.get('TINKOFF_ACCOUNT')

print("TOKEN:", token)
print("ACCOUNT_ID:", account_id)


def backtest(robot):
    stats = robot.backtest(
        TradeStrategyParams(instrument_balance=0, currency_balance=5000, pending_orders=[]),
        train_duration=datetime.timedelta(days=1), test_duration=datetime.timedelta(days=20))
    print(f"Совершено сделок: {len(stats.trades)}")
    stats.save_to_file('/Users/yaroslav/Петпроект/investRobot/backtest_stats.pickle')
    print("Файл статистики бэктеста сохранён:", '/Users/yaroslav/Петпроект/investRobot/backtest_stats.pickle')

def trade(robot):
    try:
        stats = robot.trade()
    except KeyboardInterrupt:
        print("\nОстановка по Ctrl+C. Сохраняем статистику...")
        stats = robot.trade_statistics  # Получаем статистику на момент остановки
    stats.save_to_file('/Users/yaroslav/Петпроект/investRobot/stats.pickle')
    print("Файл статистики торговли сохранён:", '/Users/yaroslav/Петпроект/investRobot/stats.pickle')

def main():
    from robotlib.stats import TradeStatisticsAnalyzer

    stats_path = '/Users/yaroslav/Петпроект/investRobot/stats.pickle'
    entry_price = None

    robot_factory = TradingRobotFactory(token=token, account_id=account_id, ticker='SBER', class_code='TQBR',
                                        logger_level='INFO')
    # Пробуем загрузить статистику и найти цену последней покупки, если есть позиция
    try:
        stats = TradeStatisticsAnalyzer.load_from_file(stats_path)
        short, full = stats.get_report()
        # Если есть позиция, ищем последнюю покупку
        if not full.empty and full['instrument_balance'].iloc[-1] > 0:
            last_buy = full[full['direction'] == 1].iloc[-1]
            entry_price = last_buy['average_position_price']
    except Exception:
        pass

    strategy = RSIStrategy(
        rsi_len=21,              # Оптимальный период RSI для минутных свечей
        trade_count=5,           # 5 лотов за сделку, если хватает баланса
        min_range=0.0015,        # Фильтр по волатильности, чтобы не ловить "пилу"
        take_profit=0.01,        # 1% профит — сделки реже, но прибыльнее
        stop_loss=0.006,         # 0.6% стоп-лосс — не выбивает по шуму
        # visualizer=Visualizer('SBER', 'RUB')
    )
    if entry_price is not None:
        strategy.entry_price = entry_price

    robot = robot_factory.create_robot(
        strategy,
        sandbox_mode=False  # ВАЖНО: ставим False для боевого режима!
    )
    # Запускаем торговлю на реальном счёте
    trade(robot)
    print("Торговля завершена. Файл статистики сохранён.")
    print("Теперь можно запускать main_stats.py для анализа.")

    # backtest(robot)  # Не запускаем одновременно!

if __name__ == '__main__':
    main()
