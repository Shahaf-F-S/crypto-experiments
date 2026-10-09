# fetch_fresh.py

import asyncio
import datetime as dt

from system.history import fetch, fetch_funding

# A third group of liquid pairs, fetched only for the final validation of refinements (never explored).
FRESH = ['ATOMUSDT', 'NEARUSDT', 'FILUSDT', 'ETCUSDT', 'UNIUSDT', 'AAVEUSDT', 'XLMUSDT', 'ALGOUSDT']

if __name__ == '__main__':
    asyncio.run(fetch(FRESH, dt.date(2021, 1, 1), interval='1h'))
    asyncio.run(fetch_funding(FRESH, dt.date(2021, 1, 1)))
