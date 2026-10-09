# fetch_wide.py

import asyncio
import datetime as dt
import pickle

from system.history import fetch


# A wider universe for the breadth studies: liquid, long-listed Binance USDT pairs beyond the 21 of the panel (no
# stablecoins, no tokenized stocks), hourly bars since 2022 (resumable). Run from the root:
# python -m lab.scripts.fetch_wide

WANTED = (
    '1INCH ANKR APE APT AR ARB AXS BAT CAKE CELO CHZ COMP CRV DASH DYDX EGLD ENJ ENS FET FLOW GALA GMT GRT HBAR ICP '
    'IMX INJ IOTA IOTX JASMY KAVA KSM LDO MANA MASK MINA NEO OP PEPE QNT QTUM ROSE RUNE RVN SAND SHIB SNX STX SUI '
    'THETA VET XTZ ZEC ZIL ONE ONT CFX'
).split()

if __name__ == '__main__':
    markets = pickle.load(open('data/markets/binance_spot.pickle', 'rb'))
    active = {v['id'] for v in markets.values() if v.get('quote') == 'USDT' and v.get('spot') and v.get('active')}
    symbols = [f'{w}USDT' for w in WANTED if f'{w}USDT' in active]
    print(f'{len(symbols)} pairs: {" ".join(symbols)}', flush=True)
    asyncio.run(fetch(symbols, dt.date(2022, 1, 1), interval='1h', concurrency=4))
