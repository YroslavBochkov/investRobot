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
    tickers = [
        ('MTSS', 'МТС'),
        ('MOEX', 'Мосбиржа'),
        ('VKCO', 'ВКонтакте'),
        ('OZON', 'Озон'),
        ('SBER', 'Сбербанк'),
        ('GAZP', 'Газпром'),
        ('LKOH', 'Лукойл'),
        ('GMKN', 'Норникель'),
        ('NVTK', 'Новатэк'),
        ('PLZL', 'Полюс'),
        ('ROSN', 'Роснефть'),
        ('TATN', 'Татнефть'),
        ('CHMF', 'Северсталь'),
    ]
    open_positions = []
    for ticker, label in tickers:
        stats_path = f'/Users/yaroslav/Петпроект/investRobot/stats_{ticker}.pickle'
        try:
            from robotlib.stats import TradeStatisticsAnalyzer, BalanceProcessor, BalanceCalculator
            stats = TradeStatisticsAnalyzer.load_from_file(stats_path)
            short, _ = stats.get_report(processors=[BalanceProcessor()], calculators=[BalanceCalculator()])
            if short.get('final_instrument_balance', 0) > 0:
                open_positions.append((label, short['final_instrument_balance']))
        except Exception:
            continue

    print("Открытые позиции:")
    if open_positions:
        for label, lots in open_positions:
            print(f"- {label}: {lots} лот(ов)")
    else:
        print("Нет открытых позиций.")

    # Старый вывод полной статистики
    for ticker, label in tickers:
        print_stats(f'/Users/yaroslav/Петпроект/investRobot/stats_{ticker}.pickle', label)

if __name__ == '__main__':
    main()
