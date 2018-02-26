#!/usr/bim/python27
# -*- coding: utf-8 -*-

import os
import sys
import json
import requests
import urllib, http.client
import hmac, hashlib
import time
from config import API_KEY, API_SECRET

# Тонкая настройка
CURRENCY_1 = sys.argv[1]
CURRENCY_2 = 'btc'

ORDER_LIFE_TIME = 3 # 
STOCK_FEE = 0.002 # Комиссия, которую берет биржа (0.002 = 0.2%)
OFFERS_AMOUNT = 2 # Сколько предложений из стакана берем для расчета средней цены
CAN_SPEND = 0.00007 # Сколько максимум вливать в памп
PROFIT_MARKUP = 0.10 # Профит от пампа в % (0.1 = 10%)
DEBUG = True 
MAX_UNPROFIT = 0.01 # Насколько максимум уменьшить профит при покупке

CURR_PAIR = CURRENCY_1.lower() + "_" + CURRENCY_2.lower()

nonce_file = "./nonce"
if not os.path.exists(nonce_file):
    with open(nonce_file, "w") as out:
        out.write('1')

class ScriptError(Exception):
    pass
class ScriptQuitCondition(Exception):
    pass
        
def call_api(**kwargs):
    with open(nonce_file, 'r+') as inp:
        nonce = int(inp.read())
        inp.seek(0)
        inp.write(str(nonce+1))
        inp.truncate()

    payload = {'nonce': nonce}

    if kwargs:
        payload.update(kwargs)
    payload =  urllib.parse.urlencode(payload)

    H = hmac.new(key=API_SECRET, digestmod=hashlib.sha512)
    H.update(payload.encode('utf-8'))
    sign = H.hexdigest()
    
    headers = {"Content-type": "application/x-www-form-urlencoded",
           "Key":API_KEY,
           "Sign":sign}
    conn = http.client.HTTPSConnection("yobit.io", timeout=60)
    conn.request("POST", "/tapi/", payload, headers)
    response = conn.getresponse().read()
    
    conn.close()

    try:
        obj = json.loads(response.decode('utf-8'))

        if 'error' in obj and obj['error']:
            raise ScriptError(obj['error'])
        return obj
    except json.decoder.JSONDecodeError:
        raise ScriptError('Ошибка анализа возвращаемых данных, получена строка', response)


def wanna_get():
    return  (CAN_SPEND*(1+STOCK_FEE) + CAN_SPEND * PROFIT_MARKUP) / (1 - STOCK_FEE)  

def main_flow():
    try:
        offers = json.loads(requests.get("https://yobit.io/api/3/depth/"+CURR_PAIR+"?limit="+str(OFFERS_AMOUNT)).text)[CURR_PAIR]
        prices = [bid[0] for bid in offers['asks']]                                       
        try:        
            avg_price = (sum(prices)/len(prices))
            my_need_price = avg_price*(1+MAX_UNPROFIT)
            my_amount = CAN_SPEND/my_need_price

            # Покупаем
            new_order = call_api(method="Trade", pair=CURR_PAIR, type="buy", rate="{rate:0.8f}".format(rate=my_need_price), amount="{amount:0.8f}".format(amount=my_amount))['return']
            # Смиотрим сколько купили
            balances = call_api(method="getInfo")['return']['funds']
            # Продаем по профиту
            new_order = call_api(method="Trade", pair=CURR_PAIR, type="sell", rate="{rate:0.8f}".format(rate=wanna_get()/float(balances[CURRENCY_1])), amount="{amount:0.8f}".format(amount=balances[CURRENCY_1]))['return']
        except ZeroDivisionError:
            print('Не удается вычислить среднюю цену', prices)
               
        
    except ScriptError as e:
        print(e)
    except ScriptQuitCondition as e:
        print(e)

    
main_flow()     
