"""Measurements the test loop calls: trading results per combination, and when the combinations hold positions."""

import datetime as dt
from collections import Counter

import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

from rapid_markets.base import FeeModel

from pipeline.features import Features
from pipeline.management import Manager, Position
from pipeline.strategy import LONG


# start, end (POSIX seconds), side (+1 long, -1 short), outcome net of fees (+1 won, -1 lost, 0 still open)
type Interval = tuple[float, float, int, int]


class Performance:
    """Trading results of every manager, each named `strategy / manager`."""

    def __init__(self, managers: dict[str, Manager], fee: FeeModel):
        self.managers = managers
        self.fee = fee

    def table(self) -> str:
        """
        Ranked by equity (realized capital). `sharpe` is per trade, not annualized,
        and shown from two closed trades. Combinations (named `strategy / manager`)
        with a negative sharpe are left out of the table and only summarized below
        it, by strategy and by manager; other rows (such as a collaborator) always show.
        """
        rows = []
        losing: list[str] = []
        width = max(map(len, self.managers), default=len("strategy / manager")) + 2

        for name, manager in self.managers.items():
            stats = manager.stats

            if (' / ' in name) and (stats.exits >= 2) and (stats.sharpe < 0):
                losing.append(name)

            elif stats.entries or ' / ' not in name:
                rows.append((manager.capital, name))

        header = (
            f'{"strategy / manager":<{width}}{"equity":>9}{"return%":>9}{"realized%":>10}{"open%":>8}'
            f'{"entries":>8}{"closed":>7}{"sharpe":>8}{"holding":>10}'
        )
        lines = [header, '-' * len(header)]

        for equity, name in sorted(rows, reverse=True):
            manager = self.managers[name]
            stats = manager.stats
            sharpe = f'{stats.sharpe:.2f}' if stats.exits >= 2 else '-'
            holding = '-' if manager.position is None else str(manager.position.duration).split('.')[0]
            lines.append(
                f'{name:<{width}}{equity:>9.5f}{(equity - 1) * 100:>8.3f}%{(manager.capital - 1) * 100:>9.3f}%'
                f'{(equity - manager.capital) * 100:>7.3f}%{stats.entries:>8}{stats.exits:>7}{sharpe:>8}{holding:>10}'
            )

        if losing:
            strategies = Counter(name.split(' / ')[0] for name in losing)
            managers = Counter(name.split(' / ')[1] for name in losing)

            lines.append("")
            lines.append(
                f'{len(losing)} losing combinations (negative sharpe):\n'
                f'- strategies: {", ".join(f"{s} x{n}" for s, n in strategies.most_common())}\n'
                f'- managers: {", ".join(f"{m} x{n}" for m, n in managers.most_common())}'
            )

        if idle := len(self.managers) - len(rows) - len(losing):
            lines.append("")
            lines.append(f'{idle} combinations have not traded yet')

        return '\n'.join(lines)


def _merge(intervals: list[Interval]) -> list[list[float]]:
    """The union of `intervals` as disjoint [start, end] pairs (sides ignored)."""
    merged: list[list[float]] = []

    for start, end, *_ in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)

        else:
            merged.append([start, end])

    return merged


def _length(intervals: list[Interval]) -> float:
    return sum(end - start for start, end in _merge(intervals))


def _sides(intervals: list[Interval]) -> dict[int, list[list[float]]]:
    return {side: _merge([i for i in intervals if i[2] == side]) for side in (1, -1)}


def _unique(intervals: list[Interval], tolerance: float) -> int:
    """
    Positions on the same side entered within `tolerance` seconds of each other
    (chained) count as one trade.
    """
    count = 0

    for side in (1, -1):
        entries = sorted(start for start, _, s, _ in intervals if s == side)
        count += sum(1 for i, entry in enumerate(entries) if i == 0 or entry - entries[i - 1] > tolerance)

    return count


def _shared(a: list[Interval], b: list[Interval]) -> float:
    """The time `a` and `b` both hold a position on the same side."""
    total = 0.0
    sides_a, sides_b = _sides(a), _sides(b)

    for side in (1, -1):
        x, y, i, j = sides_a[side], sides_b[side], 0, 0

        while i < len(x) and j < len(y):
            total += max(min(x[i][1], y[j][1]) - max(x[i][0], y[j][0]), 0.0)

            if x[i][1] < y[j][1]:
                i += 1

            else:
                j += 1

    return total


