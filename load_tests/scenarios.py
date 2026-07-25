"""
Pre-configured stress test scenarios.

Run with:
    locust -f load_tests/locustfile.py --host=http://localhost:8000 --config load_tests/scenarios.py

Or use these values directly with --users, --spawn-rate, --run-time.
"""

# ── Scenario: 10 concurrent students (smoke test) ─────────────────────
SCENARIO_SMOKE = {
    'users': 10,
    'spawn_rate': 2,
    'run_time': '5m',
}

# ── Scenario: 30 concurrent students ──────────────────────────────────
SCENARIO_30 = {
    'users': 30,
    'spawn_rate': 5,
    'run_time': '10m',
}

# ── Scenario: 50 concurrent students ──────────────────────────────────
SCENARIO_50 = {
    'users': 50,
    'spawn_rate': 10,
    'run_time': '15m',
}

# ── Scenario: 70 concurrent students (target) ─────────────────────────
SCENARIO_70 = {
    'users': 70,
    'spawn_rate': 14,
    'run_time': '20m',
}

# ── Scenario: 100 concurrent students ─────────────────────────────────
SCENARIO_100 = {
    'users': 100,
    'spawn_rate': 20,
    'run_time': '30m',
}

# ── Scenario: 150 concurrent students ─────────────────────────────────
SCENARIO_150 = {
    'users': 150,
    'spawn_rate': 30,
    'run_time': '40m',
}

# ── Scenario: 200 concurrent students (stress test) ───────────────────
SCENARIO_200 = {
    'users': 200,
    'spawn_rate': 40,
    'run_time': '45m',
}

ALL_SCENARIOS = {
    'smoke': SCENARIO_SMOKE,
    '30': SCENARIO_30,
    '50': SCENARIO_50,
    '70': SCENARIO_70,
    '100': SCENARIO_100,
    '150': SCENARIO_150,
    '200': SCENARIO_200,
}
