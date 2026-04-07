#!/usr/bin/env node
/**
 * Arquero HTTP API
 *
 * Exposes the arquero data-transformation library over REST.
 * Each endpoint accepts JSON data (array of row objects) plus operation
 * parameters, applies the operation, and returns the resulting table.
 *
 * Port: 3336 (override with ARQUERO_PORT env var)
 */
import express from 'express';
import * as aq from 'arquero';

const {
  from, fromCSV, fromJSON, toCSV, toMarkdown, toJSON,
  op, desc, asc, all, not, range, bin, rolling, field,
} = aq;

const PORT = parseInt(process.env.ARQUERO_PORT ?? '3336', 10);
const app = express();
app.use(express.json({ limit: '50mb' }));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Evaluate an expression string with arquero helpers available in scope.
 * Supports arrow functions like "d => d.a + d.b" and helpers like desc('age').
 */
function evalExpr(str) {
  // op, desc, asc, all, not, range, bin, rolling, field are available via closure
  // eslint-disable-next-line no-eval
  return eval(str);
}

/** Evaluate a map of { colName: exprString } into { colName: fn }. */
function evalExprs(obj) {
  return Object.fromEntries(Object.entries(obj).map(([k, v]) => [k, evalExpr(v)]));
}

/** Serialize a table to a plain response object. */
function tableToResponse(t) {
  return {
    rows: t.objects(),
    numRows: t.numRows(),
    numCols: t.numCols(),
    columnNames: t.columnNames(),
  };
}

