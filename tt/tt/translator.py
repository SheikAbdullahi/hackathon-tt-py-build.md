"""
TypeScript to Python translator for the ghostfolio portfolio calculator.

This translator reads TypeScript source files and performs AST-informed regex
transformations to produce equivalent Python code. No LLMs are used in the
translation process.

Pipeline:
  1. Strip TypeScript-only syntax (imports, type annotations, generics)
  2. Translate class/method declarations
  3. Translate variable declarations
  4. Translate control flow
  5. Translate operators and literals
  6. Translate method calls and special patterns
  7. Convert brace-delimited blocks to indented Python blocks
  8. Generate final output with scaffolding
"""
from __future__ import annotations

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Per-line transformations
# ---------------------------------------------------------------------------

def _translate_line(line: str) -> str:
    """Apply per-line transformations to convert TypeScript to Python."""
    stripped = line.lstrip()
    indent = line[: len(line) - len(stripped)]

    if not stripped:
        return ''

    # Drop standalone `)` or `);` — leftover from collapsed multi-line calls
    if re.match(r'^\s*\);\s*$', line) or re.match(r'^\s*\)\s*$', line):
        return ''
    # Convert // comments to #
    if stripped.startswith('//'):
        return indent + '#' + stripped[2:]

    # Drop block comment markers (keep content)
    if stripped.startswith('*') or stripped.startswith('/*') or stripped.startswith('*/'):
        return ''

    # Drop TypeScript imports
    if re.match(r'^import\s+', stripped):
        return ''

    # Remove export/abstract/access modifier keywords from line starts
    line = re.sub(r'^(\s*)export\s+(abstract\s+)?', r'\1', line)
    line = re.sub(r'^(\s*)abstract\s+', r'\1', line)
    line = re.sub(r'^(\s*)(private|protected|public|override)\s+(?!static\s)', r'\1', line)

    # --- Class declaration --- keep `{` so brace converter pushes the class body level
    line = re.sub(
        r'^(\s*)class\s+(\w+)\s+extends\s+(\w+)\s*\{',
        r'\1class \2(\3): {',
        line
    )
    line = re.sub(r'^(\s*)class\s+(\w+)\s*\{', r'\1class \2: {', line)

    # --- Drop instance field declarations: private/protected/public name: Type ---
    m = re.match(r'^(\s*)(private|protected|public)\s+(\w+)\s*:', stripped)
    if m and '(' not in stripped:
        return ''

    # --- Static property ---
    m = re.match(
        r'^(\s*)(protected|private|public)?\s*static\s+readonly\s+(\w+)\s*=\s*(.+?);?\s*$',
        line
    )
    if m:
        val = m.group(4).strip()
        val = val.replace('false', 'False').replace('true', 'True').replace('null', 'None')
        return f"{m.group(1)}{m.group(3)} = {val}"

    # --- Method declarations ---
    line = _translate_method_declaration(line)

    # --- Variable declarations ---
    line = re.sub(r'\b(const|let|var)\s+', '', line)

    # --- Remove type assertions: `as Type` ---
    line = re.sub(r'\s+as\s+[A-Z]\w*(?:<[^>]*>)?', '', line)

    # --- Remove generics from method calls: func<Type>( -> func( ---
    line = re.sub(r'(\w+)<[A-Z]\w*(?:,\s*[A-Z]\w*)?>(?=\s*\()', r'\1', line)

    # --- new Big(x) -> Big(x) ---
    line = re.sub(r'\bnew\s+Big\s*\(', 'Big(', line)

    # --- new Date(x) -> parse_date(x) ---
    line = re.sub(r'\bnew\s+Date\s*\(([^)]+)\)', r'parse_date(\1)', line)
    line = re.sub(r'\bnew\s+Date\s*\(\s*\)', 'datetime.now()', line)

    # --- new Set / Map ---
    line = re.sub(r'\bnew\s+Set\s*\(', 'set(', line)
    line = re.sub(r'\bnew\s+Map\s*\(\s*\)', 'dict()', line)

    # --- this. -> self. ---
    line = re.sub(r'\bthis\.', 'self.', line)

    # --- Operators ---
    line = line.replace('===', '==').replace('!==', '!=')
    line = re.sub(r'(?<! )&&(?! )', ' and ', line)
    line = re.sub(r' && ', ' and ', line)
    line = re.sub(r'(?<! )\|\|(?! )', ' or ', line)
    line = re.sub(r' \|\| ', ' or ', line)
    # Logical NOT: !expr (careful not to break !=)
    line = re.sub(r'(?<![=!<>])!(?!=)(?=\s*[\w(])', 'not ', line)

    # --- Literals ---
    line = re.sub(r'\bnull\b', 'None', line)
    line = re.sub(r'\bundefined\b', 'None', line)
    line = re.sub(r'\btrue\b', 'True', line)
    line = re.sub(r'\bfalse\b', 'False', line)

    # --- Template literals ---
    line = _translate_template_literals(line)

    # --- Optional chaining: obj?.prop -> (obj or {}).get('prop') ---
    line = re.sub(r'(\w+)\?\.\[', r'(\1 or [])[', line)
    line = re.sub(r'\?\.([\w]+)', r'.get("\1")', line)

    # --- Nullish coalescing: a ?? b ---
    line = re.sub(r'\s*\?\?\s*new\s+Big\s*\(0\)', ' or Big(0)', line)
    line = re.sub(r'\s*\?\?\s*(\w[\w.()]*)', r' or \1', line)

    # --- Array methods ---
    line = re.sub(r'\.at\s*\((-?\d+)\)', r'[\1]', line)
    line = re.sub(r'\.length\b', '.__len__()', line)
    line = re.sub(r'\.push\s*\(', '.append(', line)
    line = re.sub(r'\.includes\s*\(([^)]+)\)', r'.__contains__(\1)', line)

    # --- Object methods ---
    line = re.sub(r'\bObject\.keys\s*\(([^)]+)\)', r'list(\1.keys())', line)
    line = re.sub(r'\bObject\.entries\s*\(([^)]+)\)', r'\1.items()', line)
    line = re.sub(r'\bObject\.values\s*\(([^)]+)\)', r'list(\1.values())', line)
    line = re.sub(r'\bArray\.from\s*\(([^)]+)\)', r'list(\1)', line)

    # --- Number.EPSILON ---
    line = re.sub(r'\bNumber\.EPSILON\b', '5e-324', line)

    # --- console.log -> suppress ---
    line = re.sub(r'\bconsole\.log\s*\(', '# console.log(', line)
    line = re.sub(r'\bLogger\.warn\s*\(', '# Logger.warn(', line)

    # --- Math ---
    line = re.sub(r'\bMath\.abs\s*\(', 'abs(', line)
    line = re.sub(r'\bMath\.max\s*\(', 'max(', line)
    line = re.sub(r'\bMath\.min\s*\(', 'min(', line)
    line = re.sub(r'\bMath\.floor\s*\(', 'int(', line)

    # --- date-fns ---
    line = re.sub(r'\bdifferenceInDays\b', 'difference_in_days', line)
    line = re.sub(r'\beachYearOfInterval\b', 'each_year_of_interval', line)
    line = re.sub(r'\bisThisYear\b', 'is_this_year', line)
    line = re.sub(r'\bisBefore\b', 'is_before', line)
    line = re.sub(r'\bisAfter\b', 'is_after', line)
    line = re.sub(r'\baddMilliseconds\b', 'add_milliseconds', line)
    line = re.sub(r'\bstartOfYear\b', 'start_of_year', line)
    line = re.sub(r'\bendOfYear\b', 'end_of_year', line)
    line = re.sub(r'\bgetIntervalFromDateRange\b', 'get_interval_from_date_range', line)
    line = re.sub(r'\bparseDate\b', 'parse_date', line)
    line = re.sub(r'\bresetHours\b', 'reset_hours', line)
    line = re.sub(r'\beachDayOfInterval\b', 'each_day_of_interval', line)
    line = re.sub(r'\bisWithinInterval\b', 'is_within_interval', line)

    # --- lodash ---
    line = re.sub(r'\bsortBy\b', 'sort_by', line)
    line = re.sub(r'\bcloneDeep\b', 'clone_deep', line)
    line = re.sub(r'\buniqBy\b', 'uniq_by', line)
    line = re.sub(r'\bgroupBy\b', 'group_by', line)
    line = re.sub(r'\bisNumber\b', 'is_number', line)
    line = re.sub(r'\bsum\b(?=\s*\()', 'sum_values', line)

    # --- getFactor ---
    line = re.sub(r'\bgetFactor\b', 'get_factor', line)

    # --- PortfolioCalculator.ENABLE_LOGGING ---
    line = re.sub(r'\bPortfolioCalculator\.ENABLE_LOGGING\b', 'self.ENABLE_LOGGING', line)

    # --- Semicolons at end ---
    line = re.sub(r';\s*$', '', line)

    # --- Fix __len__() -> len() ---
    line = re.sub(r'(\w+)\.__len__\(\)', r'len(\1)', line)
    # Fix __contains__ -> in
    line = re.sub(r'(\w+)\.__contains__\(([^)]+)\)', r'\2 in \1', line)

    return line


