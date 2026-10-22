from datetime import datetime, timedelta, timezone

from metatwin_guard import MetaTwinGuard, SoftwareSensor, deterministic_private_key
from metatwin_guard.generator import normal_features
import random

T0 = datetime(2026, 8, 23, tzinfo=timezone.utc)


def make_sensor(sid="s-test", seed=1):
    return SoftwareSensor(sid, "A", f"A/{sid}", deterministic_private_key(sid, seed))


def make_stream(sensor, n, phase="baseline", seed=7, start=0):
    rng = random.Random(seed)
    return [
        sensor.emit(normal_features(rng, transients=False), T0 + timedelta(seconds=start + i), 45.0, "test", phase)
        for i in range(n)
    ]


def fitted_guard(sensor, n=60):
    guard = MetaTwinGuard({sensor.sensor_id: sensor.private_key.public_key()}, seed=1)
    for ev in make_stream(sensor, n):
        guard.process(ev)
    guard.fit_baseline()
    return guard
