import eth_account
from eth_account.signers.local import LocalAccount
import json
import os
import logging
import sys
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

logging.basicConfig(level=logging.INFO,format='%(asctime)s:%(levelname)s:%(message)s')

def get_accounts():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path) as f:
        config = json.load(f)
    accounts = config["accounts"]
    return accounts

def get_account(address):
    accounts = get_accounts()
    address_lower = address.lower()
    for acc_address, acc_value in accounts.items():
        acc_address_lower = acc_address.lower()
        if acc_address_lower == address_lower:
            return acc_value
    return None

def get_service():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path) as f:
        config = json.load(f)
    service = config["service"]
    return service

def setup(wallet, base_url=None, skip_ws=False, skip_ex=False):
    if wallet == "service":
        account_data = get_service()
    else:
        account_data = get_account(wallet)
    account: LocalAccount = eth_account.Account.from_key(account_data["secret_key"])
    address = account_data["account_address"]
    proxy = account_data["proxy"]
    if proxy != True:
        proxy = None
    if address == "":
        address = account.address
    logging.info("Running with account address: " + address)
    if address != account.address:
         logging.info("Running with agent address: " + account.address)
    info = Info(base_url, skip_ws, proxy = proxy)
    user_state = info.user_state(address)
    margin_summary = user_state["marginSummary"]
    if float(margin_summary["accountValue"]) == 0:
        logging.debug("Not running the example because the provided account has no equity.")
        url = info.base_url.split(".", 1)[1]
        error_string = f"No accountValue:\nIf you think this is a mistake, make sure that {address} has a balance on {url}.\nIf address shown is your API wallet address, update the config to specify the address of your account, not the address of the API wallet."
        raise Exception(error_string)
    if skip_ex != True:
        exchange = Exchange(account, base_url, account_address=address, proxy=proxy)
        return address, info, exchange
    else:
        return address, info

