"""Unit tests for run_q3_h1_formal_v1.py pure logic (no q3_formal worlds
consumed; no engine runs except tiny development-unit smokes)."""

from __future__ import annotations

import hashlib
import sys
import unittest
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
CODE_DIR = BASE / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from g3 import lifetime_regeneration_v1 as lr  # noqa: E402
from scripts import run_q3_h1_formal_v1 as r  # noqa: E402


class TestFrozenGrid(unittest.TestCase):
    def test_k_grid_exact_seven(self) -> None:
        self.assertEqual([k for k, _ in r.K_VALUES],
                         ["K09", "K09p5", "K10", "K10p5", "K11", "K11p5", "K12"])
        self.assertEqual([Fraction(h) for _, h in r.K_VALUES],
                         [Fraction(9), Fraction(19, 2), Fraction(10),
                          Fraction(21, 2), Fraction(11), Fraction(23, 2),
                          Fraction(12)])

    def test_cell_tokens(self) -> None:
        self.assertEqual(r.cell_id("tier1", "K09"), "tier1__single__K09")
        self.assertEqual(r.cell_id("tier2", "K12"), "tier2__chain__K12")

    def test_bonferroni_frozen(self) -> None:
        self.assertAlmostEqual(r.ALPHA_EACH, 0.05 / 21)
        self.assertAlmostEqual(r.P_LO, 0.05 / 42)
        self.assertAlmostEqual(r.P_HI, 1 - 0.05 / 42)

    def test_analysis_stream_frozen(self) -> None:
        self.assertEqual(r.ANALYSIS_NAMESPACE, "q3_formal_analysis_bootstrap_v1")
        self.assertEqual(r.ANALYSIS_SEED, 40003)
        self.assertEqual(r.BOOTSTRAP_B, 10000)


class TestConfigShape(unittest.TestCase):
    def test_tier1_config(self) -> None:
        cfg = r.make_cell_config("tier1", "K09p5", 0)
        self.assertEqual(cfg.namespace, "q3_formal")
        self.assertEqual(cfg.master_seed, 5)
        self.assertEqual(cfg.replicate_id, 0)
        self.assertEqual(cfg.scenario, "q3_two_shift")
        self.assertEqual(cfg.shifts_per_day, 2)
        self.assertEqual(cfg.shift_length_h, Fraction(19, 2))
        self.assertEqual(cfg.batch_size, 100)
        self.assertIs(cfg.tau_pm, lr.NO_PM_BEFORE_MANDATORY)
        self.assertEqual(cfg.turnover_profile, "1h_literal")

    def test_tier1_tier2_kernel_difference(self) -> None:
        s = r.single_kernel()
        c = r.chain_kernel()
        self.assertNotEqual(s["A"]["alpha"], c["A"]["alpha"])
        # frozen single-test E kernel: closed form with Q1-frozen q_E
        q_e = Fraction("0.062593912407392898")
        e_e = Fraction(2, 100)
        self.assertEqual(s["E"]["alpha"], e_e / (2 * (1 - q_e)))
        self.assertEqual(s["E"]["beta"], e_e / (2 * q_e))

    def test_c15_assertions(self) -> None:
        cfg = r.make_cell_config("tier1", "K12", 199)
        r.assert_c15_cell(cfg, "tier1", "K12")  # must not raise
        with self.assertRaises(AssertionError):
            r.assert_c15_cell(replace(cfg, replicate_id=200), "tier1", "K12")
        with self.assertRaises(AssertionError):
            r.assert_c15_cell(replace(cfg, namespace="pilot"), "tier1", "K12")
        with self.assertRaises(AssertionError):
            r.assert_c15_cell(replace(cfg, shift_length_h=Fraction(9)), "tier1", "K12")
        with self.assertRaises(AssertionError):
            r.assert_c15_cell(replace(cfg, tau_pm=Fraction(198)), "tier1", "K12")


