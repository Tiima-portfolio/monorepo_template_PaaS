import copy

from factory.policy import load_policy
from factory.simulate import simulate, table


def cfg(**over):
    c = {**load_policy("simulation"), **{k: v for k, v in load_policy("queue").items() if k in ("hold_at_depth", "max_depth")}}
    c = copy.deepcopy(c)
    for path, value in over.items():
        node = c
        *parents, leaf = path.split("__")
        for k in parents:
            node = node[k]
        node[leaf] = value
    return c


def test_the_same_seed_gives_the_same_day():
    assert simulate(300, cfg(), seed=3) == simulate(300, cfg(), seed=3)


def test_every_pr_is_merged_or_still_waiting():
    r = simulate(300, cfg(), seed=1)
    assert r.merged + r.pending == 300
    assert r.merged > 0


def test_a_light_day_without_failures_drains_the_queue():
    quiet = cfg(queue__defect_rate=0.0, queue__flake_rate=0.0, pr__verify_fail_rate=0.0, people__bursts=[])
    r = simulate(100, quiet, seed=1)
    assert r.pending == 0
    assert r.totals["rebuild_share"] == 0
    assert r.latency["queue"][1] < 120


def test_a_burst_makes_the_queue_wait():
    calm = simulate(300, cfg(people__bursts=[]), seed=1)
    burst = simulate(300, cfg(), seed=1)
    assert burst.latency["queue"][1] > calm.latency["queue"][1]


def test_failures_cause_rebuilds():
    clean = simulate(500, cfg(queue__defect_rate=0.0, queue__flake_rate=0.0), seed=1)
    broken = simulate(500, cfg(queue__defect_rate=0.15), seed=1)
    assert clean.totals["rebuild_share"] == 0
    assert broken.totals["rebuild_share"] > 0.05


def test_more_parallel_entries_merge_faster_under_load():
    narrow = simulate(1000, cfg(queue__entries_building=2), seed=1)
    wide = simulate(1000, cfg(queue__entries_building=10, queue__max_entries_to_merge=10), seed=1)
    assert wide.latency["queue"][1] < narrow.latency["queue"][1]


def test_saturation_never_exceeds_the_pool():
    r = simulate(1500, cfg(), seed=1)
    assert r.saturation["pr_pool_peak"] <= 1 and r.saturation["queue_pool_peak"] <= 1


def test_the_table_has_a_row_per_load():
    out = table([simulate(300, cfg(), seed=1), simulate(500, cfg(), seed=1)])
    assert out.count("\n") == 3
    assert "| 300 |" in out and "| 500 |" in out
