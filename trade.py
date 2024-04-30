import logging
import manager
import threading
import queue
import logging
import random



class Trade:
    def __init__(self, service):
        self.service = service
        self.sz_decimals = {}
        self.max_leverages = {}
        self.result_queue = queue.Queue()
        meta = self.service['info'].meta()
        for asset_info in meta["universe"]:
            self.sz_decimals[asset_info["name"]] = asset_info["szDecimals"]
            self.max_leverages[asset_info["name"]] = asset_info["maxLeverage"]

    def roundSize(self, coin, size):
        return round(size, self.sz_decimals[coin])
    
    def calculate_tpslPrice(self, entry_price, leverage, delta):
        pnl_change = entry_price * delta/100 / leverage
        pnl_plus = entry_price + pnl_change
        pnl_minus= entry_price - pnl_change
        return round(float(f"{pnl_plus:.5g}"), 6), round(float(f"{pnl_minus:.5g}"), 6)
    
    def get_prices(self, coin):
        returnData = {}
        book_data = self.service["info"].l2_snapshot(coin)
        returnData["buy_price"] = float(book_data["levels"][0][0]["px"])
        returnData["sell_price"] = float(book_data["levels"][1][0]["px"])
        returnData["buy_size"] = float(book_data["levels"][0][0]["sz"])
        returnData["sell_size"] = float(book_data["levels"][1][0]["sz"])
        return returnData
    
    def check_slipage(self, num1, num2):
        if num1 - int(num1) == 0:
            num1 = int(num1)
        if num2 - int(num2) == 0:
            num2 = int(num2)
        decimal_places_num1 = len(str(num1).split('.')[-1]) if '.' in str(num1) else 0
        decimal_places_num2 = len(str(num2).split('.')[-1]) if '.' in str(num2) else 0
        max_decimal_places = max(decimal_places_num1, decimal_places_num2)
        threshold = 2 * 10 ** -max_decimal_places
        max1 = max(num1, num2)
        min2 = min(num1, num2)
        s = max1 - threshold
        return s < min2
    
    def openOrderTHRD(self, account, coin, is_buy, sz, px):
        res = account.openOrder(coin, is_buy, sz, px)
        self.result_queue.put(res)

    def open_tpsl(self, coin, account, is_buy, price, sz, leverage, delta):
        tppx, slpx = self.calculate_tpslPrice(price, leverage, delta)
        stop_order_type = None
        tp_order_type = None
        stop_result = None
        tp_result = None
        if (is_buy):
            stop_order_type = {"trigger": {"triggerPx": tppx, "isMarket": False, "tpsl": "sl"}}
            tp_order_type = {"trigger": {"triggerPx": slpx, "isMarket": False, "tpsl": "tp"}}
            stop_result = account.exchange.order(coin, is_buy, sz, tppx, stop_order_type, reduce_only=True)
        else:
            stop_order_type = {"trigger": {"triggerPx": slpx, "isMarket": False, "tpsl": "sl"}}
            tp_order_type = {"trigger": {"triggerPx": tppx, "isMarket": False, "tpsl": "tp"}}
            stop_result = account.exchange.order(coin, is_buy, sz, slpx, stop_order_type, reduce_only=True)
        if stop_result["status"] == "ok":
            statusSL = stop_result["response"]["data"]["statuses"][0]
            if "resting" in statusSL:
                if (is_buy):
                    tp_result = account.exchange.order(coin, is_buy, sz, slpx, tp_order_type, reduce_only=True) 
                else:
                    tp_result = account.exchange.order(coin, is_buy, sz, tppx, tp_order_type, reduce_only=True) 
                statusTP = tp_result["response"]["data"]["statuses"][0]
                if "resting" in statusTP: 
                    return True
                else:
                    self.open_tpsl(coin, account, is_buy, price, sz, leverage, delta)        
            else:
                self.open_tpsl(coin, account, is_buy, price, sz, leverage, delta)
    
    def open_oders(self, pair, coin, margin, leverage, tpsl):
        book_data = self.get_prices(coin)
        book_buy_price = book_data["buy_price"]
        book_sell_price = book_data["sell_price"]
        book_buy_size = book_data["buy_size"]
        book_sell_size = book_data["sell_size"]
        buy_value = margin * leverage / book_sell_price 
        sell_value = margin * leverage / book_buy_price 
        buy_sz = self.roundSize(coin, buy_value)
        sell_sz = self.roundSize(coin, sell_value)
        check = self.check_slipage(book_sell_price, book_buy_price)
        if  (book_sell_size > sell_sz and book_buy_size > buy_sz and check):
            variables = pair
            longer = random.choice(variables)
            shorter = None
            if longer == variables[0]:
                shorter = variables[1]
            else:
                shorter = variables[0]
            longer = manager.ACCOUNTS[longer]
            shorter = manager.ACCOUNTS[shorter]
            thread1 = threading.Thread(target=self.openOrderTHRD, args=(longer, coin, True, buy_sz, book_sell_price,))
            thread2 = threading.Thread(target=self.openOrderTHRD, args=(shorter, coin, False, sell_sz, book_buy_price,))
        # order_result = first.openOrder(COIN, True, sz, book_sell_price)
        # res2 = second.openOrder(COIN, False, sz, book_buy_price)

            thread1.start()
            thread2.start()
            thread1.join()
            thread2.join()
            result_buyOrder = self.result_queue.get()
            result_sellOrder = self.result_queue.get()
            res = None
            res1 = None
            if (result_buyOrder == False and result_sellOrder != False):
                logging.info(f"BuyOrder is not filled")
                res = shorter.closePosition(coin)
                res1 = longer.closePosition(coin)
                return self.open_oders(pair, coin, margin, leverage, tpsl)
            if (result_sellOrder == False and result_buyOrder != False):
                logging.info(f"SellOrder is not filled")
                res = shorter.closePosition(coin)
                res1 = longer.closePosition(coin)
                return self.open_oders(pair, coin, margin, leverage, tpsl)                
            if ((result_buyOrder == False and result_sellOrder == False) or float(result_buyOrder["sz"]) != buy_sz or float(result_sellOrder["sz"]) != sell_sz):
                res = longer.closePosition(coin)
                res1 = shorter.closePosition(coin)
                logging.info(f"some kind of order is not filled, or it is not fully filled")
                return self.open_oders(pair, coin, margin, leverage, tpsl)

            if (res == False or res1 == False):
                logging.info(f"Давай по новвой все хуйня")
                return False
            

            self.open_tpsl(coin, longer, False, book_sell_price, buy_sz, leverage, tpsl)
            self.open_tpsl(coin, shorter, True, book_buy_price, sell_sz, leverage, tpsl)
            # self.open_tpsl(coin, longer, False, book_sell_price, buy_sz, leverage, tpsl+1)
            # self.open_tpsl(coin, shorter, True, book_buy_price, sell_sz, leverage, tpsl+1)
            self.open_tpsl(coin, longer, False, book_sell_price, buy_sz, leverage, tpsl+2)
            self.open_tpsl(coin, shorter, True, book_buy_price, sell_sz, leverage, tpsl+2)
            # self.open_tpsl(coin, longer, False, book_sell_price, buy_sz, leverage, tpsl+3)
            # self.open_tpsl(coin, shorter, True, book_buy_price, sell_sz, leverage, tpsl+3)
            self.open_tpsl(coin, longer, False, book_sell_price, buy_sz, leverage, tpsl+4)
            self.open_tpsl(coin, shorter, True, book_buy_price, sell_sz, leverage, tpsl+4)
            # self.open_tpsl(coin, longer, False, book_sell_price, buy_sz, leverage, tpsl+5)
            # self.open_tpsl(coin, shorter, True, book_buy_price, sell_sz, leverage, tpsl+5)
            logging.info(f"Orders is open")

        else:
            logging.info(f"There is not enough volume to execute orders or the execution price is too different")
            return self.open_oders(pair, coin, margin, leverage, tpsl)
