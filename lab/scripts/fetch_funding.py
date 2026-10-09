# fetch_funding.py

import asyncio
import datetime as dt

from system.history import fetch_funding

SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']

if __name__ == '__main__':
    asyncio.run(fetch_funding(SYMBOLS, dt.date(2021, 1, 1)))
