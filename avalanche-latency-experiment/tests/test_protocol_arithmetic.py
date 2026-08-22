"""The campaign arithmetic and the closed-form tables of the protocol.

These tests pin the numbers that appear in the article text. If a protocol
amendment changes one of them, the test fails and the amendment has to be
deliberate.
"""

import pytest

from alp import config, theory


def test_full_campaign_matches_the_protocol():
    p = config.FULL
    assert p.n_runs == 750                    # equation (1)
    assert p.t_run_s == 420                   # equation (2)
    assert p.wall_clock_s == 315_000          # equation (3)
    assert p.wall_clock_s / 3600 == pytest.approx(87.50)
    assert p.n_scheduled_tx == 34_875_000     # equation (4)


def test_every_profile_keeps_all_factor_levels_where_it_claims_to():
    for name in ("full", "demo"):
        p = config.get_profile(name)
        assert p.configs == config.CONFIGS
        assert p.topologies == config.TOPOLOGIES
        assert p.loads_tps == config.LOADS_TPS


def test_nominal_block_rate_table():
    table = theory.table_nominal_rate().set_index("B_ms")
    assert table.loc[1000, "f_B_blocks_per_s"] == pytest.approx(1.0)
    assert table.loc[250, "f_B_blocks_per_s"] == pytest.approx(4.0)
    assert table.loc[250, "blocks_per_300s"] == pytest.approx(1200)
    assert table.loc[500, "relative_to_slowest"] == pytest.approx(2.0)


def test_block_wait_quantiles_are_uniform():
    table = theory.table_block_wait().set_index("B_ms")
    for b in (1000, 750, 500, 250):
        assert table.loc[b, "E_W_ms"] == pytest.approx(b / 2)
        assert table.loc[b, "p50_ms"] == pytest.approx(0.50 * b)
        assert table.loc[b, "p95_ms"] == pytest.approx(0.95 * b)
        assert table.loc[b, "p99_ms"] == pytest.approx(0.99 * b)


def test_tx_per_block_requirement():
    table = theory.table_tx_per_block().set_index("load_tps")
    assert table.loc[400, "B_1000ms"] == pytest.approx(400.0)
    assert table.loc[400, "B_250ms"] == pytest.approx(100.0)
    assert table.loc[25, "B_750ms"] == pytest.approx(18.75)


def test_tx_per_run_table():
    table = theory.table_tx_per_run().set_index("load_tps")
    assert table.loc[400, "tx_per_300s"] == 120_000
    assert table.loc[400, "tx_per_10_repeats"] == 1_200_000
    assert table.loc[25, "per_client_tps"] == pytest.approx(1.0)


def test_campaign_arithmetic_table_is_self_consistent():
    table = theory.campaign_arithmetic(config.FULL).set_index("equation")
    assert table.loc[1, "value"] == 750
    assert table.loc[4, "value"] == 34_875_000
