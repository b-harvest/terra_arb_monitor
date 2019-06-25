# terra_arb_monitor
Web monitoring tool for terra blockchain arbitrage opportunity. It should be running on a server with terrad running.

# must-install
- python3
- redis
- requests
- flask
- plotly

# files
- terra_backend.py : running backend(retrieve data and save in local redis)
- terra_frontend.py : running frontend(run flask to serve website to monitor prices and graphs)
- templates/index.html : html for website

# telegram alert
- in terra_backend.py, there exists a parameter called alarm_trigger. It implies it will send telegram message when any price difference between market_price and swap_price exceeds alarm_trigger.
