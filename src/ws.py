import json
import logging
import src.manager as manager


from hyperliquid.info import Info
from hyperliquid.utils.types import (
    L2BookMsg,
    L2BookSubscription,
    UserEventsMsg,
)

logging.basicConfig(level=logging.INFO,format='%(asctime)s:%(levelname)s:%(message)s')

def on_book_update(book_msg: L2BookMsg) -> None:
        # logging.debug(f"book_msg {book_msg}")
        book_data = book_msg["data"]
        if book_data["coin"] != "ETH":
            logging.debug("Unexpected book message or ather coin, skipping")
            return
        book_buy_price = float(book_data["levels"][0][0]["px"])
        book_sell_price = float(book_data["levels"][1][0]["px"])
        book_buy_size = float(book_data["levels"][0][0]["sz"])
        book_sell_size = float(book_data["levels"][1][0]["sz"])
        logging.info(
            f"on_book_update buy_price:{book_buy_price} size:{book_buy_size} sell_price:{book_sell_price} size:{book_sell_size}"
        )

def subCoin(info: Info, coin: str):
    subscription: L2BookSubscription = {"type": "l2Book", "coin": coin}
    info.subscribe(subscription, on_book_update)

def on_user_events(user_events: UserEventsMsg) -> None:
    user_events_data = user_events["data"]
    fill = user_events_data["fills"][0]
    address = user_events_data["user"]
    coin = fill["coin"]
    if "Close" in fill["dir"]:
        acc = manager.ACCOUNTS[address]
        user_state = acc.info.user_state(acc.address)
        user_positions = user_state["assetPositions"]
        for position in user_positions:
            if (position["position"]["coin"] == coin):
                return False
        if not address in manager.ACCOUNTS[coin]["Free"]:
            manager.ACCOUNTS[coin]["Free"].append(address)
        if address in manager.ACCOUNTS[coin]["Working"]:
            index = manager.ACCOUNTS[coin]["Working"].index(address)
            manager.ACCOUNTS[coin]["Working"].pop(index)
        return True
    if "fills" in user_events_data:
        with open("fills", "a+") as f:
            f.write(json.dumps(user_events_data["fills"]))
            f.write("\n")    

def on_order_events(order_events):
    user = order_events["data"]["user"]
    for order in order_events["data"]["orderHistory"]:
        triggerCondition = order["order"]["triggerCondition"]
        status = order["status"]
        if status == 'open':
            return
        if status != 'canceled' or status != 'Canceled' or status != 'Cancelled' or status != 'cancelled':
            return
        elif triggerCondition != 'Triggered':
            return
        coin = order["order"]["coin"]
        logging.info(f"TP/SL was triggered but order is cancelled {user} coin: {coin} ")
        manager.ACCOUNTS[user].closePosition(coin)

