#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


style = load_module("academic_style_audit", SKILL_DIR / "scripts" / "academic_style_audit.py")
terms = load_module(
    "academic_terminology_audit",
    SKILL_DIR / "scripts" / "academic_terminology_audit.py",
)


class AcademicStyleAuditTests(unittest.TestCase):
    def test_routes_chinese_with_embedded_model_name(self):
        branch, ratio, cjk, latin = style.route("本文使用 Transformer 处理输入，并报告实验结果。")
        self.assertEqual(branch, "zh")
        self.assertGreater(cjk, latin)
        self.assertGreaterEqual(ratio, 0.5)

    def test_routes_english(self):
        self.assertEqual(style.route("The model reduces latency under the stated setting.")[0], "en")

    def test_masks_code_math_quote_and_reference_section(self):
        text = 'Claim. `As an AI` $x=1$. "Here is the revised version."\n## References\nAs requested.'
        report = style.analyze(text)
        self.assertEqual(report["leaks"], [])
        self.assertEqual(report["route"]["branch"], "en")

    def test_reports_process_leak_as_candidate_only(self):
        hits = style.leak_scan("Here is the revised version. The result remained unchanged.")
        self.assertEqual(hits[0]["rule"], "en.editor_preface")
        self.assertEqual(hits[0]["status"], "candidate_only")

    def test_reports_contrast_without_deciding_rewrite(self):
        hits = style.contrast_candidates("This is not a heuristic but a measured result.", "en")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["status"], "candidate_only")

    def test_global_profile_keeps_locations(self):
        profile = style.global_pattern_profile(
            "However, the first result held.\n\nHowever, the second result failed.", "en"
        )
        self.assertEqual(profile["scope"]["paragraphs"], 2)
        self.assertEqual(profile["sentence_initial_markers"]["count"], 2)
        self.assertEqual(profile["interpretation"], "candidate_only_no_authorship_or_quality_verdict")

    def test_cli_json_contains_no_authorship_score(self):
        proc = subprocess.run(
            [sys.executable, str(SKILL_DIR / "scripts" / "academic_style_audit.py"), "-", "--json"],
            input="The model may improve accuracy.",
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        self.assertIn("global_patterns", payload)
        self.assertNotIn("score", payload)
        self.assertNotIn("ai_probability", payload)


class AcademicTerminologyAuditTests(unittest.TestCase):
    def setUp(self):
        self.ledger = [
            {
                "concept_id": "c1",
                "canonical_term": "Target-Aware Planner",
                "allowed_forms": ["TAP"],
                "observed_variants": ["target planner"],
                "distinguish_from": ["task planner"],
            }
        ]

    def test_finds_declared_variant_only(self):
        findings = terms.audit_text("The target planner uses TAP.", self.ledger)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["canonical_term"], "Target-Aware Planner")

    def test_ignores_variant_in_protected_spans(self):
        text = 'Prior work called it "target planner". Use `target planner` and $target planner$.'
        self.assertEqual(terms.audit_text(text, self.ledger), [])

    def test_does_not_merge_distinct_term(self):
        self.assertEqual(terms.audit_text("The task planner is a separate baseline.", self.ledger), [])

    def test_rejects_incomplete_ledger(self):
        with self.assertRaises(ValueError):
            terms.validate_ledger([{"concept_id": "c1"}])

    def test_cli_exit_codes_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text_path = root / "paper.txt"
            ledger_path = root / "terms.json"
            text_path.write_text("The target planner is evaluated.", encoding="utf-8")
            ledger_path.write_text(json.dumps({"terms": self.ledger}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SKILL_DIR / "scripts" / "academic_terminology_audit.py"),
                    str(text_path),
                    "--ledger",
                    str(ledger_path),
                    "--json",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(json.loads(proc.stdout)["finding_count"], 1)

    def test_cli_returns_zero_when_no_variant_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text_path = root / "paper.txt"
            ledger_path = root / "terms.json"
            text_path.write_text("The Target-Aware Planner uses TAP.", encoding="utf-8")
            ledger_path.write_text(json.dumps(self.ledger), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SKILL_DIR / "scripts" / "academic_terminology_audit.py"),
                    str(text_path),
                    "--ledger",
                    str(ledger_path),
                    "--json",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(json.loads(proc.stdout)["finding_count"], 0)

    def test_cli_returns_two_for_invalid_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text_path = root / "paper.txt"
            ledger_path = root / "terms.json"
            text_path.write_text("Text.", encoding="utf-8")
            ledger_path.write_text("{}", encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SKILL_DIR / "scripts" / "academic_terminology_audit.py"),
                    str(text_path),
                    "--ledger",
                    str(ledger_path),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("terminology audit error", proc.stderr)


if __name__ == "__main__":
    unittest.main()
