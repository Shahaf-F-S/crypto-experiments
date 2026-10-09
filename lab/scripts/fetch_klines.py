# fetch_klines.py

import asyncio
import datetime as dt

from system.history import fetch

SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']

if __name__ == '__main__':
    asyncio.run(fetch(SYMBOLS, dt.date(2021, 1, 1), interval='1h'))
    asyncio.run(fetch(SYMBOLS, dt.date(2021, 1, 1), interval='15m'))