class TestStatistics(unittest.TestCase):
    def test_paired_bootstrap_identical_arrays(self) -> None:
        a = [10.0 + i * 0.1 for i in range(200)]
        ci = r.paired_bootstrap_ci(a, a)
        self.assertAlmostEqual(ci["point_estimate_Delta_T_h"], 0.0, places=9)
        self.assertAlmostEqual(ci["ci_lo_h"], 0.0, places=6)
        self.assertAlmostEqual(ci["ci_hi_h"], 0.0, places=6)

    def test_paired_bootstrap_known_delta(self) -> None:
        a = [100.0 + i for i in range(200)]
        b = [80.0 + i for i in range(200)]
        ci = r.paired_bootstrap_ci(a, b)
        self.assertAlmostEqual(ci["point_estimate_Delta_T_h"], 20.0, places=9)
        self.assertGreater(ci["ci_lo_h"], 0.0)

    def test_recommendation_logic(self) -> None:
        # synthetic aggregates: K09 fastest, K12 slowest, others in between
        from scripts.run_q3_h1_formal_v1 import CellAggregate

        def agg(k_label: str, t_h: Fraction) -> CellAggregate:
            cid = r.cell_id("tier1", k_label)
            return CellAggregate(
                cell=cid, tier="tier1", k_label=k_label, n=200,
                mean_T=t_h, mean_T_days=t_h / Fraction(24),
                mean_S=Fraction(94, 1), mean_PL=Fraction(1, 100),
                mean_PW=Fraction(1, 100),
                mean_YXB={"A": Fraction(1, 2), "B": Fraction(1, 2),
                          "C": Fraction(1, 2), "E": Fraction(1, 2)},
                mean_preventive=Fraction(0), mean_mandatory=Fraction(2, 1),
                mean_random_failures=Fraction(1, 1),
                mean_wasted_fragments=Fraction(0),
                four_cell_totals={"GP": 1, "BP": 1, "GE": 1, "BE": 1},
                pl_pooled_x=2, pw_pooled_x=2, pl_batch_se=0.1, pw_batch_se=0.1,
                t_batch_se=1.0, t_p50=float(t_h), t_p90=float(t_h),
                quality_pass_count=200, replay_pass_count=200,
            )

        t_h = {"K09": 900, "K09p5": 905, "K10": 910, "K10p5": 915,
               "K11": 920, "K11p5": 925, "K12": 930}
        aggs = {r.cell_id("tier1", k): agg(k, Fraction(v)) for k, v in t_h.items()}
        # synthetic pairwise: all pairs vs K09 far below 0
        pairs = []
        idx = 0
        for i, (k1, v1) in enumerate(t_h.items()):
            for j, (k2, v2) in enumerate(list(t_h.items())[i + 1:], start=i + 1):
                idx += 1
                pairs.append({
                    "pair_id": f"P{idx:02d}", "k1": k1, "k2": k2,
                    "delta_T_h": float(v1 - v2),
                    "ci_lo_h": float(v1 - v2 - 2), "ci_hi_h": float(v1 - v2 + 2),
                    "interpretation": "CI includes 0",
                })
        rec = r.recommendation("tier1", aggs, pairs)
        self.assertEqual(rec["k_star"], "K09")
        self.assertIn("scope", rec)
        self.assertIn("七个 K", rec["scope"])

    def test_recommendation_sign_semantics_kk_lt_kstar(self) -> None:
        # k_star = K10; K09 (lexicographically earlier, kk < k_star) is
        # significantly SLOWER: pair (K09, K10) delta=T(K09)-T(K10)>0 with
        # CI entirely >0 -> K09 must NOT be co-best and strong stays true
        # (for this pair).  K12 indistinguishable -> co-best.
        from scripts.run_q3_h1_formal_v1 import CellAggregate

        def agg(k_label: str, t_h: Fraction) -> CellAggregate:
            cid = r.cell_id("tier1", k_label)
            return CellAggregate(
                cell=cid, tier="tier1", k_label=k_label, n=200,
                mean_T=t_h, mean_T_days=t_h / Fraction(24),
                mean_S=Fraction(94, 1), mean_PL=Fraction(1, 100),
                mean_PW=Fraction(1, 100),
                mean_YXB={"A": Fraction(1, 2), "B": Fraction(1, 2),
                          "C": Fraction(1, 2), "E": Fraction(1, 2)},
                mean_preventive=Fraction(0), mean_mandatory=Fraction(2, 1),
                mean_random_failures=Fraction(1, 1),
                mean_wasted_fragments=Fraction(0),
                four_cell_totals={"GP": 1, "BP": 1, "GE": 1, "BE": 1},
                pl_pooled_x=2, pw_pooled_x=2, pl_batch_se=0.1, pw_batch_se=0.1,
                t_batch_se=1.0, t_p50=float(t_h), t_p90=float(t_h),
                quality_pass_count=200, replay_pass_count=200,
            )

        t_h = {"K09": 910, "K09p5": 915, "K10": 900, "K10p5": 905,
               "K11": 920, "K11p5": 925, "K12": 902}  # K12 close to K10
        aggs = {r.cell_id("tier1", k): agg(k, Fraction(v)) for k, v in t_h.items()}
        labels = [k for k, _ in r.K_VALUES]
        pairs = []
        idx = 0
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                idx += 1
                k1, k2 = labels[i], labels[j]
                d = float(t_h[k1] - t_h[k2])
                # CI width 2; K09 vs K10: d=+10 -> CI [8,12] entirely >0.
                # K10 vs K12: d=-2 -> CI [-4,0] includes 0.
                pairs.append({
                    "pair_id": f"P{idx:02d}", "k1": k1, "k2": k2,
                    "delta_T_h": d, "ci_lo_h": d - 2, "ci_hi_h": d + 2,
                    "interpretation": "x",
                })
        rec = r.recommendation("tier1", aggs, pairs)
        self.assertEqual(rec["k_star"], "K10")
        # K09: pair (K09, K10), k_star == b, lo=8 > 0 -> faster confirmed,
        # K09 NOT co-best.  K10p5: d=-5 -> CI [-7,-3] -> k_star faster, not
        # co-best.  K12: d=-2 -> CI includes 0 -> co-best.  K11/K11p5: d>0
        # and CI >0 -> k_star faster... wait K11=920: pair (K10,K11) d=-20
        # CI <-18 -> k_star faster -> not co-best. K09p5: pair (K09p5,K10)
        # d=+15 CI [13,17] -> k_star==b, lo>0 -> faster -> not co-best.
        self.assertEqual(rec["co_best"], ["K12"])
        self.assertFalse(rec["strong_recommendation"])  # K12 indistinguishable

    def test_cp_one_sided_x0(self) -> None:
        # x=0, n=20000 -> 1 - 0.05^(1/20000)
        upper = r.clopper_pearson_one_sided_upper(0, 20000)
        expected = 1.0 - 0.05 ** (1.0 / 20000)
        self.assertAlmostEqual(upper, expected, places=9)