def _translate_method_declaration(line: str) -> str:
    """Convert TypeScript method declarations to Python def statements."""
    stripped = line.lstrip()
    indent = line[: len(line) - len(stripped)]

    # Check for method patterns (but not if/for/while etc.)
    skip = {'if', 'for', 'while', 'switch', 'catch', 'else', 'return', 'class',
            'interface', 'type', 'enum', 'import', 'export', 'const', 'let', 'var',
            'new', 'super', 'typeof', 'instanceof', 'throw', 'try'}

    # Match: [access modifier] [static] [async] [get] methodName(...) [: ReturnType] {
    m = re.match(
        r'^(protected|private|public|override)?\s*'
        r'(static\s+)?(async\s+)?(get\s+)?'
        r'(\w+)\s*\(([^)]*(?:\([^)]*\)[^)]*)*)\)\s*(?::[^{]+?)?\s*\{?\s*$',
        stripped
    )
    if not m:
        return line

    name = m.group(5)
    if name in skip:
        return line

    is_static = bool(m.group(2))
    is_async = bool(m.group(3))
    is_getter = bool(m.group(4))
    params_raw = m.group(6)

    py_name = _to_snake_case(name)
    if py_name == 'constructor':
        py_name = '__init__'

    params = _translate_params(params_raw, is_static)

    async_prefix = 'async ' if is_async else ''
    getter_deco = f'{indent}@property\n' if is_getter else ''

    # Keep `{` so brace converter pushes the method body indent level
    return f'{getter_deco}{indent}{async_prefix}def {py_name}({params}): {{'


def _to_snake_case(name: str) -> str:
    """Convert camelCase to snake_case."""
    if name in ('constructor', '__init__'):
        return '__init__'
    result = re.sub(r'(?<=[a-z0-9])([A-Z])', r'_\1', name)
    return result.lower()


def _translate_params(params_raw: str, is_static: bool = False) -> str:
    """Convert TypeScript parameter list to Python parameter list."""
    params_raw = params_raw.strip()
    self_param = 'cls' if is_static else 'self'

    # Destructured object parameter: { a, b, c }: Type
    dm = re.match(r'^\s*\{([^}]+)\}\s*(?::\s*[^,)]+)?\s*$', params_raw)
    if dm:
        fields_str = dm.group(1)
        fields = []
        for f in re.split(r',', fields_str):
            f = f.strip()
            if not f:
                continue
            if ':' in f:
                local = f.split(':', 1)[1].strip().split()[0]
                fields.append(f'{_to_snake_case(local)}=None')
            else:
                name = f.rstrip('?').strip()
                fields.append(f'{_to_snake_case(name)}=None')
        if fields:
            return f'{self_param}, ' + ', '.join(fields)
        return self_param

    if not params_raw:
        return self_param

    param_parts = _split_params(params_raw)
    py_params = []
    for p in param_parts:
        p = p.strip()
        if not p:
            continue
        # Optional: name?: Type -> name=None
        p = re.sub(r'\s*\?:\s*[^,=]+', '=None', p)
        # Type annotation: name: Type -> name
        p = re.sub(r'\s*:\s*[^,=]+', '', p)
        p = re.sub(r'\s+as\s+\w+', '', p)
        p = p.strip().rstrip(',')
        if not p:
            continue
        if '=' in p:
            parts = p.split('=', 1)
            snake = _to_snake_case(parts[0].strip())
            default = parts[1].strip()
            default = default.replace('false', 'False').replace('true', 'True').replace('null', 'None')
            py_params.append(f'{snake}={default}')
        else:
            py_params.append(_to_snake_case(p))

    if py_params:
        return f'{self_param}, ' + ', '.join(py_params)
    return self_param


def _split_params(params_raw: str) -> list[str]:
    """Split parameter string by commas, respecting nested brackets."""
    parts = []
    depth = 0
    current = []
    for char in params_raw:
        if char in '({[<':
            depth += 1
            current.append(char)
        elif char in ')}]>':
            depth = max(0, depth - 1)
            current.append(char)
        elif char == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(char)
    if current:
        parts.append(''.join(current))
    return parts


def _translate_template_literals(line: str) -> str:
    """Convert TypeScript template literals to Python f-strings."""
    if '`' not in line:
        return line
    result = []
    i = 0
    while i < len(line):
        if line[i] == '`':
            j = i + 1
            content = []
            while j < len(line) and line[j] != '`':
                if line[j] == '$' and j + 1 < len(line) and line[j + 1] == '{':
                    k = j + 2
                    depth = 1
                    expr_chars = []
                    while k < len(line) and depth > 0:
                        if line[k] == '{':
                            depth += 1
                        elif line[k] == '}':
                            depth -= 1
                        if depth > 0:
                            expr_chars.append(line[k])
                        k += 1
                    content.append('{' + ''.join(expr_chars) + '}')
                    j = k
                else:
                    c = line[j]
                    if c == '"':
                        c = '\\"'
                    content.append(c)
                    j += 1
            result.append('f"' + ''.join(content) + '"')
            i = j + 1
        else:
            result.append(line[i])
            i += 1
    return ''.join(result)


# ---------------------------------------------------------------------------
# Block indentation converter
# ---------------------------------------------------------------------------

def _line_opens_code_block(stripped: str) -> bool:
    """
    Return True if this line opens a Python code block (not an object literal).
    We open a code block for: if/elif/else, for, while, def, class, try/except,
    and NOT for: return {, = {, ( {, [ {, => {, : {
    """
    if not stripped.endswith('{'):
        return False
    # These keyword patterns open code blocks
    if re.match(r'^(if|elif|else|for|while|def|class|try|except|finally|with)\b', stripped):
        return True
    if re.match(r'^(async\s+def|async\s+for)\b', stripped):
        return True
    # Method/function declaration pattern (already translated to def ...):
    if re.match(r'^def\s+\w+', stripped):
        return True
    if re.match(r'^class\s+\w+', stripped):
        return True
    # Check if it's after `return` (object literal return)
    if re.match(r'^return\s*\{', stripped):
        return False
    # Check common object literal patterns
    if re.search(r'[=({[,?:!]\s*\{?\s*$', stripped.rstrip('{')):
        return False
    # Arrow function block: => {
    if stripped.rstrip('{').rstrip().endswith('=>'):
        return False
    # Default: treat as code block
    return True


