#!/usr/bin/env python3
"""
detect_llm_usage.py — scan the tt/ package source for LLM API usage.

Checks Python source files under tt/tt/ (excluding .venv) for:
  - Imports of known LLM client libraries (anthropic, openai, langchain, etc.)
  - HTTP calls to known LLM API endpoints (api.anthropic.com, api.openai.com, etc.)
  - Common LLM SDK call patterns (chat.completions.create, messages.create, etc.)

Exits with code 1 and prints an alert if any LLM usage is detected.
Run directly:
  python checks/detect_llm_usage.py
Or as a test:
  pytest checks/detect_llm_usage.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Source root — only scan first-party code, not .venv
# ---------------------------------------------------------------------------

TT_SRC = Path(__file__).parent.parent.parent.parent / "tt" / "tt"

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

# Top-level package names whose import indicates an LLM client library.
LLM_IMPORT_PACKAGES = {
    "anthropic",
    "openai",
    "langchain",
    "langchain_core",
    "langchain_community",
    "llama_cpp",
    "llama_index",
    "transformers",          # HuggingFace transformers (generate / pipeline)
    "huggingface_hub",
    "cohere",
    "together",
    "mistralai",
    "groq",
    "google.generativeai",
    "vertexai",
    "boto3",                 # AWS Bedrock is accessed via boto3
    "botocore",
    "litellm",
    "ollama",
    "replicate",
}

# Regex patterns matched against raw source lines (case-insensitive).
# Flagged when found outside a comment or string (best-effort; AST import
# check is the primary guard; this catches dynamic usage).
LLM_URL_PATTERNS = [
    re.compile(r"api\.anthropic\.com", re.IGNORECASE),
    re.compile(r"api\.openai\.com", re.IGNORECASE),
    re.compile(r"generativelanguage\.googleapis\.com", re.IGNORECASE),
    re.compile(r"api\.cohere\.ai", re.IGNORECASE),
    re.compile(r"api\.together\.xyz", re.IGNORECASE),
    re.compile(r"api\.mistral\.ai", re.IGNORECASE),
    re.compile(r"api\.groq\.com", re.IGNORECASE),
    re.compile(r"bedrock(?:-runtime)?\.amazonaws\.com", re.IGNORECASE),
    re.compile(r"openrouter\.ai", re.IGNORECASE),
]

# Regex for common SDK call patterns in source text.
LLM_CALL_PATTERNS = [
    re.compile(r"chat\.completions\.create", re.IGNORECASE),
    re.compile(r"messages\.create\s*\(", re.IGNORECASE),
    re.compile(r"client\.generate\s*\(", re.IGNORECASE),
    re.compile(r"\.invoke_model\s*\(", re.IGNORECASE),   # Bedrock
    re.compile(r"GenerativeModel\s*\(", re.IGNORECASE),  # Google Gemini
    re.compile(r"pipeline\s*\(\s*['\"]text-generation", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Scanning helpers
# ---------------------------------------------------------------------------

def _source_files() -> list[Path]:
    """Return all .py files under TT_SRC."""
    return sorted(TT_SRC.rglob("*.py"))


def _check_imports(tree: ast.Module, path: Path) -> list[str]:
    """Return violation messages for any LLM-related import nodes."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in LLM_IMPORT_PACKAGES or alias.name in LLM_IMPORT_PACKAGES:
                    violations.append(
                        f"{path}:{node.lineno}: LLM import detected: import {alias.name}"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                full = node.module
                if top in LLM_IMPORT_PACKAGES or full in LLM_IMPORT_PACKAGES:
                    violations.append(
                        f"{path}:{node.lineno}: LLM import detected: from {node.module} import ..."
                    )
    return violations


def _check_patterns(source: str, path: Path) -> list[str]:
    """Return violation messages for URL / call-pattern matches in raw source."""
    violations: list[str] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue  # skip comment lines
        for pattern in LLM_URL_PATTERNS + LLM_CALL_PATTERNS:
            if pattern.search(line):
                violations.append(
                    f"{path}:{lineno}: LLM usage pattern '{pattern.pattern}' matched: {line.rstrip()}"
                )
                break  # one violation per line is enough
    return violations


def scan() -> list[str]:
    """Scan all source files; return a list of violation strings (empty = clean)."""
    all_violations: list[str] = []
    for path in _source_files():
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            all_violations.append(f"{path}: SyntaxError during parse: {exc}")
            continue
        all_violations.extend(_check_imports(tree, path))
        all_violations.extend(_check_patterns(source, path))
    return all_violations


# ---------------------------------------------------------------------------
# pytest-compatible test function
# ---------------------------------------------------------------------------

def test_no_llm_usage_in_tt():
    """tt/ source must not import or call any LLM API."""
    violations = scan()
    if violations:
        report = "\n".join(violations)
        raise AssertionError(
            f"LLM usage detected in tt/ source ({len(violations)} finding(s)):\n{report}"
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    violations = scan()
    if violations:
        print("ALERT: LLM usage detected in tt/ source code!\n")
        for v in violations:
            print(f"  {v}")
        print(f"\n{len(violations)} finding(s) total.")
        sys.exit(1)
    else:
        print("OK: No LLM usage detected in tt/ source code.")
        sys.exit(0)
