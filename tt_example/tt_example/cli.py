"""
Minimal example translation tool.

This is the simplest possible tt implementation. It does nothing beyond calling
helptools/setup_ghostfolio_scaffold_for_tt.py to set up the scaffold as the
translation output. No actual TypeScript-to-Python translation is performed.

Use this as a starting point to understand the tt workflow:
  1. The scaffold provides the FastAPI HTTP layer (main.py)
  2. Support modules (models, helpers) provide the interfaces
  3. Your job: translate the TypeScript source into Python that implements
     RoaiPortfolioCalculator.get_symbol_metrics()

See COMPETITION_RULES/RULES.md and PORTFOLIO_CALCULATOR_INTERFACE.md for details.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.resolve()
TRANSLATION_DIR = REPO_ROOT / "translations" / "ghostfolio_pytx"


def cmd_translate(args: argparse.Namespace) -> int:
    output_dir = Path(args.output) if args.output else TRANSLATION_DIR

    # Step 1: Set up the scaffold (copies example + support modules)
    setup_script = REPO_ROOT / "helptools" / "setup_ghostfolio_scaffold_for_tt.py"
    if not setup_script.exists():
        print(f"ERROR: setup script not found: {setup_script}", file=sys.stderr)
        return 1

    print(f"Setting up scaffold → {output_dir}")
    subprocess.run(
        [sys.executable, str(setup_script), "--output", str(output_dir)],
        check=True,
    )

    # Step 2: This is where your translation logic goes.
    # The real tt (in tt/) uses regex-based passes to translate TypeScript
    # source files into Python. This example does nothing — the scaffold
    # alone passes ~30 tests with stub responses.
    print("\nNo translation performed (this is tt_example).")
    print("To build a real translator, see tt/tt/translator.py for reference.")
    print(f"\nDone. Output at {output_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="tt_example",
        description="Minimal example translation tool (scaffold only)",
    )
    sub = parser.add_subparsers(dest="command")

    p_translate = sub.add_parser("translate", help="Set up scaffold (no translation)")
    p_translate.add_argument("-o", "--output", help="Output directory")

    args = parser.parse_args()
    if args.command == "translate":
        return cmd_translate(args)

    parser.print_help()
    return 0