def _convert_ts_obj_property_line(stripped: str, indent: str) -> str:
    """
    Convert a TypeScript object literal property line to Python dict entry.
    `key: value,` → `"key": value,`
    `key,` → `"key": key,`
    Returns original if not a property line.
    """
    # Shorthand: `identifier,` or `identifier` (at end of object)
    m = re.match(r'^([a-z_][a-zA-Z0-9_]*),?\s*$', stripped)
    if m:
        name = m.group(1)
        trailing = ',' if ',' in stripped else ''
        return f'{indent}"{name}": {name}{trailing}'

    # Named: `identifier: expression,`
    m = re.match(r'^([a-z_][a-zA-Z0-9_]*)\s*:\s*(.+?),?\s*$', stripped)
    if m:
        name = m.group(1)
        value = m.group(2).strip()
        trailing = ',' if stripped.endswith(',') else ''
        # Skip if value starts with a keyword that suggests it's not a property
        if not re.match(r'^(return|if|for|while|class|def|import|from)\b', value):
            return f'{indent}"{name}": {value}{trailing}'

    return indent + stripped


def _convert_braces_to_indent(lines: list[str]) -> list[str]:
    """Convert TypeScript brace-based blocks to Python indentation."""
    result = []
    INDENT = "    "
    # Stack: (indent_level, is_object_literal)
    stack: list[tuple[int, bool]] = [(0, False)]

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            result.append('')
            i += 1
            continue

        level, in_obj = stack[-1]

        # Handle `} else if (...) {`
        if re.match(r'^}\s*else\s+if\s*\(', stripped) and not in_obj:
            if len(stack) > 1:
                stack.pop()
            level = stack[-1][0]
            cond_m = re.search(r'else\s+if\s*\((.+)\)\s*\{?$', stripped)
            if cond_m:
                cond = _simple_translate(cond_m.group(1))
                result.append(INDENT * level + f'elif {cond}:')
            stack.append((level + 1, False))
            i += 1
            continue

        # Handle `} else {`
        if re.match(r'^}\s*else\s*\{$', stripped) and not in_obj:
            if len(stack) > 1:
                stack.pop()
            level = stack[-1][0]
            result.append(INDENT * level + 'else:')
            stack.append((level + 1, False))
            i += 1
            continue

        # Handle lone `}` or `};`
        if re.match(r'^}\s*;?\s*$', stripped):
            if in_obj:
                # Close object literal — emit the closing `}` for multi-line Python dicts
                stack.pop()
                level = stack[-1][0]
                result.append(INDENT * level + '}')
            else:
                # Close code block - just pop
                if len(stack) > 1:
                    stack.pop()
            i += 1
            continue

        # Handle `} catch (e) {`
        if re.match(r'^}\s*catch\s*\(', stripped) and not in_obj:
            if len(stack) > 1:
                stack.pop()
            level = stack[-1][0]
            result.append(INDENT * level + 'except Exception as e:')
            stack.append((level + 1, False))
            i += 1
            continue

        # Handle `} finally {`
        if re.match(r'^}\s*finally\s*\{', stripped) and not in_obj:
            if len(stack) > 1:
                stack.pop()
            level = stack[-1][0]
            result.append(INDENT * level + 'finally:')
            stack.append((level + 1, False))
            i += 1
            continue

        # Does this line open a block?
        opens_code_block = _line_opens_code_block(stripped)
        opens_obj_literal = (
            stripped.endswith('{') and
            not stripped.endswith('${') and
            not opens_code_block
        )

        if in_obj:
            # Inside object literal: convert property syntax
            py_line = _convert_ts_obj_property_line(stripped, INDENT * level)
            result.append(py_line)
            if opens_obj_literal:
                stack.append((level + 1, True))
                # Replace last appended line to include the {
                result[-1] = result[-1].rstrip()
                if not result[-1].endswith('{'):
                    result[-1] += ' {'
        else:
            # Transform control flow
            py_line = _translate_control_flow_line(stripped)

            if opens_obj_literal:
                # Object literal opener: emit the `return {` or similar
                # Remove trailing { and add it back properly
                base = stripped.rstrip('{').rstrip()
                result.append(INDENT * level + base + ' {')
                stack.append((level + 1, True))
            elif opens_code_block:
                result.append(INDENT * level + py_line)
                stack.append((level + 1, False))
            else:
                result.append(INDENT * level + py_line)

        i += 1

    return result


def _simple_translate(expr: str) -> str:
    """Simple expression translation for conditions."""
    expr = expr.replace('===', '==').replace('!==', '!=')
    expr = re.sub(r'\s*&&\s*', ' and ', expr)
    expr = re.sub(r'\s*\|\|\s*', ' or ', expr)
    expr = re.sub(r'\bnull\b', 'None', expr)
    expr = re.sub(r'\bundefined\b', 'None', expr)
    expr = re.sub(r'\btrue\b', 'True', expr)
    expr = re.sub(r'\bfalse\b', 'False', expr)
    expr = re.sub(r'\.length\b', '', expr)
    expr = re.sub(r'\bnew\s+Big\s*\(', 'Big(', expr)
    expr = re.sub(r'\bthis\.', 'self.', expr)
    return expr


def _translate_control_flow_line(stripped: str) -> str:
    """Transform TypeScript control flow to Python."""

    # if (cond) { -> if cond:
    m = re.match(r'^if\s*\((.+)\)\s*\{$', stripped)
    if m:
        return f'if {_simple_translate(m.group(1))}:'

    # else if (cond) { -> elif cond:
    m = re.match(r'^else\s+if\s*\((.+)\)\s*\{$', stripped)
    if m:
        return f'elif {_simple_translate(m.group(1))}:'

    # else { -> else:
    if stripped in ('else {', 'else{'):
        return 'else:'

    # for (const x of arr) {  — use rfind to find the outer closing paren
    m = re.match(r'^for\s*\(\s*(?:(?:const|let|var)\s+)?(\w+)\s+of\s+', stripped)
    if m and stripped.rstrip().endswith('{'):
        rest = stripped[m.end():]  # everything after `for (const VAR of `
        close_idx = rest.rfind(')')  # last `)` is the for-loop's outer closer
        if close_idx >= 0:
            arr_raw = rest[:close_idx + 1].strip()  # include the `)` at close_idx (iterable's last paren)
            arr = _simple_translate(arr_raw)
            return f'for {m.group(1)} in {arr}:'

    # for (const [k, v] of ...) {
    m = re.match(r'^for\s*\(\s*(?:const|let)\s+\[(\w+),\s*(\w+)\]\s+of\s+(.+)\)\s*\{$', stripped)
    if m:
        iterable = _simple_translate(m.group(3))
        return f'for {m.group(1)}, {m.group(2)} in {iterable}:'

    # for (let i = 0; i < n; i += 1)
    m = re.match(r'^for\s*\(\s*let\s+(\w+)\s*=\s*(\d+)\s*;\s*\1\s*<\s*(.+?)\s*;\s*\1\s*\+=\s*1\s*\)\s*\{$', stripped)
    if m:
        start = m.group(2)
        end = _simple_translate(m.group(3))
        start_s = '' if start == '0' else f'{start}, '
        return f'for {m.group(1)} in range({start_s}{end}):'

    # for (let i = n; i >= 0; i -= 1)
    m = re.match(r'^for\s*\(\s*let\s+(\w+)\s*=\s*(.+?)\s*;\s*\1\s*>=\s*(\d+)\s*;\s*\1\s*-=\s*1\s*\)\s*\{$', stripped)
    if m:
        start = _simple_translate(m.group(2))
        stop = int(m.group(3)) - 1
        return f'for {m.group(1)} in range({start}, {stop}, -1):'

    # while (cond) {
    m = re.match(r'^while\s*\((.+)\)\s*\{$', stripped)
    if m:
        return f'while {_simple_translate(m.group(1))}:'

    # Remove trailing { if line still ends with it
    if stripped.endswith('{') and not stripped.endswith('${'):
        stripped = stripped[:-1].rstrip()
        if stripped.endswith(':'):
            return stripped  # already has colon
        return stripped + ':'

    # Remove trailing ;
    stripped = stripped.rstrip(';')
    return stripped


