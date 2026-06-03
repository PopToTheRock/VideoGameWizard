import math

from eval import metrics


def test_rank_of_is_one_based_and_none_when_absent():
    ranked = ["a", "b", "c"]
    assert metrics.rank_of(ranked, "a") == 1
    assert metrics.rank_of(ranked, "c") == 3
    assert metrics.rank_of(ranked, "z") is None


def test_hit_at_k_respects_the_cutoff():
    ranked = ["a", "b", "c", "d"]
    assert metrics.hit_at_k(ranked, "c", k=3) is True
    assert metrics.hit_at_k(ranked, "c", k=2) is False  # c is at rank 3
    assert metrics.hit_at_k(ranked, "z", k=4) is False


def test_reciprocal_rank_values():
    ranked = ["a", "b", "c"]
    assert metrics.reciprocal_rank(ranked, "a") == 1.0
    assert metrics.reciprocal_rank(ranked, "b") == 0.5
    assert metrics.reciprocal_rank(ranked, "z") == 0.0  # not retrieved


def test_ndcg_is_one_at_rank_one_and_zero_when_missing():
    ranked = ["gold", "b", "c"]
    assert metrics.ndcg_at_k(ranked, "gold", k=5) == 1.0
    assert metrics.ndcg_at_k(["x", "gold"], "gold", k=5) == 1.0 / math.log2(3)
    # Present in the list but below the cutoff -> 0.
    assert metrics.ndcg_at_k(["x", "y", "gold"], "gold", k=2) == 0.0


def test_mean_handles_booleans_and_empty():
    assert metrics.mean([True, False, True, False]) == 0.5
    assert metrics.mean([]) == 0.0


def test_aggregate_produces_expected_keys_and_values():
    # Two questions: gold at rank 1, and gold at rank 3.
    rankings = [
        (["g1", "x", "y"], "g1"),
        (["x", "y", "g2"], "g2"),
    ]
    summary = metrics.aggregate(rankings, ks=(1, 3))

    assert set(summary) == {"hit_rate@1", "ndcg@1", "hit_rate@3", "ndcg@3", "mrr"}
    assert summary["hit_rate@1"] == 0.5  # only the first is at rank 1
    assert summary["hit_rate@3"] == 1.0  # both within top 3
    assert summary["mrr"] == (1.0 + 1.0 / 3) / 2  # ranks 1 and 3
