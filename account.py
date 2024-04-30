import ws
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants
import utils
import logging
import manager

active = {}

class Account:
    def __init__(self, address: str):
        setup = utils.setup(address, base_url=constants.MAINNET_API_URL, skip_ws = False , skip_ex=False)
        self.address, self.info, self.exchange  = setup
        self.info.subscribe({"type": "userFills", "user": self.address}, ws.on_user_events)
        self.info.subscribe({"type": "userHistoricalOrders", "user": self.address}, ws.on_order_events)
        self.status = {}
        active[self.address.lower()] = self
    
    def cancelOrders(self):
        open_orders = self.info.open_orders(self.address)
        for open_order in open_orders:
            order_result = self.exchange.cancel(open_order["coin"], open_order["oid"])
            if order_result["status"] == "ok":
                status = order_result["response"]["data"]["statuses"][0]
                if "resting" in status:
                    cancel_result = self.exchange.cancel("ETH", status["resting"]["oid"])
                    logging.info(f"Cancelled order {cancel_result}")

    def closePosition(self, coin):
        logging.info(f"Closing position {coin}")
        order_result = self.exchange.market_close(coin)
        if order_result == None:
            user_state = self.info.user_state(self.address)
            user_positions = user_state["assetPositions"]
            for position in user_positions:
                if (position["position"]["coin"] == coin):
                    return False
            return None
        elif order_result["status"] == "ok":
            for status in order_result["response"]["data"]["statuses"]:
                try:
                    filled = status["filled"]
                    logging.info(f'Order #{filled["oid"]} filled {filled["totalSz"]} @{filled["avgPx"]}')
                    return True
                except KeyError:
                    logging.error(f'Error: {status["error"]}')
        return False
        

    def openOrder(self, coin: str, is_buy: bool, size: float, price: float):
        order_result = self.exchange.order(coin, is_buy, size, price, {"limit": {"tif": "Ioc"}})
        if order_result["status"] == "ok":
            status = order_result["response"]["data"]["statuses"][0]
            if "error" in status:
                err = status["error"]
                logging.error(f"Open order: {err}")
                return False
            elif "filled"in status:
                fill = status["filled"]
                sz = fill["totalSz"]
                px = fill["avgPx"]
                oid = fill["oid"]
                logging.info(f"Open order: oid {oid} sz {sz} px {px}")
                res = {}
                res["sz"] = sz
                res["px"] = px
                address = self.address.lower()
                coinData = manager.ACCOUNTS[coin]
                coinWorkers = coinData["Working"]
                coinResters = coinData["Free"]
                if not address in coinWorkers:
                    coinWorkers.append(address)
                    manager.ACCOUNTS[coin]["Working"] = coinWorkers
                if address in coinResters:
                    coinResters.remove(address)
                    manager.ACCOUNTS[coin]["Free"] = coinResters
                    # manager.ACCOUNTS[coin]["Free"].remove(address) # тут вроде хуйня удаляет отовсюду адрес и во фри и в листе
                return res
            
        # if "resting" in status:
        #     order_status = info.query_order_by_oid(address, status["resting"]["oid"])
        #     print("Order status by oid:", order_status)
        # if order_result["status"] == "ok":
        # for status in order_result["response"]["data"]["statuses"]:
        #     try:
        #         filled = status["filled"]
        #         print(f'Order #{filled["oid"]} filled {filled["totalSz"]} @{filled["avgPx"]}')
        #     except KeyError:
        #         print(f'Error: {status["error"]}')