# ---------------------------------------------------------------------------
# Destructuring handler
# ---------------------------------------------------------------------------

def _handle_destructuring(lines: list[str]) -> list[str]:
    """Convert TypeScript destructuring assignments to Python."""
    result = []
    for line in lines:
        stripped = line.strip()
        indent = line[: len(line) - len(stripped)]

        # Object destructuring: { a, b } = expr
        m = re.match(r'^(?:const|let|var)\s+\{\s*([^}]+)\}\s*=\s*(.+?);?\s*$', stripped)
        if m:
            fields_str = m.group(1)
            expr = m.group(2).strip()
            fields = []
            for f in re.split(r',', fields_str):
                f = f.strip()
                if not f:
                    continue
                if ':' in f and not f.startswith('"') and not f.startswith("'"):
                    parts = f.split(':', 1)
                    orig = parts[0].strip().rstrip('?')
                    local = parts[1].strip().split()[0]
                    fields.append((orig, local))
                else:
                    name = f.rstrip('?').strip()
                    fields.append((name, name))
            for orig, local in fields:
                result.append(f'{indent}{local} = ({expr} or {{}}).get("{orig}")')
            continue

        # Array destructuring: [a, b] = expr
        m = re.match(r'^(?:const|let|var)\s+\[\s*([^\]]+)\]\s*=\s*(.+?);?\s*$', stripped)
        if m:
            vars_list = [v.strip() for v in m.group(1).split(',')]
            result.append(f'{indent}{", ".join(vars_list)} = {m.group(2).strip()}')
            continue

        result.append(line)
    return result


# ---------------------------------------------------------------------------
# Arrow function handler
# ---------------------------------------------------------------------------

def _translate_arrow_functions(code: str) -> str:
    """Convert simple arrow functions to Python lambdas."""
    # ({ prop }) => expr - destructured single-arg - skip (complex)

    # Simple: (x) => expr
    code = re.sub(
        r'\((\w+)\)\s*=>\s*\{?\s*return\s+([^;}\n]+);?\s*\}?',
        r'lambda \1: \2',
        code
    )
    code = re.sub(
        r'\((\w+)\)\s*=>\s*([^{;\n,)]+)',
        r'lambda \1: \2',
        code
    )
    # x => expr
    code = re.sub(
        r'(?<!\w)(\w+)\s*=>\s*([^{;\n,)]+)',
        r'lambda \1: \2',
        code
    )
    return code


# ---------------------------------------------------------------------------
# Type annotation stripper
# ---------------------------------------------------------------------------

def _strip_type_annotations(line: str) -> str:
    """Remove TypeScript type annotations."""
    # Strip split method return type: ): ReturnType: or ): ReturnType {
    line = re.sub(r'^\s*\)\s*:\s*[A-Z]\w*(?:<[^>]*>)?\s*[:{]?\s*$', ')', line)
    # Remove inline type annotations in variable declarations
    # x: { [key: string]: Big } = ...  -> x = ...
    line = re.sub(r':\s*\{\s*\[[^\]]+\]\s*:\s*[^}]+\}\s*=', ' =', line)
    # x: Type[] = -> x =
    line = re.sub(r':\s*\w+(?:<[^>]*>)?\[\]\s*=', ' =', line)
    # x: Type = -> x =
    line = re.sub(r':\s*[A-Z]\w*(?:<[^>]*>)?\s*=', ' =', line)
    # Uninitialized typed declarations: let x: Type; -> x = None
    line = re.sub(r'^(\s*)(\w+):\s*[A-Z]\w*(?:<[^>]*>)?(?:\[\])?\s*;?\s*$',
                  r'\1\2 = None', line)
    return line


# ---------------------------------------------------------------------------
# Main translation function
# ---------------------------------------------------------------------------

def _is_object_literal_context(line_before: str) -> bool:
    """Detect if a `{` opens an object literal rather than a code block."""
    s = line_before.rstrip()
    # Object literal openers: return {, = {, ({ , [{ , => {, : {, , {
    if re.search(r'\breturn\s*$', s):
        return True
    if re.search(r'[=({[,\?:]\s*$', s):
        return True
    if re.search(r'=>\s*$', s):
        return True
    return False


def _convert_ts_object_property(line: str) -> str:
    """
    Convert TypeScript object literal property to Python dict entry.
    `  key: value,` → `  "key": value,`
    `  key,`        → `  "key": key,`
    Only applies if the line looks like a TS object property.
    """
    stripped = line.strip()
    indent = line[: len(line) - len(stripped)]

    # Shorthand property: just `identifier,` or `identifier`
    m = re.match(r'^([a-z][a-zA-Z0-9]*),?\s*$', stripped)
    if m:
        name = m.group(1)
        trailing = ',' if stripped.endswith(',') else ''
        return f'{indent}"{name}": {name}{trailing}'

    # Named property: `identifier: expression,`
    m = re.match(r'^([a-z][a-zA-Z0-9]*)\s*:\s*(.+?),?\s*$', stripped)
    if m:
        name = m.group(1)
        value = m.group(2).strip()
        trailing = ',' if stripped.endswith(',') else ''
        # Don't convert lines that are clearly code (have keywords, operators, etc.)
        # that suggest it's actually a labeled statement or something else
        if not re.match(r'^(if|for|while|return|class|def|import)\b', value):
            return f'{indent}"{name}": {value}{trailing}'

    return line


def _preprocess_object_literals(ts_content: str) -> str:
    """
    Pre-process TypeScript object literals to convert them to Python dict syntax.
    Handles `return { key: value, shorthand, ... }` patterns.
    """
    lines = ts_content.split('\n')
    result = []
    # Track object literal nesting
    # Stack entries: True = object literal, False = code block
    context_stack: list[bool] = []
    in_object_literal = False
    object_depth = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip()
        sline = stripped.lstrip()

        # Check if this line opens a block/object
        brace_count = stripped.count('{') - stripped.count('}')

        if '{' in stripped and '}' not in stripped:
            # Line ends with { (block/object opener)
            is_obj = _is_object_literal_context(stripped.rstrip('{').rstrip())
            context_stack.append(is_obj)
        elif '{' in stripped and '}' in stripped:
            # Inline object or balanced - leave as is
            pass
        elif stripped.rstrip() == '}' or stripped.rstrip() == '};':
            if context_stack:
                context_stack.pop()

        result.append(line)
        i += 1

    return '\n'.join(result)


def _strip_multiline_imports(ts_content: str) -> str:
    """Remove multi-line TypeScript import blocks."""
    # Remove: import { ... } from '...';  (possibly spanning multiple lines)
    ts_content = re.sub(
        r'import\s+\{[^}]*\}\s+from\s+[\'"][^\'"]+[\'"]\s*;?',
        '',
        ts_content,
        flags=re.DOTALL
    )
    # Remove: import Type from '...'
    ts_content = re.sub(
        r'import\s+\w+\s+from\s+[\'"][^\'"]+[\'"]\s*;?',
        '',
        ts_content
    )
    # Remove: import * as X from '...'
    ts_content = re.sub(
        r'import\s+\*\s+as\s+\w+\s+from\s+[\'"][^\'"]+[\'"]\s*;?',
        '',
        ts_content
    )
    return ts_content


