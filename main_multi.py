import os
import threading
from dotenv import load_dotenv

from robotlib.robot import TradingRobotFactory
from robotlib.strategy import RSIStrategy

load_dotenv()
token = os.environ.get('TINKOFF_TOKEN')
account_id = os.environ.get('TINKOFF_ACCOUNT')

stop_event = threading.Event()

# Для минимизации влияния комиссии:
# 1. take_profit должен быть существенно больше двойной комиссии (обычно 0.001-0.002 для дешёвых бумаг, 0.01-0.02 для дорогих)
# 2. min_range чуть выше, чтобы не ловить "пилу"
# 3. stop_loss чуть больше, чтобы не выбивало по шуму

TICKER_PARAMS = {
    'MTSS':  dict(rsi_len=21, min_range=0.001,  take_profit=0.01,  stop_loss=0.007,  trade_count=2),
    'MOEX':  dict(rsi_len=21, min_range=0.0015, take_profit=0.015, stop_loss=0.009,  trade_count=2),
    'VKCO':  dict(rsi_len=14, min_range=0.0015, take_profit=0.025, stop_loss=0.012,  trade_count=2),
    'OZON':  dict(rsi_len=14, min_range=0.0015, take_profit=0.03,  stop_loss=0.015,  trade_count=2),
    'SBER':  dict(rsi_len=21, min_range=0.0012, take_profit=0.012, stop_loss=0.007,  trade_count=5),
    'GAZP':  dict(rsi_len=21, min_range=0.0012, take_profit=0.012, stop_loss=0.007,  trade_count=3),
    'LKOH':  dict(rsi_len=14, min_range=0.0015, take_profit=0.018, stop_loss=0.009,  trade_count=1),
    'GMKN':  dict(rsi_len=14, min_range=0.0018, take_profit=0.02,  stop_loss=0.01,   trade_count=1),
    'NVTK':  dict(rsi_len=14, min_range=0.0015, take_profit=0.015, stop_loss=0.008,  trade_count=2),
    'PLZL':  dict(rsi_len=14, min_range=0.0018, take_profit=0.018, stop_loss=0.009,  trade_count=1),
    'ROSN':  dict(rsi_len=14, min_range=0.0015, take_profit=0.014, stop_loss=0.007,  trade_count=2),
    'TATN':  dict(rsi_len=14, min_range=0.0015, take_profit=0.013, stop_loss=0.007,  trade_count=2),
    'CHMF':  dict(rsi_len=14, min_range=0.0015, take_profit=0.015, stop_loss=0.008,  trade_count=2),
}

TICKERS = [
    ('MTSS', 'TQBR'),
    ('MOEX', 'TQBR'),
    ('VKCO', 'TQBR'),
    ('OZON', 'TQBR'),
    ('SBER', 'TQBR'),
    ('GAZP', 'TQBR'),
    ('LKOH', 'TQBR'),
    ('GMKN', 'TQBR'),
    ('NVTK', 'TQBR'),
    ('PLZL', 'TQBR'),
    ('ROSN', 'TQBR'),
    ('TATN', 'TQBR'),
    ('CHMF', 'TQBR'),
]

def trade_for_ticker(ticker, class_code):
    print(f"Запуск торговли для {ticker}")
    params = TICKER_PARAMS.get(ticker, dict(rsi_len=14, min_range=0.001, take_profit=0.015, stop_loss=0.008, trade_count=2))
    from robotlib.stats import TradeStatisticsAnalyzer, BalanceProcessor
    stats_path = f'/Users/yaroslav/Петпроект/investRobot/stats_{ticker}.pickle'

    # --- Загружаем или создаём статистику ---
    try:
        stats = TradeStatisticsAnalyzer.load_from_file(stats_path)
        print(f"Загружена существующая статистика для {ticker}")
    except Exception as e:
        print(f"❌ Не удалось загрузить stats_{ticker}.pickle: {e}")
        import traceback
        traceback.print_exc()
        stats = None

    # --- Если статистика была утеряна, но на счету есть купленные лоты, добавляем их вручную ---
    if stats is None:
        print(f"‼️  ВАЖНО: Файл stats_{ticker}.pickle не найден или не читается.")
        print(f"Проверьте, что он создан корректно и не повреждён.")
        print(f"Если вы создавали файл через add_manual_trades.py, убедитесь, что:")
        print(f"  - В файле есть хотя бы одна покупка (OrderState с direction=BUY)")
        print(f"  - Количество лотов и цена совпадают с вашими реальными позициями")
        print(f"  - figi в файле совпадает с figi инструмента ({ticker})")
        print(f"  - Файл не пустой и не повреждён")
        print(f"Попробуйте открыть файл stats_{ticker}.pickle через TradeStatisticsAnalyzer.load_from_file в отдельном скрипте и вывести .trades")
        print(f"Если ошибка повторяется — пересоздайте файл через add_manual_trades.py")
        print(f"Робот не будет спрашивать цену входа, если файл корректный!")

    robot_factory = TradingRobotFactory(token=token, account_id=account_id, ticker=ticker, class_code=class_code, logger_level='INFO')
    strategy = RSIStrategy(
        rsi_len=params['rsi_len'],
        trade_count=params['trade_count'],
        min_range=params['min_range'],
        take_profit=params['take_profit'],
        stop_loss=params['stop_loss'],
        trailing_stop=0.01,  # trailing stop 1%
        # visualizer=Visualizer(ticker, 'RUB')
    )

    # Восстанавливаем entry_price, если есть открытая позиция
    entry_price = None
    if stats is not None:
        short, full = stats.get_report(processors=[BalanceProcessor()])
        if not full.empty and 'instrument_balance' in full.columns and full['instrument_balance'].iloc[-1] > 0:
            last_row = full[full['instrument_balance'] > 0].iloc[-1]
            entry_price = last_row['average_position_price']
    if entry_price is not None:
        strategy.entry_price = entry_price

    # --- Передаём существующую статистику в робота, если есть ---
    robot = robot_factory.create_robot(strategy, sandbox_mode=False)
    if stats is not None:
        robot.trade_statistics = stats

    try:
        # Передаем stop_event в стратегию/робота, чтобы они могли корректно завершить торговый цикл
        stats = robot.trade(stop_event=stop_event)
        if stats is None:
            stats = robot.trade_statistics
    except KeyboardInterrupt:
        print(f"\nОстановка торговли по {ticker} по Ctrl+C. Сохраняем статистику...")
        stats = robot.trade_statistics  # Получаем статистику на момент остановки
    finally:
        try:
            if stats is not None:
                stats.save_to_file(stats_path)
                print(f"Файл статистики торговли сохранён: {stats_path}")
            else:
                print(f"Нет статистики для сохранения по {ticker}!")
        except Exception as e:
            print(f"Ошибка при сохранении статистики: {e}")
    print(f"Торговля по {ticker} завершена. Файл статистики: stats_{ticker}.pickle")

def main():
    threads = []
    for ticker, class_code in TICKERS:
        t = threading.Thread(target=trade_for_ticker, args=(ticker, class_code))
        t.start()
        threads.append(t)
    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("\nОстановка всех торговых потоков по Ctrl+C. Ждём завершения и сохранения статистики...")
        stop_event.set()
        for t in threads:
            t.join()
    print("Торговля по всем тикерам завершена.")

if __name__ == '__main__':
    main()