class Activity:
    """
    When each combination holds a position, read from the managers once per
    tick (`observe`). `coverage` is the share of the recorded time (gaps longer
    than `gap` excluded) in which at least one combination holds a position,
    overlaps counted once. Combinations are clustered by how alike they act:
    their similarity is the time both hold the same side divided by the time
    either holds anything (opposite sides count as different), and clusters are
    cut at `similarity` (average linkage). Within a cluster, or across all,
    positions on the same side entered within `same_trade` of each other count
    as one unique trade - the number of distinct trades the combinations make
    together. Both are also given for the winning and the losing positions
    alone (net of fees; positions still open are in neither), so a unique trade
    whose members ended differently counts once on each side.
    """

    def __init__(
        self,
        managers: dict[str, Manager],
        gap: dt.timedelta,
        similarity: float = 0.5,
        same_trade: dt.timedelta = dt.timedelta(minutes=15)
    ):
        self.managers = managers
        self.gap = gap.total_seconds()
        self.similarity = similarity
        self.same_trade = same_trade.total_seconds()
        self.elapsed = 0.0
        self.intervals: dict[str, list[Interval]] = {name: [] for name in managers}
        self._open: dict[str, Position | None] = dict.fromkeys(managers)
        self._last: float | None = None

    @staticmethod
    def _interval(position: Position, end: dt.datetime, outcome: int) -> Interval:
        side = 1 if position.entry.side == LONG else -1
        return position.entry.trade.timestamp.timestamp(), end.timestamp(), side, outcome

    def observe(self, features: Features) -> None:
        now = features.timestamp.timestamp()

        if (self._last is not None) and (0 < now - self._last <= self.gap):
            self.elapsed += now - self._last

        self._last = now

        for name, manager in self.managers.items():
            held = self._open[name]

            if (held is not None) and (held.exit is not None):
                outcome = 1 if held.returns(manager.fee) > 1 else -1
                self.intervals[name].append(self._interval(held, held.exit.trade.timestamp, outcome))
                held = None

            if (manager.position is not None) and (manager.position is not held):
                held = manager.position

            self._open[name] = held

    def positions(self, name: str) -> list[Interval]:
        """Closed positions, and the open one up to the last observed moment."""
        held = self._open[name]

        if held is None:
            return self.intervals[name]

        return self.intervals[name] + [self._interval(held, dt.datetime.fromtimestamp(self._last, dt.UTC), 0)]

    def coverage(self, intervals: list[Interval]) -> float:
        return _length(intervals) / self.elapsed if self.elapsed else 0.0

    def split(self, intervals: list[Interval]) -> tuple[str, str, str]:
        """Unique trades and coverage of all, winning and losing positions, formatted."""
        won = [i for i in intervals if i[3] > 0]
        lost = [i for i in intervals if i[3] < 0]

        return tuple(
            f'{_unique(part, self.same_trade)} unique trades, {self.coverage(part):.1%} of the time'
            for part in (intervals, won, lost)
        )

    def clusters(self) -> list[list[str]]:
        names = [name for name in self.managers if self.positions(name)]

        if len(names) < 2:
            return [names] if names else []

        positions = [self.positions(name) for name in names]
        lengths = [_length(p) for p in positions]
        distance = np.zeros((len(names), len(names)))

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                shared = _shared(positions[i], positions[j])
                union = lengths[i] + lengths[j] - shared
                distance[i, j] = distance[j, i] = 1.0 - (shared / union if union > 0 else 0.0)

        labels = fcluster(linkage(squareform(distance), method='average'), t=1.0 - self.similarity, criterion='distance')
        groups: dict[int, list[str]] = {}

        for name, label in zip(names, labels):
            groups.setdefault(int(label), []).append(name)

        return list(groups.values())

    def report(self, clusters: bool = False) -> str:
        names = [name for name in self.managers if self.positions(name)]
        everything = [i for name in names for i in self.positions(name)]
        most = max((len(self.positions(name)) for name in names), default=0)
        total, won, lost = self.split(everything)

        lines = [
            f'activity over {self.elapsed / 3600:.1f} h, {len(names)} combinations traded '
            f'(the most trades by one combination: {most})',
            f'  all:     {total}',
            f'  winning: {won} (net of fees)',
            f'  losing:  {lost}'
        ]

        if clusters:
            groups = self.clusters()
            members = {id(group): [i for name in group for i in self.positions(name)] for group in groups}
            lines.append(f'{len(groups)} clusters of combinations that act alike (similarity >= {self.similarity}):')

            for k, group in enumerate(sorted(groups, key=lambda g: -_unique(members[id(g)], self.same_trade)), 1):
                total, won, lost = self.split(members[id(group)])
                lines.append(f'  {k}. {", ".join(group)}')
                lines.append(f'       all: {total}; winning: {won}; losing: {lost}')

        return '\n'.join(lines)
