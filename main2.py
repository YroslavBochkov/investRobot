import datetime
import os
from dotenv import load_dotenv

from robotlib.robot import TradingRobotFactory
from robotlib.strategy import RSIStrategy
from robotlib.vizualization import Visualizer

load_dotenv()
token = os.environ.get('TINKOFF_TOKEN')
account_id = os.environ.get('TINKOFF_ACCOUNT')

print("TOKEN:", token)
print("ACCOUNT_ID:", account_id)

def trade(robot):
    try:
        stats = robot.trade()
    except KeyboardInterrupt:
        print("\nОстановка по Ctrl+C. Сохраняем статистику...")
        stats = robot.trade_statistics  # Получаем статистику на момент остановки
    stats.save_to_file('/Users/yaroslav/Петпроект/investRobot/stats_tcsg.pickle')
    print("Файл статистики торговли сохранён:", '/Users/yaroslav/Петпроект/investRobot/stats_tcsg.pickle')

def main():
    from robotlib.stats import TradeStatisticsAnalyzer

    stats_path = '/Users/yaroslav/Петпроект/investRobot/stats_tcsg.pickle'
    entry_price = None

    # Получаем текущий баланс и позицию
    robot_factory = TradingRobotFactory(token=token, account_id=account_id, ticker='T', class_code='TQBR',
                                        logger_level='INFO')
    # Пробуем загрузить статистику и найти цену последней покупки, если есть позиция
    try:
        stats = TradeStatisticsAnalyzer.load_from_file(stats_path)
        short, full = stats.get_report()
        # Если есть позиция, ищем последнюю покупку
        if not full.empty and full['instrument_balance'].iloc[-1] > 0:
            # Берём цену последней покупки (average_position_price)
            last_buy = full[full['direction'] == 1].iloc[-1]
            entry_price = last_buy['average_position_price']
    except Exception:
        pass

    strategy = RSIStrategy(
        rsi_len=21,              # Более короткий RSI для чуть более частых, но не слишком частых сигналов
        trade_count=2,           # Можно увеличить, если хватает баланса
        min_range=0.0015,        # Оставить не слишком маленьким, чтобы не ловить "пилу"
        take_profit=0.012,       # Чуть больше профит, чтобы сделки были реже и прибыльнее
        stop_loss=0.006,         # Чуть больше стоп-лосс, чтобы не выбивало по шуму
        # visualizer=Visualizer('T', 'RUB')
    )
    if entry_price is not None:
        strategy.entry_price = entry_price

    robot = robot_factory.create_robot(
        strategy,
        sandbox_mode=False  # Боевой режим!
    )
    trade(robot)
    print("Торговля завершена. Файл статистики сохранён.")
    print("Теперь можно запускать main_stats.py для анализа.")

if __name__ == '__main__':
    main()