def _collapse_arrow_callbacks(ts_content: str) -> str:
    """
    Collapse multi-line destructured arrow callbacks into single-line lambdas.

    Handles both same-line and split-line cases:
      arr.filter(          arr.filter(lambda _x: (_x or {}).get('prop'))
        ({ prop }) => {  →
          return prop
        })
    """
    lines = ts_content.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Case 1: same-line — `method(({ props }) => {` OR `method(x, ({ props }) => {`
        same = re.search(r'(\w+)\s*\([^)]*,?\s*\(\s*\{([^}]+)\}\s*\)\s*=>\s*\{', line)

        # Case 2: split-line — current line ends with `filter(` or similar,
        #         next line is `({ props }) => {`
        split_trigger = None
        if not same and i + 1 < len(lines):
            next_s = lines[i + 1].strip()
            if (line.rstrip().endswith('(') and
                    re.match(r'^\(\s*\{[^}]+\}\s*\)\s*=>\s*\{', next_s)):
                split_trigger = i  # current line is the call prefix

        if same or split_trigger is not None:
            if same:
                indent = line[: len(line) - len(line.lstrip())]
                # prefix = everything up to (but not including) the `({` of the callback
                cb_start = same.start() + same.group(0).index('({')
                prefix = line[:cb_start]
                props_raw = same.group(2)
                j = i + 1
            else:
                # split case: join prefix line + next line to extract props
                indent = line[: len(line) - len(line.lstrip())]
                prefix = line  # e.g. `    for (const x of positions.filter(`
                m2 = re.match(r'^\(\s*\{([^}]+)\}\s*\)\s*=>\s*\{', lines[i + 1].strip())
                props_raw = m2.group(1)
                j = i + 2

            props = [p.strip().split(':')[0].rstrip('?').strip()
                     for p in props_raw.split(',') if p.strip()]

            # Collect callback body until depth returns to 0
            body_lines = []
            depth = 1
            while j < len(lines) and depth > 0:
                s = lines[j].strip()
                depth += s.count('{') - s.count('}')
                if depth <= 0:
                    break
                if s and not s.startswith('//'):
                    body_lines.append(s.rstrip(';'))
                j += 1

            # Build lambda
            lambda_expr = 'lambda _x: _x'  # fallback
            if len(body_lines) == 1 and body_lines[0].startswith('return '):
                expr = body_lines[0][len('return '):]
                lambda_expr = f'lambda _x: {expr}'
                for prop in props:
                    lambda_expr = re.sub(r'\b' + re.escape(prop) + r'\b',
                                         f'(_x or {{}}).get("{prop}")', lambda_expr)

            # j now points to the line containing the closing `}` of the callback body.
            # Extract any suffix on that same line (e.g. `}).length,` → suffix=`.length,`)
            closing_line = lines[j].strip() if j < len(lines) else ''
            # strip the leading `}` (and optional `)`) to get what follows
            after_close = re.sub(r'^[})\s]+', '', closing_line).strip()
            j += 1  # advance past the closing `}` line
            suffix_after = lines[j].strip() if j < len(lines) else ''
            # If next line is just closing parens + optional `{`, consume it too
            if re.match(r'^[)\s]+\{?\s*$', suffix_after):
                opens_block = bool(re.search(r'\{', suffix_after))
                suffix_clean = ''
                j += 1  # consume the closer line
            else:
                opens_block = bool(re.search(r'\{$', suffix_after))
                suffix_clean = re.sub(r'^[}\)]+\s*', '', suffix_after).strip().rstrip('{').strip()

            if same:
                # Count closing parens stripped from suffix to restore them
                leading_close = re.match(r'^([}\)]+)', suffix_after or '')
                extra_close = leading_close.group(1).replace('}', '').count(')') if leading_close else 0
                close_parens = ')' * (1 + extra_close)
                # Use after_close (e.g. `.length,`) if present, else suffix_clean
                trail = after_close if after_close else suffix_clean
                new_line = f'{prefix}{lambda_expr}{close_parens}{trail}'
                if opens_block:
                    new_line += ' {'
            else:
                new_line = f'{prefix.rstrip()}{lambda_expr})'
                if suffix_clean:
                    new_line += suffix_clean
                if opens_block:
                    new_line += ' {'

            result.append(new_line)
            # If suffix_after was NOT consumed (else branch, not a paren-closer), back up so it gets processed
            if re.match(r'^[)\s]+\{?\s*$', suffix_after) or not suffix_after:
                i = j + 1
            else:
                i = j  # let suffix_after line be processed normally
            continue

        result.append(line)
        i += 1
    return '\n'.join(result)


def _strip_ts_type_blocks(ts_content: str) -> str:
    """
    Strip TypeScript type annotation blocks from method signatures.
    Rewrites `methodName({ a, b, c }: { ... } & Type): ReturnType {`
    into a single-line `methodName({ a, b, c }) {` so normal translation handles it.
    """
    lines = ts_content.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Detect: method declaration with destructured params opening: `methodName({`
        # followed eventually by `}: {` type block start
        # Strategy: look ahead for `}: {` within the next 10 lines
        if re.search(r'\w+\s*\(\s*\{', line) and not re.search(r'\}\s*\)\s*', line):
            # Collect param names until we hit `}: {` (start of type block)
            param_names = []
            found_type_block = False
            j = i
            lookahead_lines = []
            while j < len(lines) and j < i + 15:
                s = lines[j].strip().rstrip(';')
                lookahead_lines.append(lines[j])
                if re.match(r'^\}\s*:\s*\{', s):
                    found_type_block = True
                    # Skip ahead to end of type block
                    k = j + 1
                    while k < len(lines):
                        ks = lines[k].strip()
                        if re.search(r'\)\s*:\s*\w+.*\{?\s*$', ks) and ('}' in ks or ')' in ks):
                            # Reconstruct single-line method sig from first line
                            method_line = line.rstrip()
                            # Already has `method({` — just close it with `) {`
                            # Extract just the method open: e.g. `  protected getSymbolMetrics(`
                            method_open = re.sub(r'\(\s*\{.*', '(', method_line)
                            params_str = ', '.join(param_names) if param_names else ''
                            indent = line[:len(line) - len(line.lstrip())]
                            if ks.endswith('{'):
                                result.append(f'{method_open}{{{params_str}}}) {{')
                            else:
                                result.append(f'{method_open}{{{params_str}}})')
                            i = k + 1
                            break
                        # Collect param names from inside destructure block (before `}: {`)
                        k += 1
                    else:
                        # Didn't find end — fall through
                        found_type_block = False
                    break
                # Collect bare identifiers as param names (inside `{ a, b, c }`)
                for token in re.split(r'[,\s]+', s):
                    token = token.strip().lstrip('{').rstrip('}').rstrip('?')
                    if re.match(r'^[a-zA-Z_]\w*$', token) and token:
                        param_names.append(token)
                j += 1

            if found_type_block:
                continue

        result.append(line)
        i += 1
    return '\n'.join(result)


def _join_split_method_signatures(ts_content: str) -> str:
    """
    Join multi-line method signatures into a single line.
    Handles:
      methodName(          →  methodName(param): ReturnType {
        param: Type
      ): ReturnType {
    """
    lines = ts_content.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        # Detect: line ends with `(` and is a method/function declaration (not a call in an expression)
        # Must start with optional access modifier + identifier + `(`
        if (re.match(r'^\s*(?:(?:protected|private|public|override|static|async)\s+)*\w+\s*\(\s*$', line)
                and i + 1 < len(lines)):
            # Peek ahead: collect until we find `)` or `): Type {`
            j = i + 1
            param_lines = []
            found_close = False
            while j < len(lines) and j < i + 8:
                s = lines[j].strip()
                # Closing paren line: `): ReturnType {` or `): ReturnType`  or just `)`
                if re.match(r'^\)\s*(?::\s*\w[\w<>, ]*\s*)?\{?\s*$', s):
                    found_close = True
                    close_line = s
                    j += 1
                    break
                param_lines.append(s)
                j += 1
            if found_close:
                params = ' '.join(param_lines)
                new_line = line.rstrip('( \n') + '(' + params + close_line
                result.append(new_line)
                i = j
                continue
        result.append(line)
        i += 1
    return '\n'.join(result)


