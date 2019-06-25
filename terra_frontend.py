import subprocess
import json
import time
# installation required
import redis
import requests
from flask import Flask, render_template
import plotly, plotly.graph_objs as go

# flask
app = Flask(__name__)

# redis
r = redis.Redis(host='localhost', port=6379, db=0)

# parameters
currencies = ["ukrw","usdr","uusd"]
max_data = 600 # automatically delete historical data passing more than max_data minutes

last_update_height = 0

def retrieve_data():

    global last_update_height

    swap_prices_data = []
    for item in r.lrange("terra_swap_market",0,max_data):
        swap_prices_data.append(json.loads(item.decode('utf-8')))

    current_terra_swap_market = json.loads(r.get("current_terra_swap_market").decode("utf-8"))

    # initialize
    swap_prices = {"ukrw": [], "usdr": [], "uusd": []}
    market_prices = {"ukrw": [], "usdr": [], "uusd": []}
    current_swap_prices = {"ukrw": 0.0, "usdr": 0.0, "uusd": 0.0}
    current_market_prices = {"ukrw": 0.0, "usdr": 0.0, "uusd": 0.0}
    height_swap_price = []
    time_swap_price = []
    update_flag = False

    # get historical data
    for i in range(0,len(swap_prices_data)):
        j = len(swap_prices_data)-i-1
        height_swap_price.append(int(swap_prices_data[j]["block_height"]))
        time_swap_price.append(swap_prices_data[j]["block_time"])
        for currency in currencies:
            for item in swap_prices_data[j]["swap_price_compare"]:
                if item["market"] == currency:
                    swap_prices[currency].append(float(item["swap_price"]))
                    market_prices[currency].append(float(item["market_price"]))
                    break

    num_data = len(height_swap_price)

    # get current data
    current_height_swap_price = int(current_terra_swap_market["block_height"])
    current_time_swap_price = current_terra_swap_market["block_time"]
    for currency in currencies:
        for item in current_terra_swap_market["swap_price_compare"]:
            if item["market"] == currency:
                current_swap_prices[currency] = float(item["swap_price"])
                current_market_prices[currency] = float(item["market_price"])
                break

    # create an array of traces for graph data
    graph_data = []
    data = {}
    i = 1
    data.update({'current_info' : {'block_height':height_swap_price[num_data-1], 'block_time':time_swap_price[num_data-1]}})
    data.update({'current_rate' : {'ukrw':{'swap_price':swap_prices["ukrw"][num_data-1],'market_price':market_prices["ukrw"][num_data-1]}, \
                                   'usdr':{'swap_price':swap_prices["usdr"][num_data-1],'market_price':market_prices["usdr"][num_data-1]}, \
                                   'uusd':{'swap_price':swap_prices["uusd"][num_data-1],'market_price':market_prices["uusd"][num_data-1]}}})
    for currency in currencies:
        graph_data_each = []
        graph_data_each.append(go.Scatter(x=height_swap_price,y=swap_prices.get(currency),name="{} swap prices".format(currency)))
        graph_data_each.append(go.Scatter(x=height_swap_price,y=market_prices.get(currency),name="{} market prices".format(currency)))
        data.update({'graph' + str(i) : json.dumps(list(graph_data_each), cls=plotly.utils.PlotlyJSONEncoder)})
        i += 1

    # create current_data json
    current_data = {}
    current_data.update({'current_info' : {'block_height':current_height_swap_price, 'block_time':current_time_swap_price}})
    current_data.update({'current_rate' : {'ukrw':{'swap_price':current_swap_prices["ukrw"],'market_price':current_market_prices["ukrw"]}, \
                                   'usdr':{'swap_price':current_swap_prices["usdr"],'market_price':current_market_prices["usdr"]}, \
                                   'uusd':{'swap_price':current_swap_prices["uusd"],'market_price':current_market_prices["uusd"]}}})

    if last_update_height < height_swap_price[num_data-1] or last_update_height == 0:
        update_flag = True

    if update_flag:
        # trigger event
        last_update_height = height_swap_price[num_data-1]
        print("pushing data complete at height " + str(last_update_height))

    r.set("data",json.dumps(data))
    r.set("current_data",json.dumps(current_data))

    return True

@app.route("/")
def index():

    retrieve_data()
    data = json.loads(r.get("data").decode('utf-8'))
    current_data = json.loads(r.get("current_data").decode('utf-8'))
    return render_template("index.html",data=data, current_data=current_data)

def flask_run():
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)

if __name__ == '__main__':

    global last_update_height
    last_update_height = 0
    flask_run()
