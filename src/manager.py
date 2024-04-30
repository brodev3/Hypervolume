import random


ACCOUNTS = {
    "list": []
}

def check_Statuses(coin):
    for account in ACCOUNTS["list"]:
        acc = ACCOUNTS[account]
        user_state = acc.info.user_state(acc.address)
        user_positions = user_state["assetPositions"]
        for position in user_positions:
            if (position["position"]["coin"] == coin):
                if not account in ACCOUNTS[coin]["Working"]:
                    ACCOUNTS[coin]["Working"].append(account)
                if account in ACCOUNTS[coin]["Free"]:
                    index = ACCOUNTS[coin]["Free"].index(account)
                    ACCOUNTS[coin]["Free"].pop(index)
            else:
                if not account in ACCOUNTS[coin]["Free"]:
                    ACCOUNTS[coin]["Free"].append(account)
                if account in ACCOUNTS[coin]["Working"]:
                    index = ACCOUNTS[coin]["Working"].index(account)
                    ACCOUNTS[coin]["Working"].pop(index)

def add_Coin(coin):
   ACCOUNTS[coin] = {
       "Free": [],
       "Working": []
   }
   ACCOUNTS[coin]["Free"].extend(ACCOUNTS['list'])

def get_FreePair(coin):
    if len(ACCOUNTS[coin]["Free"]) >= 2:
        result = random.sample(ACCOUNTS[coin]["Free"], 2)
    else:
        result = False
    return result
 