from robotlib.stats import BalanceProcessor, BalanceCalculator, TradeStatisticsAnalyzer


def print_stats(stats_path, label):
    try:
        stats = TradeStatisticsAnalyzer.load_from_file(stats_path)
    except FileNotFoundError:
        print(f"Файл статистики не найден: {stats_path}")
        print("Сначала запустите робота для генерации статистики.")
        return

    short, full = stats.get_report(processors=[BalanceProcessor()], calculators=[BalanceCalculator()])

    print(f"\n=== {label} ===")
    print(full)
    print(short)

    income = short.get("income", 0)
    commission = short.get("total_commission", 0)
    if income > 0:
        print(f"\n✅ ВЫ ЗАРАБОТАЛИ (с учётом комиссии): {income:.2f} руб.")
    elif income < 0:
        print(f"\n❌ ВЫ ПОТЕРЯЛИ (с учётом комиссии): {abs(income):.2f} руб.")
    else:
        print("\nℹ️  Доходность стратегии за период: 0 руб.")
    print(f"💸 Всего потрачено на комиссию: {commission:.2f} руб.")

def main():
    print_stats('/Users/yaroslav/Петпроект/investRobot/stats.pickle', 'SBER')
    print_stats('/Users/yaroslav/Петпроект/investRobot/stats_tcsg.pickle', 'Тинькофф Инвестиции (T)')


if __name__ == '__main__':
    main()