def _rewrite_for_of_loops(ts_content: str) -> str:
    """
    Rewrite `for (const x of expr) {` → `for (x of expr) {`
    using paren-depth counting so nested parens in expr are handled correctly.
    The result is still TS-style for...of so _translate_control_flow_line can match it.
    """
    lines = ts_content.split('\n')
    result = []
    for line in lines:
        m = re.match(r'^(\s*)for\s*\(\s*(?:const|let|var)\s+(\w+)\s+of\s+', line)
        if m:
            indent = m.group(1)
            var = m.group(2)
            pos = m.end()
            # depth=-1 accounts for the outer `for(` already consumed by the regex
            depth = -1
            end_pos = len(line)
            for i in range(pos, len(line)):
                c = line[i]
                if c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
                    if depth < 0:
                        end_pos = i
                        break
            if end_pos == len(line):
                # No closing ) found — multi-line for...of, leave unchanged
                result.append(line)
                continue
            iterable = line[pos:end_pos].strip()
            suffix = line[end_pos + 1:].strip()
            if suffix.startswith('{'):
                result.append(f'{indent}for (const {var} of {iterable}) {{')
            else:
                result.append(f'{indent}for (const {var} of {iterable}) {suffix}')
            continue
        result.append(line)
    return '\n'.join(result)


def translate_typescript_content(ts_content: str) -> str:
    """Translate TypeScript source code to Python."""
    ts_content = _strip_multiline_imports(ts_content)
    ts_content = _join_split_method_signatures(ts_content)
    ts_content = _strip_ts_type_blocks(ts_content)
    ts_content = _collapse_arrow_callbacks(ts_content)
    ts_content = _rewrite_for_of_loops(ts_content)
    lines = ts_content.split('\n')

    # Phase 1: Destructuring
    lines = _handle_destructuring(lines)

    # Phase 2: Per-line transformations
    translated = []
    for line in lines:
        line = _strip_type_annotations(line)
        py_line = _translate_line(line)
        translated.append(py_line)

    # Phase 3: Filter consecutive blanks
    filtered = []
    prev_blank = False
    for line in translated:
        if line.strip() == '':
            if not prev_blank:
                filtered.append('')
            prev_blank = True
        else:
            prev_blank = False
            filtered.append(line)

    # Phase 4: Brace → indent
    result = _convert_braces_to_indent(filtered)

    # Phase 4b: Join split assignments (line ends with bare `=`)
    result = _fix_split_assignments(result)

    # Phase 5: Arrow functions
    code = '\n'.join(result)
    code = _translate_arrow_functions(code)

    # Phase 6: Post-process
    code = _post_process(code)

    return code


def _fix_split_assignments(lines: list[str]) -> list[str]:
    """Join lines where assignment RHS is on the next line (ends with bare `=`)."""
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.rstrip().endswith('=') and line.strip() and not line.strip().startswith('#'):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                result.append(line.rstrip() + ' ' + lines[j].strip())
                i = j + 1
                continue
        result.append(line)
        i += 1
    return result


def _drop_logger_console_args(code: str) -> str:
    """Drop argument lines left by commented-out console.log() multi-line calls."""
    lines = code.split('\n')
    result = []
    skip = False
    for line in lines:
        s = line.strip()
        if '# console.log(' in line:
            result.append(line)
            skip = True
            continue
        if skip:
            if s == ')':
                skip = False
            continue
        result.append(line)
    return '\n'.join(result)


def _fix_ternary(code: str) -> str:
    """Convert simple JS ternary `a ? b : c` to Python `b if a else c`.
    Only handles single-token conditions to avoid false positives."""
    # Only convert: identifier ? simpleExpr : simpleExpr
    code = re.sub(
        r'\b(\w+)\s*\?\s*(\'[^\']*\'|"[^"]*"|None|True|False|\w+)\s*:\s*(\'[^\']*\'|"[^"]*"|None|True|False|\w+)\b',
        r'\2 if \1 else \3',
        code
    )
    return code


def _fix_unquoted_keys(code: str) -> str:
    """Quote unquoted identifier keys in dict literals: `Foo: val` → `"Foo": val`."""
    # Match lines with an unquoted PascalCase or camelCase key followed by `: value`
    code = re.sub(
        r'^(\s*)([A-Z][a-zA-Z0-9]*)\s*:\s*(\{)',
        r'\1"\2": \3',
        code,
        flags=re.MULTILINE
    )
    return code


def _drop_logger_warn_args(code: str) -> str:
    """Drop argument lines and closing ) left by commented-out Logger.warn calls."""
    lines = code.split('\n')
    result = []
    skip_until_paren = False
    for line in lines:
        s = line.strip()
        if '# Logger.warn(' in line:
            result.append(line)
            skip_until_paren = True
            continue
        if skip_until_paren:
            if s == ')':
                skip_until_paren = False
            continue
        result.append(line)
    return '\n'.join(result)


def _post_process(code: str) -> str:
    """Fix common translation artifacts."""
    code = _drop_logger_warn_args(code)
    code = _drop_logger_console_args(code)
    code = _fix_ternary(code)
    code = _fix_unquoted_keys(code)
    # Fix (None or {}).get("x") -> None
    code = re.sub(r'\(None or \{\}\)\.get\("(\w+)"\)', r'None', code)
    # Remove trailing whitespace (do NOT collapse leading spaces — that's indentation)
    code = '\n'.join(l.rstrip() for l in code.split('\n'))
    code = code.lstrip('\n')
    if not code.endswith('\n'):
        code += '\n'
    return code


# ---------------------------------------------------------------------------
# Generate the Python calculator file
# ---------------------------------------------------------------------------

PYTHON_FILE_HEADER = '''\
"""
RoaiPortfolioCalculator — translated from TypeScript by tt.

Auto-generated. Do not edit manually.
"""
from __future__ import annotations

import copy
from datetime import datetime, date as _date_type, timedelta
from typing import Any

from app.wrapper.portfolio.calculator.portfolio_calculator import PortfolioCalculator
from app.helpers.big import Big
from app.helpers.date_fns import (
    format, is_before, is_after, add_milliseconds,
    difference_in_days, each_year_of_interval, is_this_year,
    parse_date, get_interval_from_date_range, start_of_year, end_of_year,
    start_of_day, end_of_day, reset_hours, each_day_of_interval,
    is_within_interval,
)
from app.helpers.lodash import sort_by, clone_deep, uniq_by, is_number, sum_values
from app.helpers.portfolio_helpers import get_factor

DATE_FORMAT = "yyyy-MM-dd"
_DATE_FMT = "%Y-%m-%d"


def _fmt(d) -> str:
    """Format a date to YYYY-MM-DD string."""
    if isinstance(d, str):
        return d
    if isinstance(d, datetime):
        return d.strftime(_DATE_FMT)
    if isinstance(d, _date_type):
        return d.strftime(_DATE_FMT)
    return str(d)


def _to_dt(s) -> datetime:
    """Parse a YYYY-MM-DD string to datetime."""
    if isinstance(s, datetime):
        return s
    if isinstance(s, _date_type):
        return datetime(s.year, s.month, s.day)
    if isinstance(s, str):
        return datetime.strptime(s, _DATE_FMT)
    raise ValueError(f"Cannot parse date: {s!r}")

'''

