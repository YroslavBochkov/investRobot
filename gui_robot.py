# Графическая оболочка для запуска робота с мультиторговлей, ручным добавлением тикеров, параметрами и пояснениями
import sys
import threading
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QVBoxLayout, QHBoxLayout, QWidget, QSpinBox, QDoubleSpinBox, QTextEdit, QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt

from robotlib.robot import TradingRobotFactory
from robotlib.strategy import RSIStrategy
from robotlib.vizualization import Visualizer

# --- Параметры по умолчанию из мультистратегии ---
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
    'YDEX':  dict(rsi_len=14, min_range=0.0018, take_profit=0.02,  stop_loss=0.01,   trade_count=1),
}

# --- Получение тикеров с Мосбиржи через Tinkoff Invest API ---
def get_moex_tickers(token):
    from tinkoff.invest import Client
    tickers = []
    with Client(token) as client:
        shares = client.instruments.shares().instruments
        for share in shares:
            # Фильтруем только акции основного рынка Мосбиржи по class_code
            if getattr(share, "class_code", None) == "TQBR":
                tickers.append((share.ticker, share.class_code))
    return sorted(set(tickers))

class MultiRobotThread(QtCore.QThread):
    log_signal = QtCore.pyqtSignal(str)
    finished_signal = QtCore.pyqtSignal(str)

    def __init__(self, token, account_id, tickers_params):
        super().__init__()
        self.token = token
        self.account_id = account_id
        self.tickers_params = tickers_params  # список кортежей: (ticker, class_code, rsi_len, min_range, take_profit, stop_loss, trade_count)

    def run(self):
        threads = []
        def run_one(ticker, class_code, rsi_len, min_range, take_profit, stop_loss, trade_count):
            try:
                self.log_signal.emit(f"Запуск торговли для {ticker}")
                visualizer = Visualizer(ticker, 'RUB')
                robot_factory = TradingRobotFactory(
                    token=self.token,
                    account_id=self.account_id,
                    ticker=ticker,
                    class_code=class_code,
                    logger_level='INFO'
                )
                strategy = RSIStrategy(
                    rsi_len=rsi_len,
                    trade_count=trade_count,
                    min_range=min_range,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                    visualizer=visualizer
                )
                robot = robot_factory.create_robot(strategy, sandbox_mode=False)
                stats = robot.trade()
                stats.save_to_file(f'stats_{ticker}.pickle')
                self.log_signal.emit(f"Торговля по {ticker} завершена. Файл статистики: stats_{ticker}.pickle")
            except Exception as e:
                self.log_signal.emit(f"Ошибка по {ticker}: {e}")

        for params in self.tickers_params:
            t = threading.Thread(target=run_one, args=params)
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        self.finished_signal.emit("Торговля по выбранным тикерам завершена.")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tinkoff Invest Robot")
        self.setGeometry(200, 200, 800, 600)

        # --- UI элементы ---
        self.token_label = QLabel("Токен:")
        self.token_label.setToolTip("Ваш персональный API-токен Тинькофф Инвестиций. Получить можно на сайте Тинькофф.")
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.Password)
        self.token_input.setToolTip("Вставьте сюда ваш API-токен Тинькофф Инвестиций.")
        self.token_help_btn = QPushButton("Как получить токен?")
        self.token_help_btn.setToolTip("Пошаговая инструкция по получению токена на сайте Тинькофф.")
        self.token_help_btn.clicked.connect(self.show_token_help)

        self.account_label = QLabel("Account ID:")
        self.account_label.setToolTip("ID вашего брокерского счёта. Можно получить автоматически.")
        self.account_input = QLineEdit()
        self.account_input.setToolTip("Вставьте сюда ID счёта или нажмите 'Получить аккаунты'.")
        self.account_btn = QPushButton("Получить аккаунты")
        self.account_btn.setToolTip("Получить список ваших счетов по введённому токену.")
        self.account_btn.clicked.connect(self.get_accounts)

        self.ticker_label = QLabel("Тикеры для торговли:")
        self.ticker_label.setToolTip("Выберите один или несколько тикеров для мультиторговли.")
        self.ticker_list = QListWidget()
        self.ticker_list.setSelectionMode(QListWidget.MultiSelection)
        self.ticker_list.setToolTip(
            "Список тикеров Мосбиржи. Можно выбрать несколько для одновременной торговли.\n"
            "Если тикеры не подгружаются, вы можете добавить свой тикер вручную:\n"
            "1. Кликните правой кнопкой мыши по списку и выберите 'Добавить тикер'.\n"
            "2. Введите тикер (например, SBER) и нажмите OK."
        )
        self.ticker_btn = QPushButton("Обновить тикеры")
        self.ticker_btn.setToolTip("Загрузить актуальный список тикеров с Мосбиржи по вашему токену.")
        self.ticker_btn.clicked.connect(self.update_tickers)

        # --- Контекстное меню для ручного добавления тикера ---
        self.ticker_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ticker_list.customContextMenuRequested.connect(self.show_ticker_context_menu)

        # --- Группа параметров стратегии ---
        params_group = QGroupBox("Параметры стратегии (для каждого тикера)")
        params_group.setToolTip("Параметры применяются к каждому выбранному тикеру. Для предустановленных тикеров значения подставляются автоматически.")
        params_layout = QVBoxLayout()

        self.rsi_label = QLabel("RSI период:")
        self.rsi_label.setToolTip("Период RSI-индикатора. Чем больше, тем реже сигналы.")
        self.rsi_spin = QSpinBox()
        self.rsi_spin.setRange(2, 50)
        self.rsi_spin.setValue(14)
        self.rsi_spin.setToolTip("Период RSI-индикатора (обычно 14-21).")

        self.min_range_label = QLabel("min_range:")
        self.min_range_label.setToolTip("Минимальный диапазон изменения цены для фильтрации 'пилы'.")
        self.min_range_spin = QDoubleSpinBox()
        self.min_range_spin.setDecimals(4)
        self.min_range_spin.setSingleStep(0.0001)
        self.min_range_spin.setRange(0.0001, 0.01)
        self.min_range_spin.setValue(0.0015)
        self.min_range_spin.setToolTip("Фильтр волатильности: сделки только если диапазон больше этого значения.")

        self.tp_label = QLabel("Take-profit (%):")
        self.tp_label.setToolTip("Процент прибыли, при котором позиция будет закрыта с прибылью.")
        self.tp_spin = QDoubleSpinBox()
        self.tp_spin.setDecimals(3)
        self.tp_spin.setSingleStep(0.001)
        self.tp_spin.setRange(0.001, 0.1)
        self.tp_spin.setValue(0.015)
        self.tp_spin.setToolTip("Take-profit: на сколько процентов должна вырасти цена для продажи.")

        self.sl_label = QLabel("Stop-loss (%):")
        self.sl_label.setToolTip("Процент убытка, при котором позиция будет закрыта с убытком.")
        self.sl_spin = QDoubleSpinBox()
        self.sl_spin.setDecimals(3)
        self.sl_spin.setSingleStep(0.001)
        self.sl_spin.setRange(0.001, 0.1)
        self.sl_spin.setValue(0.008)
        self.sl_spin.setToolTip("Stop-loss: на сколько процентов должна упасть цена для продажи.")

        self.trade_count_label = QLabel("Лотов за сделку:")
        self.trade_count_label.setToolTip("Сколько лотов покупать/продавать за одну сделку.")
        self.trade_count_spin = QSpinBox()
        self.trade_count_spin.setRange(1, 100)
        self.trade_count_spin.setValue(2)
        self.trade_count_spin.setToolTip("Количество лотов в одной сделке.")

        params_layout.addWidget(self.rsi_label)
        params_layout.addWidget(self.rsi_spin)
        params_layout.addWidget(self.min_range_label)
        params_layout.addWidget(self.min_range_spin)
        params_layout.addWidget(self.tp_label)
        params_layout.addWidget(self.tp_spin)
        params_layout.addWidget(self.sl_label)
        params_layout.addWidget(self.sl_spin)
        params_layout.addWidget(self.trade_count_label)
        params_layout.addWidget(self.trade_count_spin)
        params_group.setLayout(params_layout)

        self.start_btn = QPushButton("Запустить мультиторговлю")
        self.start_btn.setToolTip("Запустить торговлю по выбранным тикерам и параметрам.")
        self.start_btn.clicked.connect(self.start_multi_robot)
        self.stop_btn = QPushButton("Остановить")
        self.stop_btn.setToolTip("Остановить торговлю (если поддерживается).")
        self.stop_btn.setEnabled(False)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setToolTip("Здесь отображается ход работы робота и все сообщения.")

        # --- Layout ---
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.token_label)
        main_layout.addWidget(self.token_input)
        main_layout.addWidget(self.token_help_btn)
        main_layout.addWidget(self.account_label)
        main_layout.addWidget(self.account_input)
        main_layout.addWidget(self.account_btn)
        main_layout.addWidget(self.ticker_label)
        main_layout.addWidget(self.ticker_list)
        main_layout.addWidget(self.ticker_btn)
        main_layout.addWidget(params_group)
        main_layout.addWidget(self.start_btn)
        main_layout.addWidget(self.stop_btn)
        main_layout.addWidget(self.log)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.robot_thread = None

        # Автоматически подставлять параметры при выборе тикера
        self.ticker_list.itemSelectionChanged.connect(self.set_params_for_selected_ticker)

    def show_token_help(self):
        QMessageBox.information(self, "Как получить токен",
            "1. Перейдите на https://www.tinkoff.ru/invest/settings/\n"
            "2. В разделе 'API токены' нажмите 'Создать токен'.\n"
            "3. Скопируйте токен и вставьте его в это поле.\n"
            "4. Account ID можно получить автоматически.")

    def get_accounts(self):
        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "Ошибка", "Введите токен!")
            return
        try:
            from tinkoff.invest import Client
            with Client(token) as client:
                accounts = client.users.get_accounts().accounts
                if not accounts:
                    QMessageBox.warning(self, "Ошибка", "Нет доступных аккаунтов.")
                    return
                accs = [f"{acc.id} ({acc.type})" for acc in accounts]
                self.account_input.setText(accounts[0].id)
                QMessageBox.information(self, "Аккаунты", "\n".join(accs))
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось получить аккаунты: {e}")

    def update_tickers(self):
        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "Ошибка", "Введите токен!")
            return
        self.ticker_list.clear()
        self.ticker_list.addItem("Загрузка...")
        QtWidgets.QApplication.processEvents()
        try:
            tickers = get_moex_tickers(token)
            self.ticker_list.clear()
            # Сначала добавим тикеры из мультистратегии (с параметрами)
            for ticker in TICKER_PARAMS:
                item = QListWidgetItem(f"{ticker} (TQBR)")
                item.setToolTip("Предустановленный тикер с оптимальными параметрами и стратегией.")
                self.ticker_list.addItem(item)
            # Затем добавим остальные тикеры MOEX (без дублей)
            for ticker, class_code in tickers:
                if ticker not in TICKER_PARAMS:
                    item = QListWidgetItem(f"{ticker} ({class_code})")
                    item.setToolTip("Тикер Мосбиржи. Параметры можно задать вручную.")
                    self.ticker_list.addItem(item)
        except Exception as e:
            self.ticker_list.clear()
            self.ticker_list.addItem("Ошибка загрузки")
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось получить тикеры: {e}\n\n"
                "Если тикеры не подгружаются, вы можете добавить свой тикер вручную через правый клик по списку.\n"
                "Тикеры из мультистратегии всегда доступны для выбора!"
            )

    def show_ticker_context_menu(self, pos):
        menu = QtWidgets.QMenu()
        add_action = menu.addAction("Добавить тикер")
        action = menu.exec_(self.ticker_list.mapToGlobal(pos))
        if action == add_action:
            text, ok = QtWidgets.QInputDialog.getText(
                self, "Добавить тикер", "Введите тикер (например, SBER):"
            )
            if ok and text.strip():
                item = QListWidgetItem(f"{text.strip().upper()} (TQBR)")
                item.setToolTip("Пользовательский тикер. Параметры задайте вручную.")
                self.ticker_list.addItem(item)


    def set_params_for_selected_ticker(self):
        # Если выбран ровно один тикер из мультистратегии — подставить параметры
        selected = self.ticker_list.selectedItems()
        if len(selected) == 1:
            ticker_str = selected[0].text().strip()
            if "(" in ticker_str and ")" in ticker_str:
                ticker, _ = ticker_str.split(" (")
            else:
                ticker = ticker_str
            params = TICKER_PARAMS.get(ticker)
            if params:
                self.rsi_spin.setValue(params['rsi_len'])
                self.min_range_spin.setValue(params['min_range'])
                self.tp_spin.setValue(params['take_profit'])
                self.sl_spin.setValue(params['stop_loss'])
                self.trade_count_spin.setValue(params['trade_count'])
                self.log.append(f"Параметры для {ticker} подставлены автоматически из мультистратегии.")
            else:
                # Значения по умолчанию
                self.rsi_spin.setValue(14)
                self.min_range_spin.setValue(0.0015)
                self.tp_spin.setValue(0.015)
                self.sl_spin.setValue(0.008)
                self.trade_count_spin.setValue(2)
                self.log.append(f"Для {ticker} параметры выставлены по умолчанию. Измените их вручную при необходимости.")
        elif len(selected) > 1:
            self.log.append("Выбрано несколько тикеров. Параметры применяются ко всем выбранным тикерам одинаково.")
        else:
            self.log.append("Выберите тикер для торговли.")
        # Если выбрано несколько тикеров — не менять параметры (пусть пользователь сам задаёт)

    def start_multi_robot(self):
        token = self.token_input.text().strip()
        account_id = self.account_input.text().strip()
        selected = self.ticker_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите хотя бы один тикер!")
            self.log.append("Ошибка: не выбран ни один тикер для торговли.")
            return
        tickers_params = []
        for item in selected:
            ticker_str = item.text().strip()
            if "(" in ticker_str and ")" in ticker_str:
                ticker, class_code = ticker_str.split(" (")
                class_code = class_code.rstrip(")")
            else:
                ticker = ticker_str
                class_code = "TQBR"
            # Для каждого тикера — если он из мультистратегии, подставить параметры, иначе взять из UI
            params = TICKER_PARAMS.get(ticker)
            if params:
                rsi_len = params['rsi_len']
                min_range = params['min_range']
                take_profit = params['take_profit']
                stop_loss = params['stop_loss']
                trade_count = params['trade_count']
                self.log.append(f"Для {ticker} применяются параметры мультистратегии.")
            else:
                rsi_len = self.rsi_spin.value()
                min_range = self.min_range_spin.value()
                take_profit = self.tp_spin.value()
                stop_loss = self.sl_spin.value()
                trade_count = self.trade_count_spin.value()
                self.log.append(f"Для {ticker} применяются параметры, заданные вручную.")
            tickers_params.append((ticker, class_code, rsi_len, min_range, take_profit, stop_loss, trade_count))

        if not token or not account_id or not tickers_params:
            QMessageBox.warning(self, "Ошибка", "Заполните все поля!")
            self.log.append("Ошибка: не все поля заполнены.")
            return

        self.log.append("Запуск мультиторговли по выбранным тикерам...")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self.robot_thread = MultiRobotThread(
            token, account_id, tickers_params
        )
        self.robot_thread.log_signal.connect(self.log.append)
        self.robot_thread.finished_signal.connect(self.on_robot_finished)
        self.robot_thread.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
