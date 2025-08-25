import matplotlib.pyplot as plt
import matplotlib.dates as mdates

class Visualizer:
    def __init__(self, ticker, currency):
        self.ticker = ticker
        self.currency = currency
        self.fig, self.ax = plt.subplots()
        self.buys = []
        self.sells = []
        self.candles = []  # (time, open, high, low, close)
    
    def _init_fig(self):
        plt.close('all')  # Закрыть все старые окна, если они есть
        self.fig, self.ax = plt.subplots()
        plt.show(block=False)
        plt.pause(0.1)  # Дать matplotlib время на создание окна

    def add_candle(self, time, open_, high, low, close):
        self.candles.append((time, open_, high, low, close))
        # Оставляем только свечи за последние 30 минут
        import datetime
        thirty_min_ago = time - datetime.timedelta(minutes=30)
        self.candles = [c for c in self.candles if c[0] >= thirty_min_ago]
    
    def add_buy(self, time):
        self.buys.append(time)

    def add_sell(self, time):
        self.sells.append(time)

    def update_plot(self):
        # Проверяем, не было ли окно закрыто пользователем
        if not plt.fignum_exists(self.fig.number):
            self._init_fig()
        # Важно: всегда очищаем ось после пересоздания окна
        self.ax.clear()
        if not self.candles:
            plt.pause(0.2)
            return

        import matplotlib.patches as mpatches

        times = [c[0] for c in self.candles]
        opens = [c[1] for c in self.candles]
        highs = [c[2] for c in self.candles]
        lows = [c[3] for c in self.candles]
        closes = [c[4] for c in self.candles]

        width = 0.0005  # ширина свечи (в днях, для matplotlib)
        for i, (t, o, h, l, c) in enumerate(self.candles):
            color = 'green' if c >= o else 'red'
            # Тень (high-low)
            self.ax.plot([t, t], [l, h], color='black', linewidth=1, zorder=1)
            # Тело свечи
            rect = mpatches.Rectangle(
                (mdates.date2num(t) - width/2, min(o, c)),
                width,
                abs(c - o),
                facecolor=color,
                edgecolor='black',
                zorder=2
            )
            self.ax.add_patch(rect)

        if times:
            minx = min(times)
            buys = [buy for buy in self.buys if buy >= minx]
            sells = [sell for sell in self.sells if sell >= minx]

            self.ax.set_title(self.ticker)
            self.ax.set_xlabel('Время (МСК)')
            self.ax.set_ylabel(f'Цена ({self.currency})')
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

            if lows and highs:
                self.ax.vlines(buys, ymin=min(lows), ymax=max(highs), color='g', linestyle='dashed')
                self.ax.vlines(sells, ymin=min(lows), ymax=max(highs), color='r', linestyle='dashed')
            self.fig.autofmt_xdate()
        plt.draw()
        plt.pause(0.2)
