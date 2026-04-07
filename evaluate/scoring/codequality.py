"""
evaluate/scoring/report — run pyscn_scoring and present results.

Calls pyscn_scoring.run(), prints a formatted table to stdout, and writes
the raw result dict to evaluate/scoring/results/score_<timestamp>.json
(and to evaluate/scoring/results/latest.json for easy access).

Usage (standalone):
  python evaluate/scoring/report
  python evaluate/scoring/report <translated_dir> <tt_dir>
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.resolve()
RESULTS_DIR = Path(__file__).parent / "results"
SCORING_DIR = Path(__file__).parent / "codequality"

# Ensure the scoring module is importable
sys.path.insert(0, str(REPO_ROOT))


def _bar(score: float, width: int = 30) -> str:
    filled = int(round(score / 100 * width))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _grade_colour(grade: str) -> str:
    """Return ANSI colour prefix for grade (green A/B, yellow C, red D/F)."""
    colours = {"A": "\033[92m", "B": "\033[92m", "C": "\033[93m", "D": "\033[91m", "F": "\033[91m"}
    reset = "\033[0m"
    return colours.get(grade, "") + grade + reset


def _fmt_row(label: str, score: float, grade: str, weight: float) -> str:
    bar = _bar(score)
    return (
        f"  {label:<22} {bar}  {score:5.1f}/100  "
        f"grade={_grade_colour(grade)}  weight={weight:.0%}"
    )


def _print_report(result: dict) -> None:
    tc = result["translated_code"]
    tt = result["tt_code"]
    ws = result["weighted_score"]
    wg = result["weighted_grade"]

    print()
    print("=" * 70)
    print("  Code Quality Report (pyscn)")
    print("=" * 70)

    print()
    print(_fmt_row("Translated code", tc["health_score"], tc["grade"], tc["weight"]))
    print(_fmt_row("tt translator",   tt["health_score"], tt["grade"], tt["weight"]))

    print()
    print(f"  {'Weighted score':<22} {_bar(ws)}  {ws:5.1f}/100  grade={_grade_colour(wg)}")
    print()

    sub_keys = [
        ("complexity_score",  "Complexity"),
        ("dead_code_score",   "Dead code"),
        ("duplication_score", "Duplication"),
        ("coupling_score",    "Coupling"),
        ("dependency_score",  "Dependencies"),
        ("architecture_score","Architecture"),
    ]
    extra_keys = [
        ("average_complexity",          "avg_complexity"),
        ("code_duplication_percentage", "duplication_%"),
        ("total_files",                 "total_files"),
    ]

    for section_label, data in [("translated code", tc), ("tt translator", tt)]:
        print(f"  --- Sub-scores ({section_label}) ---")
        for key, label in sub_keys:
            v = data.get(key)
            if v is not None:
                print(f"    {label:<20} {v:5.1f}")
        print()
        for key, label in extra_keys:
            v = data.get(key)
            if v is not None:
                print(f"    {label:<20} {v}")
        print()

    if tc.get("error"):
        print(f"\n  [!] translated_code error: {tc['error']}")
    if tt.get("error"):
        print(f"\n  [!] tt_code error: {tt['error']}")

    print()
    print("=" * 70)
    print()


def run(translated_path: Path | None = None, tt_path: Path | None = None) -> dict:
    # Import scoring module — works whether run as script or via `python -m`
    try:
        from evaluate.scoring.codequality.pyscn_scoring import run as score_run  # type: ignore
    except ImportError:
        spec_path = SCORING_DIR / "pyscn_scoring.py"
        import importlib.machinery
        import importlib.util

        loader = importlib.machinery.SourceFileLoader("pyscn_scoring", str(spec_path))
        spec = importlib.util.spec_from_loader("pyscn_scoring", loader)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        score_run = mod.run

    result = score_run(translated_path, tt_path)

    _print_report(result)

    # Persist results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    timestamped = RESULTS_DIR / f"score_{ts}.json"
    latest = RESULTS_DIR / "latest.json"

    payload = {"generated_at": ts, **result}
    text = json.dumps(payload, indent=2)
    timestamped.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")

    print(f"  Results saved to: {timestamped}")
    print(f"  Latest symlink:   {latest}")
    print()

    return result


if __name__ == "__main__":
    args = sys.argv[1:]
    translated_path = Path(args[0]) if len(args) >= 1 else None
    tt_path = Path(args[1]) if len(args) >= 2 else None
    run(translated_path, tt_path)