class TestPreflightShape(unittest.TestCase):
    def test_preflight_config_smoke(self) -> None:
        # tiny development-unit batch via the preflight config builder (no
        # q3_formal world is consumed).
        from scripts.run_q3_h1_preflight_v1 import dev_config, run_sha
        cfg = dev_config("K09", 0)
        sha, metrics = run_sha(cfg)
        self.assertEqual(len(sha), 64)
        self.assertGreater(float(Fraction(metrics["T"])), 0)


class TestRecommendationWording(unittest.TestCase):
    """Q3-H1-E1: strong-recommendation wording must be orientation-neutral."""

    def _make_aggs_and_pairs(self, t_h: dict[str, float]) -> tuple:
        from scripts.run_q3_h1_formal_v1 import CellAggregate

        def agg(k_label: str, t: float) -> CellAggregate:
            cid = r.cell_id("tier1", k_label)
            return CellAggregate(
                cell=cid, tier="tier1", k_label=k_label, n=200,
                mean_T=Fraction(int(t * 100), 100),
                mean_T_days=Fraction(int(t * 100), 2400),
                mean_S=Fraction(94, 1), mean_PL=Fraction(1, 100),
                mean_PW=Fraction(1, 100),
                mean_YXB={"A": Fraction(1, 2), "B": Fraction(1, 2),
                          "C": Fraction(1, 2), "E": Fraction(1, 2)},
                mean_preventive=Fraction(0), mean_mandatory=Fraction(2, 1),
                mean_random_failures=Fraction(1, 1),
                mean_wasted_fragments=Fraction(0),
                four_cell_totals={"GP": 1, "BP": 1, "GE": 1, "BE": 1},
                pl_pooled_x=2, pw_pooled_x=2, pl_batch_se=0.1, pw_batch_se=0.1,
                t_batch_se=1.0, t_p50=t, t_p90=t,
                quality_pass_count=200, replay_pass_count=200,
            )

        aggs = {r.cell_id("tier1", k): agg(k, v) for k, v in t_h.items()}
        labels = [k for k, _ in r.K_VALUES]
        pairs = []
        idx = 0
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                idx += 1
                k1, k2 = labels[i], labels[j]
                d = t_h[k1] - t_h[k2]
                pairs.append({
                    "pair_id": f"P{idx:02d}", "k1": k1, "k2": k2,
                    "delta_T_h": d, "ci_lo_h": d - 2, "ci_hi_h": d + 2,
                    "interpretation": "x",
                })
        return aggs, pairs

    def test_wording_is_orientation_neutral(self) -> None:
        # k* = K12 is the RIGHT end of every pair; faster means CI > 0.
        t_h = {"K09": 900, "K09p5": 890, "K10": 880, "K10p5": 870,
               "K11": 860, "K11p5": 850, "K12": 800}
        aggs, pairs = self._make_aggs_and_pairs(t_h)
        rec = r.recommendation("tier1", aggs, pairs)
        self.assertEqual(rec["k_star"], "K12")
        self.assertTrue(rec["strong_recommendation"])
        self.assertNotIn("完全 <0", rec["wording"])       # not hard-coded left-side
        self.assertIn("orientation-neutral", rec["wording"])  # explicit neutrality
        self.assertIn("CI<0", rec["wording"])  # documents both directions

    def test_case_a_left_end_kstar(self) -> None:
        # k* = K09 at the LEFT end of every pair; faster means CI < 0.
        t_h = {"K09": 800, "K09p5": 850, "K10": 860, "K10p5": 870,
               "K11": 880, "K11p5": 890, "K12": 900}
        aggs, pairs = self._make_aggs_and_pairs(t_h)
        rec = r.recommendation("tier1", aggs, pairs)
        self.assertEqual(rec["k_star"], "K09")
        self.assertTrue(rec["strong_recommendation"])
        self.assertEqual(rec["co_best"], [])

    def test_case_b_right_end_kstar(self) -> None:
        # k* = K12 at the RIGHT end; faster means CI > 0 (the actual formal case).
        t_h = {"K09": 900, "K09p5": 890, "K10": 880, "K10p5": 870,
               "K11": 860, "K11p5": 850, "K12": 800}
        aggs, pairs = self._make_aggs_and_pairs(t_h)
        rec = r.recommendation("tier1", aggs, pairs)
        self.assertEqual(rec["k_star"], "K12")
        self.assertTrue(rec["strong_recommendation"])
        self.assertEqual(rec["co_best"], [])

    def test_case_c_ci_contains_zero_goes_to_co_best(self) -> None:
        # K12 (argmin) and K11.5 indistinguishable -> K11.5 co-best, no strong.
        t_h = {"K09": 900, "K09p5": 890, "K10": 880, "K10p5": 870,
               "K11": 860, "K11p5": 801, "K12": 800}
        aggs, pairs = self._make_aggs_and_pairs(t_h)
        rec = r.recommendation("tier1", aggs, pairs)
        self.assertEqual(rec["k_star"], "K12")
        self.assertFalse(rec["strong_recommendation"])
        self.assertIn("K11p5", rec["co_best"])


