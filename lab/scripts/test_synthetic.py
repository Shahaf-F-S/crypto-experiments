# test_synthetic.py

import asyncio
import datetime as dt
import math
import multiprocessing
from pathlib import Path

import numpy as np

from rapid_markets.store import MarketDatabase, TableLimits

from system.history import segments
from simulation import Market, MarketModel, calibrate, fit, structure

DATABASE = 'database/database.db'
EXCHANGE, SYMBOL = 'binance', 'BTC/USDT'
MODEL = Path('simulation/btc_usdt.model')
CALIBRATION, HELD_OUT = (0, 1, 2, 3), 4      # recorded segments (indices): calibration, and the one held out


async def spans() -> list[tuple[str, str]]:
    db = MarketDatabase(DATABASE)
    await db.connect()
    found = await segments(db, EXCHANGE, SYMBOL, dt.timedelta(minutes=5))
    await db.close()
    return found


async def calibration() -> MarketModel:
    db = MarketDatabase(DATABASE)
    await db.connect()
    found = await spans()

    async def source():
        for index in CALIBRATION:
            start, end = found[index]

            async for event in db.simulate_market(TableLimits(EXCHANGE, SYMBOL, start_time=start, end_time=end)):
                yield event

    model = None

    async for model in calibrate(source(), every=dt.timedelta(hours=6)):
        t = model.targets
        print(
            f"{model.hours:5.1f} h  volatility {t['volatility']:.2f}  trades/s {t['trade_rate']:.1f}  "
            f"moves/s {t['move_rate']:.3f}  flow regime {model.active:.2f} / {model.active_memory:.1f} orders  "
            f"slow {t['sign_slow']:.3f}  return -> flow {t['return_flow']:.3f}  "
            f"activity {[(h, round(s, 2)) for h, s in model.activity]}", flush=True
        )

    await db.close()
    return model


def real(index: int) -> dict[str, float]:
    async def go() -> dict[str, float]:
        db = MarketDatabase(DATABASE)
        await db.connect()
        start, end = (await spans())[index]
        result = await structure(db.simulate_market(TableLimits(EXCHANGE, SYMBOL, start_time=start, end_time=end)))
        await db.close()
        return result

    return asyncio.run(go())


def synthetic(seed: int) -> dict[str, float]:
    market = Market(model=MarketModel.load(MODEL), duration=dt.timedelta(hours=12), seed=100 + seed)
    return asyncio.run(structure(market.stream()))


def validation(replicas: int = 12) -> None:
    with multiprocessing.get_context('spawn').Pool(16) as pool:
        reals = pool.map(real, [1, 2, 3, HELD_OUT])
        synthetics = pool.map(synthetic, range(replicas))

    names = ['real 1', 'real 2', 'real 3', 'held out']
    print(f'\n{"":<34}' + ''.join(f'{n:>10}' for n in names) + f'{"syn 5%":>10}{"syn mean":>10}{"syn 95%":>10}')

    for name in reals[0]:
        values = np.array([s.get(name, math.nan) for s in synthetics])
        low, mean, high = np.nanpercentile(values, 5), np.nanmean(values), np.nanpercentile(values, 95)
        print(f'{name:<34}' + ''.join(f'{r.get(name, math.nan):>10.4g}' for r in reals) + f'{low:>10.4g}{mean:>10.4g}{high:>10.4g}')


if __name__ == '__main__':
    model = asyncio.run(calibration())

    for measured in fit(model, hours=4.0, seeds=16, rounds=6):
        print({key: round(value, 4) for key, value in measured.items()})

    model.save(MODEL)
    validation()
