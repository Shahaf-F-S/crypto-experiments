# fetch_fresh_wide.py

import asyncio
import datetime as dt
import pickle

from system.history import fetch


# A third universe, never used in any design: the next tier of Binance USDT pairs listed before 2023 (smaller and
# less liquid than the 78), hourly bars since 2022, for the final test of the breadth miner's frozen design.
# Run from the root: python -m lab.scripts.fetch_fresh_wide

WANTED = (
    'ACH ALICE API3 ASTR AUDIO BAND BEL BICO C98 CELR CHR CKB COTI CTSI CVC DGB DUSK FLUX GLM GLMR GMX HOT IOST JOE JST '
    'KNC LPT LQTY LSK MAGIC MTL NMR OGN ONG PEOPLE PHA POLYX POWR QI REQ RLC RSR SFP SKL SLP SUSHI SXP TFUEL TRB TWT UMA '
    'WAXP WOO XEC XVS YFI YGG ZRX STORJ LRC'
).split()

if __name__ == '__main__':
    markets = pickle.load(open('data/markets/binance_spot.pickle', 'rb'))
    active = {v['id'] for v in markets.values() if v.get('quote') == 'USDT' and v.get('spot') and v.get('active')}
    symbols = [f'{w}USDT' for w in WANTED if f'{w}USDT' in active]
    print(f'{len(symbols)} pairs: {" ".join(symbols)}', flush=True)
    asyncio.run(fetch(symbols, dt.date(2022, 1, 1), interval='1h', concurrency=4))
