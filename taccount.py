from tinkoff.invest import Client

TOKEN = "t.e_jI6Yp81teOtITYmaLMQRRTN9WFxFOsJwoo-5RFpjZThTgFTjZm__DrhNQvoMcFoTPMfqlxsxPx8bXLvR1TtA"  # сюда подставь свой TINKOFF_TOKEN

with Client(TOKEN) as client:
    # Создаём аккаунт песочницы (если уже есть — ничего страшного)
    acc = client.sandbox.open_sandbox_account()
    print("Создан аккаунт песочницы:", acc.account_id)

    # Выводим все аккаунты песочницы
    accounts = client.sandbox.get_sandbox_accounts().accounts
    for acc in accounts:
        print("Sandbox account id:", acc.id)
