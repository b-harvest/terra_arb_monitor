import json
import time
import subprocess
from multiprocessing import Pool
# installation required
import redis
import requests

# telagram token
telegram_token = "" # put your telegram token
telegram_chat_id = "" # put your telegram chat id

# parameters
fx_map = {"uusd":"USDUSD","ukrw":"USDKRW","ueur":"USDEUR","ucny":"USDCNY","ujpy":"USDJPY","usdr":"USDSDR"}
active = ["ukrw","usdr","uusd"]
save_length = 60*24*30 # 30days
alarm_trigger = 0.05 # alarm telegram when divergence of market_price and swap_price exceeds alarm_trigger

# redis
r = redis.Redis(host='localhost', port=6379, db=0)

# set last update time
last_ts = time.time() - 60.0
last_height = 0

def get_data(source):
    print(source)
    if source=="get_fx_rate":
        return get_fx_rate()
    elif source=="get_sdr_rate":
        return get_sdr_rate()
    elif source=="get_coinone_luna_price":
        return get_coinone_luna_price()
    elif source=="get_swap_price":
        return get_swap_price()

# get latest block info
def get_latest_block():
    err_flag = False
    try:
        # get block height
        cmd = "sudo terracli status"
        status = json.loads(subprocess.check_output(cmd,shell=True).decode("utf-8"))
        latest_block_height = int(status["sync_info"]["latest_block_height"])
        latest_block_time = status["sync_info"]["latest_block_time"]
    except:
        print("get block height error!")
        err_flag = True
        latest_block_height = None
        latest_block_time = None
    return err_flag, latest_block_height, latest_block_time

# get real fx rates
def get_fx_rate():
    err_flag = False
    try:
        # get currency rate
        url = "https://www.freeforexapi.com/api/live?pairs=USDUSD,USDKRW,USDEUR,USDCNY,USDJPY"
        api_result = json.loads(requests.get(url).text)
        real_fx = {"USDUSD":1.0,"USDKRW":1.0,"USDEUR":1.0,"USDCNY":1.0,"USDJPY":1.0,"USDSDR":1.0}
        real_fx["USDUSD"] = float(api_result["rates"]["USDUSD"]["rate"])
        real_fx["USDKRW"] = float(api_result["rates"]["USDKRW"]["rate"])
        real_fx["USDEUR"] = float(api_result["rates"]["USDEUR"]["rate"])
        real_fx["USDCNY"] = float(api_result["rates"]["USDCNY"]["rate"])
        real_fx["USDJPY"] = float(api_result["rates"]["USDJPY"]["rate"])
    except:
        print("get currency rate error!")
        err_flag = True
        real_fx = None
    return err_flag, real_fx

# get real sdr rates
def get_sdr_rate():
    err_flag = False
    try:
        # get sdr
        scrap_start = '<div class="DirectionBackgroundColor__BackgroundColor-sc-1qjm64q-0 fgRxHG">'
        scrat_end = '</div>'
        url = "https://www.fxempire.com/markets/xdr-usd/chart?page=1"
        scrap_result = requests.get(url).text
        scrap_cuthead = scrap_result[scrap_result.index(scrap_start) + len(scrap_start):]
        sdr_rate = 1.0/float(scrap_cuthead[:scrap_cuthead.index(scrat_end)])
    except:
        print("get sdr rate error!")
        err_flag = True
        sdr_rate = None
    return err_flag, sdr_rate

# get coinone luna krw price
def get_coinone_luna_price():
    err_flag = False
    try:
        # get luna/krw
        url = "https://api.coinone.co.kr/orderbook/?currency=luna&format=json"
        luna_result = json.loads(requests.get(url).text)
        askprice = float(luna_result["ask"][0]["price"])
        bidprice = float(luna_result["bid"][0]["price"])
        midprice = (askprice + bidprice)/2.0
        luna_price = {"base_currency":"ukrw","exchange":"coinone","askprice":askprice,"bidprice":bidprice,"midprice":midprice}
        luna_base = "USDKRW"
        luna_midprice_krw = luna_price["midprice"]
    except:
        print("get luna/krw price error!")
        err_flag = True
        luna_price = None
        luna_base = None
        luna_midprice_krw = None
    return err_flag, luna_price, luna_base, luna_midprice_krw

# get swap price
def get_swap_price():
    err_flag = False
    try:
        swap_price = []
        for currency in active:
            cmd = "sudo terracli q oracle price --denom " + currency + " --output json"
            swap_price.append(float(json.loads(subprocess.check_output(cmd,shell=True).decode("utf-8"))["price"]))
    except:
        print("get swap price error!")
        err_flag = True
        swap_price = None
    return err_flag, swap_price

while True:

    ts = time.time()

    latest_block_err_flag = False
    fx_err_flag = False
    sdr_err_flag = False
    coinone_err_flag = False
    swap_price_err_flag = False
    all_err_flag = False

    # get latest_block
    latest_block_err_flag, latest_block_height, latest_block_time = get_latest_block()

    # get data
    if latest_block_err_flag == False:
        if latest_block_height > last_height:
            p = Pool(4)
            res_fx, res_sdr, res_coinone, res_swap = p.map(get_data, ["get_fx_rate","get_sdr_rate","get_coinone_luna_price","get_swap_price"])
            fx_err_flag, real_fx = res_fx
            sdr_err_flag, sdr_rate = res_sdr
            coinone_err_flag, luna_price, luna_base, luna_midprice_krw = res_coinone
            swap_price_err_flag, swap_price = res_swap
            if fx_err_flag or sdr_err_flag or coinone_err_flag or swap_price_err_flag:
                all_err_flag = True
        else:
            all_err_flag = True
    else:
        all_err_flag = True

    # reorganize data
    if all_err_flag==False:
        try:
            # get swap price
            real_fx["USDSDR"] = sdr_rate
            swap_price_compare = []
            i = 0
            for currency in active:
                market_price = float(luna_midprice_krw * (real_fx[fx_map[currency]] / real_fx[luna_base]))
                swap_price_compare.append({"market":currency,"swap_price":swap_price[i],"market_price":market_price})
                i += 1
        except:
            print("reorganize data error!")
            all_err_flag = True

    # save data to redis
    if all_err_flag==False:
        # save current data to redis
        result = {"index":int(ts/60), "timestamp":ts, "block_height":latest_block_height, "block_time":latest_block_time,"swap_price_compare":swap_price_compare, "real_fx":real_fx, "luna_price_list":[luna_price]}
        r.set("current_terra_swap_market",json.dumps(result))
        print("current_terra_swap_market updated at height " + str(latest_block_height))
        last_height = latest_block_height
        # telegram alert
        for compare in swap_price_compare:
            if abs(compare["swap_price"]-compare["market_price"])/compare["market_price"] > alarm_trigger: # divergence
                alarm_content = compare["market"] + " price diversion at height " + str(latest_block_height) + "! market_price:" + str("{0:.4f}".format(compare["market_price"])) + ", swap_price:" + str("{0:.4f}".format(compare["swap_price"]))
                try:
                    requestURL = "https://api.telegram.org/bot" + str(telegram_token) + "/sendMessage?chat_id=" + telegram_chat_id + "&text="
                    requestURL = requestURL + str(alarm_content)
                    response = requests.get(requestURL, timeout=1)
                except:
                    pass
        # when last update time pass 60 seconds, save to historical data list
        if int(ts/60.0) > int(last_ts/60.0):
            r.lpush("terra_swap_market",json.dumps(result))
            r.set("latest_update_market_ts", ts)
            last_ts = ts
            r.ltrim("terra_swap_market",0,save_length)


    time.sleep(1)
