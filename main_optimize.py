import datetime
import os
from dotenv import load_dotenv

from robotlib.robot import TradingRobotFactory
from robotlib.strategy import TradeStrategyParams, RSIStrategy
from robotlib.stats import BalanceProcessor, BalanceCalculator

load_dotenv()
token = os.environ.get('TINKOFF_TOKEN_TEST', os.environ.get('TINKOFF_TOKEN'))
account_id = os.environ.get('TINKOFF_ACCOUNT_TEST', os.environ.get('TINKOFF_ACCOUNT'))

def test_rsi_for_ticker(ticker, label):
    robot_factory = TradingRobotFactory(token=token, account_id=account_id, ticker=ticker, class_code='TQBR', logger_level='ERROR')
    best_income = float('-inf')
    best_params = None

    for rsi_len in [14, 21, 28]:
        for min_range in [0.001, 0.002]:
            for take_profit in [0.007, 0.01]:
                for stop_loss in [0.003, 0.005]:
                    strategy = RSIStrategy(
                        rsi_len=rsi_len,
                        trade_count=1,
                        min_range=min_range,
                        take_profit=take_profit,
                        stop_loss=stop_loss
                    )
                    robot = robot_factory.create_robot(strategy, sandbox_mode=True)
                    stats = robot.backtest(
                        TradeStrategyParams(instrument_balance=0, currency_balance=15000, pending_orders=[]),
                        train_duration=datetime.timedelta(days=1), test_duration=datetime.timedelta(days=5)
                    )
                    short, _ = stats.get_report(processors=[BalanceProcessor()], calculators=[BalanceCalculator()])
                    income = short['income']
                    print(f"{label}: RSI={rsi_len}, min_range={min_range}, TP={take_profit}, SL={stop_loss} => income={income:.2f}")
                    if income > best_income:
                        best_income = income
                        best_params = (rsi_len, min_range, take_profit, stop_loss)

    print(f"\nЛучшие параметры для {label}:")
    print(f"RSI={best_params[0]}, min_range={best_params[1]}, TP={best_params[2]}, SL={best_params[3]} => income={best_income:.2f}")

def main():
    test_rsi_for_ticker('SBER', 'SBER')
    test_rsi_for_ticker('T', 'Тинькофф Инвестиции (T)')

if __name__ == '__main__':
    main()