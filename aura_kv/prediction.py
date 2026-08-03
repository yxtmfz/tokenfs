from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from math import exp

from .core import AccessEvent, Prediction


class AccessPredictor:
    name = "base"

    def observe(self, event: AccessEvent) -> None:
        raise NotImplementedError

    def predict(self, cache_key: str, now: float, nodes: list[str]) -> Prediction:
        raise NotImplementedError


@dataclass
class EWMAAccessPredictor(AccessPredictor):
    horizon_seconds: float = 600.0
    tau_seconds: float = 600.0
    min_confidence_samples: int = 5
    name: str = "EWMA"
    _events: dict[str, deque[AccessEvent]] = field(default_factory=lambda: defaultdict(deque))

    def observe(self, event: AccessEvent) -> None:
        history = self._events[event.cache_key]
        history.append(event)
        cutoff = event.timestamp - self.tau_seconds * 8
        while history and history[0].timestamp < cutoff:
            history.popleft()

    def predict(self, cache_key: str, now: float, nodes: list[str]) -> Prediction:
        history = self._events.get(cache_key, deque())
        scores = {node: 0.0 for node in nodes}
        for event in history:
            scores[event.node_id] = scores.get(event.node_id, 0.0) + exp(
                -(now - event.timestamp) / max(1.0, self.tau_seconds)
            )
        total = sum(scores.values())
        future = {
            node: score * self.horizon_seconds / max(1.0, self.tau_seconds)
            for node, score in scores.items()
        }
        if history:
            intervals = [
                history[i].timestamp - history[i - 1].timestamp
                for i in range(1, len(history))
                if history[i].timestamp >= history[i - 1].timestamp
            ]
            next_access = sum(intervals) / len(intervals) if intervals else self.horizon_seconds
            last_gap = max(0.0, now - history[-1].timestamp)
            cold_probability = min(1.0, last_gap / max(1.0, self.horizon_seconds))
        else:
            next_access = self.horizon_seconds
            cold_probability = 1.0
        confidence = min(1.0, len(history) / max(1, self.min_confidence_samples))
        active_nodes = sum(1 for score in scores.values() if score > 0)
        cross_node_sharedness = 0.0 if active_nodes <= 1 or total <= 0 else 1.0 - max(scores.values()) / total
        return Prediction(
            future_hits_by_node=future,
            next_access_seconds=next_access,
            cold_probability=cold_probability,
            confidence=confidence,
            cross_node_sharedness=cross_node_sharedness,
        )


@dataclass
class LastAccessPredictor(AccessPredictor):
    horizon_seconds: float = 600.0
    name: str = "LastAccess"
    _last_node: dict[str, str] = field(default_factory=dict)
    _last_time: dict[str, float] = field(default_factory=dict)

    def observe(self, event: AccessEvent) -> None:
        self._last_node[event.cache_key] = event.node_id
        self._last_time[event.cache_key] = event.timestamp

    def predict(self, cache_key: str, now: float, nodes: list[str]) -> Prediction:
        future = {node: 0.0 for node in nodes}
        node = self._last_node.get(cache_key)
        if node is not None:
            future[node] = 1.0
        last = self._last_time.get(cache_key, now - self.horizon_seconds)
        return Prediction(
            future_hits_by_node=future,
            next_access_seconds=max(0.0, now - last),
            cold_probability=min(1.0, max(0.0, now - last) / self.horizon_seconds),
            confidence=0.5 if node else 0.0,
        )


@dataclass
class MovingAveragePredictor(EWMAAccessPredictor):
    name: str = "MovingAverage"

    def predict(self, cache_key: str, now: float, nodes: list[str]) -> Prediction:
        history = self._events.get(cache_key, deque())
        cutoff = now - self.tau_seconds
        counts = {node: 0.0 for node in nodes}
        for event in history:
            if event.timestamp >= cutoff:
                counts[event.node_id] = counts.get(event.node_id, 0.0) + 1.0
        future = {
            node: count * self.horizon_seconds / max(1.0, self.tau_seconds)
            for node, count in counts.items()
        }
        total = sum(counts.values())
        active = sum(1 for count in counts.values() if count > 0)
        return Prediction(
            future_hits_by_node=future,
            next_access_seconds=self.horizon_seconds / max(1.0, total) if total else self.horizon_seconds,
            cold_probability=1.0 if total == 0 else max(0.0, 1.0 - total / self.min_confidence_samples),
            confidence=min(1.0, total / max(1, self.min_confidence_samples)),
            cross_node_sharedness=0.0 if active <= 1 or total <= 0 else 1.0 - max(counts.values()) / total,
        )

