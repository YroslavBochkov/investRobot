import os
import threading
import warnings
from dotenv import load_dotenv

# Подавляем предупреждение protobuf (UserWarning: SymbolDatabase.GetPrototype() is deprecated...)
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=UserWarning, module="google.protobuf.symbol_database")

from robotlib.robot import TradingRobotFactory
from robotlib.strategy import RSIStrategy

# --- Список тикеров третьего эшелона, которые реально торгуются (исключены ROSB, LSNGP, BLNG, BSPBP, NMTP) ---
TICKERS_THIRD_TIER = [
    # ('SIBN', 'TQBR'),   # Газпром нефть
    ('MGNT', 'TQBR'),   # Магнит
    ('BANEP', 'TQBR'),  # Башнефть-преф
    ('KZOS', 'TQBR'),   # Казаньоргсинтез
    ('IRKT', 'TQBR'),   # Иркут
    ('GCHE', 'TQBR'),   # Черкизово
    ('ABRD', 'TQBR'),   # Абрау-Дюрсо
    ('OMZZP', 'TQBR'),  # Уралмаш-Ижора
    ('UKUZ', 'TQBR'),   # Южный Кузбасс
    ('GAZC', 'TQBR'),   # ГАЗКОН
    ('KOGK', 'TQBR'),   # Коршуновский ГОК
    ('SPBE', 'TQBR'),   # СПБ Биржа
    # ('GAZT', 'TQBR'),   # ГАЗ-Тек
    # ('GAZS', 'TQBR'),   # ГАЗ-сервис
    ('YAKG', 'TQBR'),   # ЯТЭК
]

# --- Оптимальные параметры для третьего эшелона (можно подбирать индивидуально) ---
THIRD_TIER_PARAMS = dict(
    rsi_len=14,         # Более короткий RSI — больше сигналов, но не слишком часто
    min_range=0.003,    # Более высокий фильтр волатильности (третьий эшелон часто "пилит")
    take_profit=0.025,  # Больше take-profit (волатильность выше)
    stop_loss=0.015,    # Больше stop-loss (чтобы не выбивало по шуму)
    trade_count=1       # Минимальный размер позиции (чтобы не попасть на "разводку")
)

load_dotenv()
token = os.environ.get('TINKOFF_TOKEN')
account_id = os.environ.get('TINKOFF_ACCOUNT')

stop_event = threading.Event()

def trade_for_ticker(ticker, class_code):
    print(f"Запуск торговли для {ticker}")
    from robotlib.stats import TradeStatisticsAnalyzer, BalanceProcessor
    stats_path = f'/Users/yaroslav/Петпроект/investRobot/stats_{ticker}.pickle'

    # --- Загружаем или создаём статистику ---
    try:
        stats = None
        if os.path.exists(stats_path):
            stats = TradeStatisticsAnalyzer.load_from_file(stats_path)
            print(f"Загружена существующая статистика для {ticker}")
        else:
            print(f"Файл статистики для {ticker} не найден, будет создан новый.")
    except Exception as e:
        print(f"❌ Не удалось загрузить stats_{ticker}.pickle: {e}")
        stats = None

    robot_factory = TradingRobotFactory(token=token, account_id=account_id, ticker=ticker, class_code=class_code, logger_level='INFO')
    strategy = RSIStrategy(
        rsi_len=THIRD_TIER_PARAMS['rsi_len'],
        trade_count=THIRD_TIER_PARAMS['trade_count'],
        min_range=THIRD_TIER_PARAMS['min_range'],
        take_profit=THIRD_TIER_PARAMS['take_profit'],
        stop_loss=THIRD_TIER_PARAMS['stop_loss'],
        trailing_stop=0.01,
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
    for ticker, class_code in TICKERS_THIRD_TIER:
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
    print("Торговля по всем тикерам третьего эшелона завершена.")

if __name__ == '__main__':
    main()