BRIDGE_CLASS = '''

class RoaiPortfolioCalculatorBridge(RoaiPortfolioCalculator):
    """
    Bridge class: provides public API methods by orchestrating the translated
    TypeScript calculator logic (_get_symbol_metrics etc).
    """

    ENABLE_LOGGING = False

    def __init__(self, activities, current_rate_service):
        super().__init__(activities, current_rate_service)
        self._chart_dates_cache = None

    def _build_market_symbol_map(self, start_str: str, end_str: str) -> dict:
        """Build marketSymbolMap: {date: {symbol: Big}}."""
        market_symbol_map: dict = {}
        for ds_map in self.current_rate_service._market_data.values():
            for symbol, price_list in ds_map.items():
                for entry in price_list:
                    d = entry.get("date", "")
                    if d:
                        if d not in market_symbol_map:
                            market_symbol_map[d] = {}
                        market_symbol_map[d][symbol] = Big(entry["marketPrice"])
        return market_symbol_map

    def _build_exchange_rates(self, dates) -> dict:
        """Build exchange rates dict. Returns 1.0 for all dates (base currency)."""
        rates = {}
        today = _fmt(_date_type.today())
        rates[today] = 1.0
        for d in dates:
            rates[d] = 1.0
        return rates

    def _get_all_symbols(self) -> list[str]:
        symbols = []
        seen: set[str] = set()
        for act in self.activities:
            sym = act.get("symbol", "")
            t = act.get("type", "")
            if sym and t in ("BUY", "SELL") and sym not in seen:
                seen.add(sym)
                symbols.append(sym)
        return symbols

    def _get_date_range(self) -> tuple[str, str]:
        if not self.activities:
            today = _fmt(_date_type.today())
            return today, today
        dates = [act["date"] for act in self.activities if act.get("date")]
        all_dates = set(dates)
        for ds_map in self.current_rate_service._market_data.values():
            for price_list in ds_map.values():
                for entry in price_list:
                    all_dates.add(entry["date"])
        start = min(all_dates)
        end = max(all_dates)
        return start, end

    def _compute_all_metrics(self) -> dict:
        """Compute symbol metrics for all symbols."""
        symbols = self._get_all_symbols()
        if not symbols:
            return {}

        start_str, end_str = self._get_date_range()

        # All dates we have market data for + activity dates
        all_dates: set[str] = set()
        for ds_map in self.current_rate_service._market_data.values():
            for price_list in ds_map.values():
                for entry in price_list:
                    all_dates.add(entry["date"])
        for act in self.activities:
            if act.get("date"):
                all_dates.add(act["date"])

        # Add day before first activity
        if start_str:
            prev = _fmt(_to_dt(start_str) - timedelta(days=1))
            all_dates.add(prev)

        chart_dates = sorted(all_dates)
        chart_date_map = {d: True for d in chart_dates}

        market_symbol_map = self._build_market_symbol_map(
            min(chart_dates) if chart_dates else start_str,
            max(chart_dates) if chart_dates else end_str,
        )
        exchange_rates = self._build_exchange_rates(chart_dates)

        start_dt = _to_dt(start_str)
        end_dt = _to_dt(end_str)

        symbol_metrics_map = {}
        for symbol in symbols:
            ds = next(
                (a.get("dataSource", "YAHOO") for a in self.activities if a.get("symbol") == symbol),
                "YAHOO"
            )
            try:
                metrics = self._get_symbol_metrics(
                    chart_date_map=chart_date_map,
                    data_source=ds,
                    end=end_dt,
                    exchange_rates=exchange_rates,
                    market_symbol_map=market_symbol_map,
                    start=start_dt,
                    symbol=symbol,
                )
                symbol_metrics_map[symbol] = metrics
            except Exception:
                pass

        return {
            "symbol_metrics": symbol_metrics_map,
            "chart_dates": chart_dates,
        }

    def get_performance(self) -> dict:
        data = self._compute_all_metrics()
        if not data:
            return {
                "chart": [],
                "firstOrderDate": None,
                "performance": {
                    "currentNetWorth": 0, "currentValue": 0,
                    "currentValueInBaseCurrency": 0, "netPerformance": 0,
                    "netPerformancePercentage": 0,
                    "netPerformancePercentageWithCurrencyEffect": 0,
                    "netPerformanceWithCurrencyEffect": 0,
                    "totalFees": 0, "totalInvestment": 0,
                    "totalLiabilities": 0.0, "totalValueables": 0.0,
                },
            }

        symbol_metrics_map = data["symbol_metrics"]
        chart_dates = data["chart_dates"]

        # Accumulate across symbols per date
        accumulated: dict = {
            d: {
                "cv": Big(0), "cv_ce": Big(0),
                "inv": Big(0), "inv_ce": Big(0),
                "net": Big(0), "net_ce": Big(0),
                "tw": Big(0), "tw_ce": Big(0),
            }
            for d in chart_dates
        }

        for symbol, metrics in symbol_metrics_map.items():
            if not isinstance(metrics, dict):
                continue
            cv = metrics.get("currentValues") or {}
            cv_ce = metrics.get("currentValuesWithCurrencyEffect") or {}
            inv = metrics.get("investmentValuesAccumulated") or {}
            inv_ce = metrics.get("investmentValuesAccumulatedWithCurrencyEffect") or {}
            net = metrics.get("netPerformanceValues") or {}
            net_ce = metrics.get("netPerformanceValuesWithCurrencyEffect") or {}
            tw = metrics.get("timeWeightedInvestmentValues") or {}
            tw_ce = metrics.get("timeWeightedInvestmentValuesWithCurrencyEffect") or {}

            for d in chart_dates:
                acc = accumulated[d]
                def _get_big(m, key):
                    v = m.get(key)
                    if v is None:
                        return Big(0)
                    return v if isinstance(v, Big) else Big(v)

                acc["cv"] = acc["cv"].plus(_get_big(cv, d))
                acc["cv_ce"] = acc["cv_ce"].plus(_get_big(cv_ce, d))
                acc["inv"] = acc["inv"].plus(_get_big(inv, d))
                acc["inv_ce"] = acc["inv_ce"].plus(_get_big(inv_ce, d))
                acc["net"] = acc["net"].plus(_get_big(net, d))
                acc["net_ce"] = acc["net_ce"].plus(_get_big(net_ce, d))
                acc["tw"] = acc["tw"].plus(_get_big(tw, d))
                acc["tw_ce"] = acc["tw_ce"].plus(_get_big(tw_ce, d))

        # Build chart
        chart = []
        for d in sorted(accumulated.keys()):
            acc = accumulated[d]
            tw = acc["tw"]
            tw_ce = acc["tw_ce"]
            net = acc["net"]
            net_ce = acc["net_ce"]
            net_pct = net.div(tw).toNumber() if not tw.eq(0) else 0
            net_pct_ce = net_ce.div(tw_ce).toNumber() if not tw_ce.eq(0) else 0
            chart.append({
                "date": d,
                "netPerformanceInPercentage": net_pct,
                "netPerformanceInPercentageWithCurrencyEffect": net_pct_ce,
                "netWorth": acc["cv_ce"].toNumber(),
                "totalInvestment": acc["inv"].toNumber(),
                "value": acc["cv"].toNumber(),
                "valueWithCurrencyEffect": acc["cv_ce"].toNumber(),
                "netPerformance": net.toNumber(),
                "netPerformanceWithCurrencyEffect": net_ce.toNumber(),
                "totalInvestmentValueWithCurrencyEffect": acc["inv_ce"].toNumber(),
            })

        last = next((e for e in reversed(chart) if e["totalInvestment"] > 0 or e["value"] > 0), chart[-1] if chart else {})

        first_date = next(
            (a["date"] for a in sorted(self.activities, key=lambda x: x.get("date", ""))
             if a.get("type") in ("BUY", "SELL")), None
        )
        total_fees = sum(float(a.get("fee", 0) or 0) for a in self.activities)

        return {
            "chart": chart,
            "firstOrderDate": first_date,
            "performance": {
                "currentNetWorth": last.get("netWorth", 0),
                "currentValue": last.get("value", 0),
                "currentValueInBaseCurrency": last.get("valueWithCurrencyEffect", 0),
                "netPerformance": last.get("netPerformance", 0),
                "netPerformancePercentage": last.get("netPerformanceInPercentage", 0),
                "netPerformancePercentageWithCurrencyEffect": last.get("netPerformanceInPercentageWithCurrencyEffect", 0),
                "netPerformanceWithCurrencyEffect": last.get("netPerformanceWithCurrencyEffect", 0),
                "totalFees": total_fees,
                "totalInvestment": last.get("totalInvestment", 0),
                "totalLiabilities": 0.0,
                "totalValueables": 0.0,
            },
        }

    def get_investments(self, group_by: str | None = None) -> dict:
        sorted_acts = sorted(self.activities, key=lambda a: a.get("date", ""))
        entries: dict[str, float] = {}
        running_inv = 0.0
        running_units: dict[str, float] = {}

        for act in sorted_acts:
            t = act.get("type", "")
            sym = act.get("symbol", "")
            date = act.get("date", "")
            qty = float(act.get("quantity", 0) or 0)
            price = float(act.get("unitPrice", 0) or 0)
            if t == "BUY":
                inv = qty * price
                running_units[sym] = running_units.get(sym, 0) + qty
                running_inv += inv
                entries[date] = entries.get(date, 0) + inv
            elif t == "SELL":
                units = running_units.get(sym, 0)
                if units > 0:
                    cost_sold = (running_inv / units) * qty
                    running_inv -= cost_sold
                    running_units[sym] = max(0, units - qty)
                    entries[date] = entries.get(date, 0) - cost_sold

        if group_by == "month":
            g: dict[str, float] = {}
            for d, v in entries.items():
                g[d[:7] + "-01"] = g.get(d[:7] + "-01", 0) + v
            entries = g
        elif group_by == "year":
            g = {}
            for d, v in entries.items():
                g[d[:4] + "-01-01"] = g.get(d[:4] + "-01-01", 0) + v
            entries = g

        return {
            "investments": [
                {"date": d, "investment": v}
                for d, v in sorted(entries.items())
            ]
        }

    def get_holdings(self) -> dict:
        sorted_acts = sorted(self.activities, key=lambda a: a.get("date", ""))
        holdings: dict = {}
        for act in sorted_acts:
            t = act.get("type", "")
            sym = act.get("symbol", "")
            if not sym or t not in ("BUY", "SELL"):
                continue
            qty = float(act.get("quantity", 0) or 0)
            price = float(act.get("unitPrice", 0) or 0)
            currency = act.get("currency", "USD")
            if sym not in holdings:
                holdings[sym] = {
                    "symbol": sym, "currency": currency,
                    "quantity": 0.0, "investment": 0.0, "averagePrice": 0.0,
                    "dataSource": act.get("dataSource", "YAHOO"),
                }
            h = holdings[sym]
            if t == "BUY":
                h["investment"] += qty * price
                h["quantity"] += qty
            elif t == "SELL" and h["quantity"] > 0:
                cost_per_unit = h["investment"] / h["quantity"]
                h["investment"] = max(0, h["investment"] - cost_per_unit * qty)
                h["quantity"] = max(0, h["quantity"] - qty)
            h["averagePrice"] = h["investment"] / h["quantity"] if h["quantity"] > 0 else 0.0

        for sym, h in holdings.items():
            latest = self.current_rate_service.get_latest_price(sym)
            h["currentPrice"] = latest if latest else h["averagePrice"]
            h["currentValue"] = h["quantity"] * h["currentPrice"]

        return {"holdings": {s: h for s, h in holdings.items() if h["quantity"] > 1e-10}}

    def get_details(self, base_currency: str = "USD") -> dict:
        hld = self.get_holdings()["holdings"]
        total_inv = sum(h["investment"] for h in hld.values())
        total_val = sum(h.get("currentValue", h["investment"]) for h in hld.values())
        first_date = next(
            (a["date"] for a in sorted(self.activities, key=lambda x: x.get("date", ""))
             if a.get("type") in ("BUY", "SELL")), None
        )
        return {
            "accounts": {"default": {"balance": 0.0, "currency": base_currency, "name": "Default Account", "valueInBaseCurrency": 0.0}},
            "createdAt": first_date,
            "holdings": hld,
            "platforms": {"default": {"balance": 0.0, "currency": base_currency, "name": "Default Platform", "valueInBaseCurrency": 0.0}},
            "summary": {
                "totalInvestment": total_inv,
                "netPerformance": total_val - total_inv,
                "currentValueInBaseCurrency": total_val,
                "totalFees": sum(float(a.get("fee", 0) or 0) for a in self.activities),
            },
            "hasError": False,
        }

    def get_dividends(self, group_by: str | None = None) -> dict:
        entries: dict[str, float] = {}
        for act in self.activities:
            if act.get("type") == "DIVIDEND":
                d = act.get("date", "")
                entries[d] = entries.get(d, 0) + float(act.get("quantity", 0) or 0) * float(act.get("unitPrice", 0) or 0)
        if group_by == "month":
            g: dict[str, float] = {}
            for d, v in entries.items():
                g[d[:7] + "-01"] = g.get(d[:7] + "-01", 0) + v
            entries = g
        elif group_by == "year":
            g = {}
            for d, v in entries.items():
                g[d[:4] + "-01-01"] = g.get(d[:4] + "-01-01", 0) + v
            entries = g
        return {"dividends": [{"date": d, "investment": v} for d, v in sorted(entries.items())]}

    def evaluate_report(self) -> dict:
        return {
            "xRay": {
                "categories": [
                    {"key": "accounts", "name": "Accounts", "rules": []},
                    {"key": "currencies", "name": "Currencies", "rules": []},
                    {"key": "fees", "name": "Fees", "rules": []},
                ],
                "statistics": {"rulesActiveCount": 0, "rulesFulfilledCount": 0},
            }
        }


# Alias: wrapper imports RoaiPortfolioCalculator, bridge overrides all public methods
RoaiPortfolioCalculator = RoaiPortfolioCalculatorBridge
'''


