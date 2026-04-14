"""
Tests for Bug A and Bug B fixes in translator.py.

Bug A: bare private/protected/public field declarations must be stripped.
Bug B: Logger.warn continuation lines (dangling f-strings, strings, ')') must be dropped.
"""
import subprocess
import sys
from pathlib import Path

import pytest

from tt.translator import _translate_line, translate_typescript_content

REPO_ROOT = Path(__file__).parent.parent.parent.resolve()


# ---------------------------------------------------------------------------
# Bug A — private/protected/public field declarations stripped
# ---------------------------------------------------------------------------

class TestBugA:
    def test_private_field_stripped(self):
        assert _translate_line('  private chartDates: string[]') == ''

    def test_protected_field_stripped(self):
        assert _translate_line('  protected foo: number') == ''

    def test_public_field_stripped(self):
        assert _translate_line('  public bar: Big') == ''

    def test_private_field_no_type_stripped(self):
        # Even without explicit type annotation
        assert _translate_line('  private someFlag') == ''

    def test_private_static_readonly_not_stripped(self):
        # Static property — must be translated, not stripped
        result = _translate_line('  private static readonly ENABLE_LOGGING = false')
        assert 'ENABLE_LOGGING' in result
        assert 'private' not in result

    def test_private_method_not_stripped(self):
        # A private method declaration must NOT be stripped — it should become a def
        result = _translate_line('  private calculateSomething() {')
        assert 'def' in result
        assert 'private' not in result

    def test_private_async_method_not_stripped(self):
        result = _translate_line('  private async fetchData() {')
        assert 'def' in result

    def test_public_constructor_not_stripped(self):
        result = _translate_line('  public constructor(activities) {')
        assert 'def' in result or '__init__' in result


# ---------------------------------------------------------------------------
# Bug B — Logger.warn continuation lines dropped
# ---------------------------------------------------------------------------

class TestBugB:
    TS_WITH_LOGGER_WARN = """
class Foo {
  bar() {
    Logger.warn(
      `Missing data for symbol`,
      'PortfolioCalculator'
    );
    return 1;
  }
}
"""

    def test_warn_class_name_arg_dropped(self):
        output = translate_typescript_content(self.TS_WITH_LOGGER_WARN)
        assert 'PortfolioCalculator' not in output

    def test_warn_message_arg_dropped(self):
        output = translate_typescript_content(self.TS_WITH_LOGGER_WARN)
        assert 'Missing data for symbol' not in output

    def test_warn_comment_line_kept(self):
        output = translate_typescript_content(self.TS_WITH_LOGGER_WARN)
        assert '# Logger.warn(' in output

    def test_no_unmatched_closing_paren(self):
        # The dangling `)` must not appear as a lone statement
        output = translate_typescript_content(self.TS_WITH_LOGGER_WARN)
        lines = output.splitlines()
        lone_parens = [l for l in lines if l.strip() == ')']
        assert lone_parens == [], f"Found lone ')' lines: {lone_parens}"

    def test_code_after_warn_preserved(self):
        # `return 1` after the warn block must still be present
        output = translate_typescript_content(self.TS_WITH_LOGGER_WARN)
        assert 'return 1' in output


# ---------------------------------------------------------------------------
# Integration — generated file must compile after translator runs
# ---------------------------------------------------------------------------

class TestIntegration:
    GENERATED = (
        REPO_ROOT
        / "translations/ghostfolio_pytx/app/implementation"
        / "portfolio/calculator/roai/portfolio_calculator.py"
    )

    @pytest.mark.skipif(
        not GENERATED.exists(),
        reason="Generated file not present; run 'uv run --project tt tt translate' first"
    )
    def test_generated_file_compiles(self):
        result = subprocess.run(
            [sys.executable, '-m', 'py_compile', str(self.GENERATED)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Compile failed:\n{result.stderr}"
        )

    @pytest.mark.skipif(
        not GENERATED.exists(),
        reason="Generated file not present; run 'uv run --project tt tt translate' first"
    )
    def test_no_private_keyword_in_output(self):
        content = self.GENERATED.read_text()
        offending = [
            (i + 1, line)
            for i, line in enumerate(content.splitlines())
            if line.lstrip().startswith(('private ', 'protected ', 'public '))
               and '(' not in line  # method declarations are fine
        ]
        assert offending == [], (
            "Found bare access-modifier lines:\n"
            + "\n".join(f"  L{ln}: {l}" for ln, l in offending)
        )
