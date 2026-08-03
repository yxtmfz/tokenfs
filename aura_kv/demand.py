from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from math import exp, sqrt

from .core import AccessEvent


@dataclass
class DemandEstimate:
    cache_key: str
    node_id: str
    horizon_seconds: float
    mean: float
    lower: float
    upper: float
    variance: float
    estimator: str
    breakdown: dict[str, float | str]


class DemandEstimator:
    name = "base"

    def observe(self, event: AccessEvent) -> None:
        raise NotImplementedError

    def estimate(self, cache_key: str, node_id: str, now: float, horizon_seconds: float) -> DemandEstimate:
        raise NotImplementedError

    def estimate_all(self, cache_key: str, nodes: list[str], now: float, horizon_seconds: float) -> dict[str, DemandEstimate]:
        return {node: self.estimate(cache_key, node, now, horizon_seconds) for node in nodes}


@dataclass
class EffectivePrefixDemandTracker:
    """Tracks effective demand while de-duplicating each request per cache key."""

    _events: dict[str, dict[str, deque[AccessEvent]]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(deque)))
    _seen_requests: set[tuple[str, str, str]] = field(default_factory=set)

    def observe(self, event: AccessEvent) -> None:
        effective_keys = [event.cache_key]
        if event.parent_cache_key and event.parent_cache_key != event.cache_key:
            effective_keys.append(event.parent_cache_key)
        for cache_key in effective_keys:
            dedupe_key = (event.request_id, event.node_id, cache_key)
            if dedupe_key in self._seen_requests:
                continue
            self._seen_requests.add(dedupe_key)
            self._events[cache_key][event.node_id].append(event)

    def events(self, cache_key: str, node_id: str) -> deque[AccessEvent]:
        return self._events.get(cache_key, {}).get(node_id, deque())


@dataclass
class EWMADemandEstimator(DemandEstimator):
    tau_seconds: float = 600.0
    horizon_seconds: float = 600.0
    min_samples_for_stable_bounds: int = 5
    name: str = "EWMADemand"
    tracker: EffectivePrefixDemandTracker = field(default_factory=EffectivePrefixDemandTracker)

    def observe(self, event: AccessEvent) -> None:
        self.tracker.observe(event)

    def estimate(self, cache_key: str, node_id: str, now: float, horizon_seconds: float | None = None) -> DemandEstimate:
        horizon = self.horizon_seconds if horizon_seconds is None else horizon_seconds
        history = self.tracker.events(cache_key, node_id)
        weighted_count = 0.0
        for event in history:
            weighted_count += exp(-(now - event.timestamp) / max(1.0, self.tau_seconds))
        mean = horizon * weighted_count / max(1.0, self.tau_seconds)
        samples = len(history)
        # EWMA has no posterior distribution, so use conservative heuristic bounds.
        bound_width = max(1.0, mean ** 0.5) * (1.0 if samples >= self.min_samples_for_stable_bounds else 2.0)
        return DemandEstimate(
            cache_key=cache_key,
            node_id=node_id,
            horizon_seconds=horizon,
            mean=mean,
            lower=max(0.0, mean - bound_width),
            upper=mean + bound_width,
            variance=bound_width * bound_width,
            estimator=self.name,
            breakdown={
                "weighted_count": weighted_count,
                "tau_seconds": self.tau_seconds,
                "samples": float(samples),
                "method": "ewma",
            },
        )


@dataclass
class GammaPoissonDemandEstimator(DemandEstimator):
    a0: float = 1.0
    b0: float = 600.0
    tau_seconds: float = 600.0
    horizon_seconds: float = 600.0
    bucket_seconds: float = 60.0
    delta: float = 0.10
    name: str = "GammaPoissonDemand"
    tracker: EffectivePrefixDemandTracker = field(default_factory=EffectivePrefixDemandTracker)

    def observe(self, event: AccessEvent) -> None:
        self.tracker.observe(event)

    def estimate(self, cache_key: str, node_id: str, now: float, horizon_seconds: float | None = None) -> DemandEstimate:
        horizon = self.horizon_seconds if horizon_seconds is None else horizon_seconds
        events = list(self.tracker.events(cache_key, node_id))
        buckets: dict[int, int] = defaultdict(int)
        for event in events:
            bucket = int(event.timestamp // max(1.0, self.bucket_seconds))
            buckets[bucket] += 1
        weighted_count = 0.0
        weighted_exposure = 0.0
        for bucket, count in buckets.items():
            bucket_time = (bucket + 0.5) * self.bucket_seconds
            weight = exp(-(now - bucket_time) / max(1.0, self.tau_seconds))
            weighted_count += weight * count
            weighted_exposure += weight * self.bucket_seconds
        a = self.a0 + weighted_count
        b = self.b0 + weighted_exposure
        rate_mean = a / max(1e-9, b)
        mean = horizon * rate_mean
        variance = horizon * rate_mean + horizon * horizon * a / max(1e-9, b * b)
        sigma = sqrt(max(0.0, variance))
        kappa = sqrt((1.0 - self.delta) / max(1e-9, self.delta))
        lower = max(0.0, mean - kappa * sigma)
        upper = mean + kappa * sigma
        return DemandEstimate(
            cache_key=cache_key,
            node_id=node_id,
            horizon_seconds=horizon,
            mean=mean,
            lower=lower,
            upper=upper,
            variance=variance,
            estimator=self.name,
            breakdown={
                "weighted_count": weighted_count,
                "weighted_exposure_seconds": weighted_exposure,
                "posterior_a": a,
                "posterior_b": b,
                "rate_per_second": rate_mean,
                "sigma": sigma,
                "cantelli_kappa": kappa,
                "samples": float(len(events)),
            },
        )


@dataclass
class OracleDemandEstimator(DemandEstimator):
    """Uses future trace events. This estimator is only valid for simulation baselines."""

    future_trace: list[AccessEvent] = field(default_factory=list)
    name: str = "OracleDemand"

    def observe(self, event: AccessEvent) -> None:
        return None

    def estimate(self, cache_key: str, node_id: str, now: float, horizon_seconds: float) -> DemandEstimate:
        end = now + horizon_seconds
        seen: set[str] = set()
        count = 0.0
        for event in self.future_trace:
            if event.timestamp < now or event.timestamp > end:
                continue
            effective_keys = [event.cache_key]
            if event.parent_cache_key and event.parent_cache_key != event.cache_key:
                effective_keys.append(event.parent_cache_key)
            if event.node_id == node_id and cache_key in effective_keys and event.request_id not in seen:
                seen.add(event.request_id)
                count += 1.0
        return DemandEstimate(
            cache_key=cache_key,
            node_id=node_id,
            horizon_seconds=horizon_seconds,
            mean=count,
            lower=count,
            upper=count,
            variance=0.0,
            estimator=self.name,
            breakdown={"future_count": count, "method": "oracle_simulation_only"},
        )