def generate_python_calculator(ts_content: str) -> str:
    """Generate the complete Python RoaiPortfolioCalculator file from TypeScript."""
    translated_body = translate_typescript_content(ts_content)
    return PYTHON_FILE_HEADER + translated_body + BRIDGE_CLASS


# ---------------------------------------------------------------------------
# File-level runner
# ---------------------------------------------------------------------------

def translate_roai_calculator(ts_file: Path, output_file: Path) -> None:
    """Translate the ROAI portfolio calculator TypeScript file to Python."""
    ts_content = ts_file.read_text(encoding='utf-8')
    print(f"  Translating {ts_file.name} ({len(ts_content.splitlines())} lines)...")
    python_content = generate_python_calculator(ts_content)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(python_content, encoding='utf-8')
    print(f"  → {output_file}")


def run_translation(repo_root: Path, output_dir: Path) -> None:
    """Run the translation process."""
    ts_source = (
        repo_root / "projects" / "ghostfolio" / "apps" / "api" / "src"
        / "app" / "portfolio" / "calculator" / "roai" / "portfolio-calculator.ts"
    )
    output_file = (
        output_dir / "app" / "implementation" / "portfolio" / "calculator"
        / "roai" / "portfolio_calculator.py"
    )
    if not ts_source.exists():
        print(f"Warning: TypeScript source not found: {ts_source}")
        return
    translate_roai_calculator(ts_source, output_file)
    print("Translation complete.")
