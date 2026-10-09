# __init__.py

import datetime as dt
from typing import Callable, Iterable

from rapid_markets.store import MarketDatabase

from pipeline.management import Manager
from pipeline.strategy import Strategy
from pipeline.indicators import Indicator
from pipeline.generators import BaseGenerator

from lab.experiment.metrics import Performance, Activity


__all__ = [
    'pair',
    'select',
    'all_generators',
    'Factory',
    'report',
    'segments'
]


type Factory = Callable[[Strategy], Manager]


def pair(strategies: dict[str, Strategy], managers: dict[str, Factory]) -> dict[str, Manager]:
    return {
        f'{s} / {m}': build(strategy)
        for s, strategy in strategies.items()
        for m, build in managers.items()
    }


def select(
    strategies: dict[str, Strategy],
    managers: dict[str, Factory],
    chosen: dict[str, tuple[str, ...]] | None = None
) -> tuple[dict[str, Strategy], dict[str, Manager]]:
    if chosen is None:
        return (
            strategies,
            {
                f'{s} / {m}': managers[m](strategies[s])
                for s in strategies
                for m in managers
            }
        )

    return (
        {s: strategies[s] for s in chosen},
        {
            f'{s} / {m}': managers[m](strategies[s])
            for s, names in chosen.items()
            for m in names
        }
    )


def all_generators(values: Iterable[Manager | Strategy | Indicator], /) -> set[BaseGenerator]:
    generators = set()

    for manager in values:
        generators.update(manager.generators())

    return generators


def report(
    title: str,
    performance: Performance,
    activity: Activity | None = None,
    sandbox: Performance | None = None,
    clusters: bool = False
) -> None:
    print(f'\n{title}\n')

    if sandbox is not None:
        print('active (real capital: contribution to the collective)\n')

    print(performance.table())

    if sandbox is not None:
        print('\nsandbox (paper, on own capital)\n')
        print(sandbox.table())

    if activity is not None:
        print()
        print(activity.report(clusters))

    print()


from system.history import segments  # noqa: E402 (kept here for the older scripts)