class TestHashDag(unittest.TestCase):
    """Q3-H1-E1: acyclic hash inventory regression (RULE A)."""

    def _build_synthetic_evidence(self, tmp: Path,
                                  bad_manifest_hashes_inventory: bool = False,
                                  bad_inventory_self: bool = False) -> Path:
        import json as _json
        root = tmp / "ev"
        (root / "cells").mkdir(parents=True)
        (root / "cells" / "a.json").write_text('{"x":1}\n', encoding="utf-8")
        (root / "task_package_snapshot.yaml").write_text("k: v\n", encoding="utf-8")
        (root / "family_aggregates.json").write_text('{"m":1}\n', encoding="utf-8")
        outputs = [
            {"path": "cells/a.json", "bytes": 8, "sha256": "x"},
            {"path": "family_aggregates.json", "bytes": 8, "sha256": "x"},
            {"path": "task_package_snapshot.yaml", "bytes": 5, "sha256": "x"},
        ]
        if bad_manifest_hashes_inventory:
            outputs.append({"path": "file_hashes.sha256", "bytes": 1, "sha256": "x"})
        manifest = {
            "hash_inventory_path": "file_hashes.sha256",
            "outputs": outputs,
        }
        (root / "run_manifest.json").write_text(
            _json.dumps(manifest, sort_keys=True), encoding="utf-8"
        )
        # inventory: all files except itself
        lines = []
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.name != "file_hashes.sha256":
                rel = p.relative_to(root).as_posix()
                h = hashlib.sha256(p.read_bytes()).hexdigest()
                lines.append(f"{h}  {rel}")
        if bad_inventory_self:
            lines.append(f"{'0' * 64}  file_hashes.sha256")
        (root / "file_hashes.sha256").write_text(
            "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
        )
        return root

    def test_acyclic_inventory_passes(self) -> None:
        import tempfile
        from scripts.run_q3_h1_formal_v1 import verify_hash_dag
        with tempfile.TemporaryDirectory() as td:
            root = self._build_synthetic_evidence(Path(td))
            report = verify_hash_dag(root)
            self.assertTrue(report["hash_graph_acyclic"])
            self.assertEqual(report["mismatches"], 0)
            self.assertEqual(report["inventory_n"], 4)  # 3 artifacts + manifest

    def test_manifest_must_not_hash_inventory(self) -> None:
        import tempfile
        from scripts.run_q3_h1_formal_v1 import verify_hash_dag
        with tempfile.TemporaryDirectory() as td:
            root = self._build_synthetic_evidence(Path(td), bad_manifest_hashes_inventory=True)
            with self.assertRaises(AssertionError):
                verify_hash_dag(root)

    def test_inventory_must_not_self_hash(self) -> None:
        import tempfile
        from scripts.run_q3_h1_formal_v1 import verify_hash_dag
        with tempfile.TemporaryDirectory() as td:
            root = self._build_synthetic_evidence(Path(td), bad_inventory_self=True)
            with self.assertRaises(AssertionError):
                verify_hash_dag(root)


if __name__ == "__main__":
    unittest.main()
