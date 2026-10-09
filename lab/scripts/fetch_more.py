# fetch_more.py

import asyncio
import datetime as dt

from system.history import fetch, fetch_funding

# Pairs never used in discovery: an out-of-sample test across assets.
NEW = ['DOGEUSDT', 'ADAUSDT', 'LTCUSDT', 'LINKUSDT', 'AVAXUSDT', 'DOTUSDT', 'TRXUSDT', 'BCHUSDT']

if __name__ == '__main__':
    asyncio.run(fetch(NEW, dt.date(2021, 1, 1), interval='1h'))
    asyncio.run(fetch_funding(NEW, dt.date(2021, 1, 1)))