/** Wrap an endpoint handler with consistent JSON error handling. */
function wrap(fn) {
  return async (req, res) => {
    try {
      await fn(req, res);
    } catch (err) {
      res.status(400).json({ error: err.message });
    }
  };
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

app.get('/health', (_req, res) => res.json({ status: 'ok' }));

// ---------------------------------------------------------------------------
// Table creation
// ---------------------------------------------------------------------------

/** POST /from-json — create table from array of row objects */
app.post('/from-json', wrap((req, res) => {
  const { data } = req.body;
  res.json(tableToResponse(from(data)));
}));

/** POST /from-csv — parse CSV string into a table */
app.post('/from-csv', wrap((req, res) => {
  const { csv, options } = req.body;
  res.json(tableToResponse(fromCSV(csv, options ?? undefined)));
}));

// ---------------------------------------------------------------------------
// Column operations
// ---------------------------------------------------------------------------

/** POST /select — select columns by name array */
app.post('/select', wrap((req, res) => {
  const { data, columns } = req.body;
  res.json(tableToResponse(from(data).select(columns)));
}));

/** POST /rename — rename columns: { oldName: newName, ... } */
app.post('/rename', wrap((req, res) => {
  const { data, columns } = req.body;
  res.json(tableToResponse(from(data).rename(columns)));
}));

/** POST /relocate — reorder columns: columns array + { before/after } options */
app.post('/relocate', wrap((req, res) => {
  const { data, columns, options } = req.body;
  res.json(tableToResponse(from(data).relocate(columns, options ?? undefined)));
}));

/** POST /derive — compute new columns: { name: "d => expr" } */
app.post('/derive', wrap((req, res) => {
  const { data, columns } = req.body;
  res.json(tableToResponse(from(data).derive(evalExprs(columns))));
}));

/** POST /assign — assign columns from a second table (same row count) */
app.post('/assign', wrap((req, res) => {
  const { data, other } = req.body;
  res.json(tableToResponse(from(data).assign(from(other))));
}));

// ---------------------------------------------------------------------------
// Row operations
// ---------------------------------------------------------------------------

/** POST /filter — filter rows: expr "d => boolean" */
app.post('/filter', wrap((req, res) => {
  const { data, expr } = req.body;
  res.json(tableToResponse(from(data).filter(evalExpr(expr))));
}));

/** POST /orderby — sort rows: exprs array of column names or "desc('col')" strings */
app.post('/orderby', wrap((req, res) => {
  const { data, exprs: exprStrs } = req.body;
  const exprs = exprStrs.map(e =>
    typeof e === 'string' && (e.includes('=>') || e.startsWith('desc') || e.startsWith('asc'))
      ? evalExpr(e)
      : e
  );
  res.json(tableToResponse(from(data).orderby(...exprs)));
}));

/** POST /slice — slice rows from start (inclusive) to end (exclusive) */
app.post('/slice', wrap((req, res) => {
  const { data, start, end } = req.body;
  res.json(tableToResponse(from(data).slice(start, end)));
}));

/** POST /sample — randomly sample n rows */
app.post('/sample', wrap((req, res) => {
  const { data, n, options } = req.body;
  res.json(tableToResponse(from(data).sample(n, options ?? undefined)));
}));

/** POST /dedupe — remove duplicate rows (optionally based on specific columns) */
app.post('/dedupe', wrap((req, res) => {
  const { data, columns } = req.body;
  const t = columns ? from(data).dedupe(...columns) : from(data).dedupe();
  res.json(tableToResponse(t));
}));

/** POST /impute — fill missing values: { colName: fillValue } */
app.post('/impute', wrap((req, res) => {
  const { data, values } = req.body;
  res.json(tableToResponse(from(data).impute(values)));
}));

// ---------------------------------------------------------------------------
// Aggregation
// ---------------------------------------------------------------------------

/** POST /rollup — aggregate entire table: { name: "d => op.sum(d.col)" } */
app.post('/rollup', wrap((req, res) => {
  const { data, rollup: rollupDef } = req.body;
  res.json(tableToResponse(from(data).rollup(evalExprs(rollupDef))));
}));

/** POST /groupby-rollup — group then aggregate */
app.post('/groupby-rollup', wrap((req, res) => {
  const { data, by, rollup: rollupDef } = req.body;
  res.json(tableToResponse(from(data).groupby(by).rollup(evalExprs(rollupDef))));
}));

// ---------------------------------------------------------------------------
// Reshaping
// ---------------------------------------------------------------------------

/** POST /fold — melt wide columns to key/value rows */
app.post('/fold', wrap((req, res) => {
  const { data, columns, options } = req.body;
  res.json(tableToResponse(from(data).fold(columns, options ?? undefined)));
}));

/** POST /pivot — pivot key/value rows to wide columns */
app.post('/pivot', wrap((req, res) => {
  const { data, on, values, options } = req.body;
  res.json(tableToResponse(from(data).pivot(on, values, options ?? undefined)));
}));

/** POST /spread — spread an array column into multiple columns */
app.post('/spread', wrap((req, res) => {
  const { data, columns, options } = req.body;
  res.json(tableToResponse(from(data).spread(columns, options ?? undefined)));
}));

/** POST /unroll — expand an array column into multiple rows */
app.post('/unroll', wrap((req, res) => {
  const { data, columns, options } = req.body;
  res.json(tableToResponse(from(data).unroll(columns, options ?? undefined)));
}));

// ---------------------------------------------------------------------------
// Joins
// ---------------------------------------------------------------------------

/** POST /join — join two tables: how = inner|left|right|full */
app.post('/join', wrap((req, res) => {
  const { left, right, on, how } = req.body;
  const lt = from(left);
  const rt = from(right);
  let t;
  if (how === 'left')       t = lt.join_left(rt, on);
  else if (how === 'right') t = lt.join_right(rt, on);
  else if (how === 'full')  t = lt.join_full(rt, on);
  else                      t = lt.join(rt, on);
  res.json(tableToResponse(t));
}));

/** POST /semijoin — keep rows in left that match right */
app.post('/semijoin', wrap((req, res) => {
  const { left, right, on } = req.body;
  res.json(tableToResponse(from(left).semijoin(from(right), on)));
}));

/** POST /antijoin — keep rows in left that do NOT match right */
app.post('/antijoin', wrap((req, res) => {
  const { left, right, on } = req.body;
  res.json(tableToResponse(from(left).antijoin(from(right), on)));
}));

/** POST /cross — cartesian product of two tables */
app.post('/cross', wrap((req, res) => {
  const { left, right } = req.body;
  res.json(tableToResponse(from(left).cross(from(right))));
}));

// ---------------------------------------------------------------------------
// Set operations
// ---------------------------------------------------------------------------

/** POST /union — union of multiple tables (deduped) */
app.post('/union', wrap((req, res) => {
  const { tables } = req.body;
  const [first, ...rest] = tables.map(d => from(d));
  res.json(tableToResponse(first.union(...rest)));
}));

/** POST /intersect — rows present in all tables */
app.post('/intersect', wrap((req, res) => {
  const { tables } = req.body;
  const [first, ...rest] = tables.map(d => from(d));
  res.json(tableToResponse(first.intersect(...rest)));
}));

/** POST /except — rows in first table not in remaining tables */
app.post('/except', wrap((req, res) => {
  const { tables } = req.body;
  const [first, ...rest] = tables.map(d => from(d));
  res.json(tableToResponse(first.except(...rest)));
}));

/** POST /concat — concatenate tables (no dedup) */
app.post('/concat', wrap((req, res) => {
  const { tables } = req.body;
  const [first, ...rest] = tables.map(d => from(d));
  res.json(tableToResponse(first.concat(...rest)));
}));

// ---------------------------------------------------------------------------
// Format output
// ---------------------------------------------------------------------------

/** POST /to-csv — serialize table to CSV string */
app.post('/to-csv', wrap((req, res) => {
  const { data, options } = req.body;
  res.json({ csv: toCSV(from(data), options ?? undefined) });
}));

/** POST /to-markdown — serialize table to Markdown table string */
app.post('/to-markdown', wrap((req, res) => {
  const { data } = req.body;
  res.json({ markdown: toMarkdown(from(data)) });
}));

/** POST /to-json — serialize table to JSON string */
app.post('/to-json', wrap((req, res) => {
  const { data, options } = req.body;
  res.json({ json: toJSON(from(data), options ?? undefined) });
}));

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

app.listen(PORT, '127.0.0.1', () => {
  console.log(`Arquero API listening on http://127.0.0.1:${PORT}`);
});
