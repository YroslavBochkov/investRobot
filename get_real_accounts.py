from tinkoff.invest import Client

TOKEN = "t.pZFbX9sjiO4zvZudBEPePrSh7RO9pHgv1wQkvhSA1ljGsokVIqtSSI0EGX7CrmdUwSLwV3S-rJJ_odiDRmPZSg"  # сюда подставь свой боевой TINKOFF_TOKEN

with Client(TOKEN) as client:
    accounts = client.users.get_accounts().accounts
    for acc in accounts:
        print(f"Real account id: {acc.id}, type: {acc.type}, status: {acc.status}")
