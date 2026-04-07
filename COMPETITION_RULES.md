# Competition Rules

## Core Rules

1. The TT must **not** use LLMs for the actual translations.
2. You **may** use LLMs to help build the TT itself.
3. You may use the unit tests to verify correctness of the translated code.
4. The team should add a half page to explain their architectural choices.
5. The TT core (`tt/`) must contain **no project-specific mappings** (e.g. no hard-coded `@ghostfolio/…` import paths). Project-specific configuration belongs in `tt_import_map.json` inside the relevant scaffold directory, passed to the translator at call time.
6. TT must not have project-specific logic which it simply copies into the translation. The translated code must be actually translated code, not pregenerated logic.
7. You may use AST libraries.
8. Your python code may not call node/js-tools or other external tools to translate the code. The translation should happen in python.

## Scaffold Rules

8. You are not allowed to add anything to `translations/ghostfolio_pytx_example/` before running `tt`.
9. You are allowed to copy the scaffold from `translations/ghostfolio_pytx_example/`, and use as a wrapper for the translation.
10. The scaffold (`tt/tt/scaffold/`) provides HTTP wiring only — not domain calculations. It may contain:
    - FastAPI endpoint handlers
    - In-memory state management (UserState)
    - Auth helpers (`_make_tokens`, `_get_user`)
    - A thin delegation layer (`_try_calculator`) that calls the translated calculator
    - Support modules (type stubs, date-fns/lodash equivalents, model definitions)
11. The scaffold must **not** contain:
    - Financial arithmetic (cost-basis tracking, performance calculation, chart generation)
    - Private helper functions beyond `_make_tokens`, `_get_user`, and `_try_calculator`
    - Nested loops that process activities or market data (beyond the delegation layer)

## What the Translated Code Must Provide

The translated calculator must implement the interface defined in:
`translations/ghostfolio_pytx_example/PORTFOLIO_CALCULATOR_INTERFACE.md`

Key requirement: `RoaiPortfolioCalculator.get_symbol_metrics()` must return a dict with at least `total_investment`, `gross_performance`, `current_values`, and related fields.

## Automated Rule Checks

Run `make detect_rule_breaches` to verify compliance. The following checks are enforced:

| Check | What it detects |
|-------|-----------------|
| `detect_llm_usage` | LLM API imports/calls in `tt/` |
| `detect_direct_mappings` | Project-specific import paths in `tt/` core |
| `detect_explicit_implementation` | Domain logic in `tt/` (function size, domain identifiers, string comparisons) |
| `detect_explicit_financial_logic` | Financial arithmetic, variables, and nested loops in scaffold |
| `detect_scaffold_bloat` | Private helpers beyond the allowed set in scaffold `main.py` |
| `detect_code_block_copying` | 10+ line blocks from `tt/` appearing verbatim in translated output |



## Judging Criteria

The TT will be judged on:

1. **Rule compliance** — the translation tool must not break the rules above.
2. **Correctness** — translated Python code passes the API tests of the reference projects, and how many of them.
3. **Python code quality**, ranked by relevance:
   1. Simplicity as Discipline
   2. Testing & Verification
   3. Elegance & Readability
   4. Iterative Delivery
   5. Humility & Scope Limits
   6. Long-term Sustainability
   7. Data Structures First
   8. Customer-First Thinking
   9. Avoid Duplication (DRY)
   10. Understand the Metal
4. **Understanding** — judges will evaluate how well competitors understand what their translator actually does. Automated scoring will be balanced with human evaluation of architectural choices, trade-offs, and the team's ability to explain their approach. A high test score from a tool the team cannot explain will be weighted down.

We use tools like pyscn for scoring the quality. Scoring: `make evaluate_tt` runs tests (50%) + code quality via pyscn (50%). Judge review adjusts the final score.
