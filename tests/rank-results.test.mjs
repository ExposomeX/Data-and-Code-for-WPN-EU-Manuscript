import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc';
import { currentRankRows, studyRankRows, cumulativeRankRows, rankCsvColumns } from '../src/lib/rankResults.js';
import { csvText } from '../src/lib/data.js';

const records = JSON.parse(fs.readFileSync(new URL('../public/data/ranks.json', import.meta.url), 'utf8'));
const catalog = JSON.parse(fs.readFileSync(new URL('../public/data/chemical-catalog.json', import.meta.url), 'utf8'));

test('study view reproduces all 52 frozen mean BEQ ranks with matched mean WW values', () => {
  const rows = studyRankRows(records);
  assert.equal(rows.length, 52);
  assert.equal(new Set(rows.map(row => row.chemical)).size, 52);
  assert.deepEqual(rows.map(row => row.rank), Array.from({ length: 52 }, (_, index) => index + 1));
  assert.equal(rows[0].chemical, 'DMSMPAJRVJJAGA-UHFFFAOYSA-N');
  assert.ok(Math.abs(rows[0].contribution - 92.03) < 0.01);
  for (const row of rows) {
    const ww = records.find(record => record.chemical === row.chemical && record.metric === 'WW_nM');
    const beq = records.find(record => record.chemical === row.chemical && record.metric === 'BEQ_ugL');
    assert.equal(row.ww, ww.mean);
    assert.equal(row.beq, beq.mean);
    assert.equal(row.contribution, beq.contribution);
    assert.ok(catalog.chemicals.find(chemical => chemical.id === row.chemical)?.nt52);
  }
});

test('a subset result contains only the submitted chemicals and preserves their stored contributions', () => {
  const result = { rows: [
    { chemical: 'B', beqRank: 2, ww: 20, beq: 1, beqContribution: 25, de: 42, cb: 12 },
    { chemical: 'A', beqRank: 1, ww: 10, beq: 3, beqContribution: 75, de: 37, cb: 11 },
  ], baseline: { rows: [{ chemical: 'unused', beq: 99 }] } };
  const rows = currentRankRows(result);
  assert.deepEqual(rows.map(row => row.chemical), ['A', 'B']);
  assert.deepEqual(rows.map(row => row.contribution), [75, 25]);
  assert.deepEqual(cumulativeRankRows(rows).map(row => row.cumulative), [75, 100]);
  assert.deepEqual(Object.keys(rows[0]), ['chemical', 'rank', 'ww', 'beq', 'contribution']);
  assert.deepEqual(result.rows.map(row => row.chemical), ['B', 'A']);
});

test('a single submitted chemical reaches 100% without filling the other 51 entries', () => {
  const rows = currentRankRows({ rows: [{ chemical: 'A', beqRank: 1, ww: 2, beq: 0.001, beqContribution: 100 }] });
  assert.equal(rows.length, 1);
  assert.equal(cumulativeRankRows(rows)[0].cumulative, 100);
});

test('study cumulative percentages use the stored full study contributions', () => {
  const rows = studyRankRows(records);
  const cumulative = cumulativeRankRows(rows);
  assert.equal(cumulative[0].cumulative, rows[0].contribution);
  assert.equal(cumulative.at(-1).cumulative, 100);
  const visibleRange = cumulative.slice(12, 20);
  assert.equal(visibleRange[0].cumulative, rows.slice(0, 13).reduce((sum, row) => sum + row.contribution, 0));
  assert.ok(visibleRange[0].cumulative > visibleRange[0].contribution);
});

test('CSV exports the same five user fields and stored precision with no intermediate or baseline fields', () => {
  const rows = studyRankRows(records);
  const columns = rankCsvColumns(id => catalog.chemicals.find(row => row.id === id).name);
  assert.deepEqual(columns.map(column => column.header), ['Rank', 'Chemical', 'WW input (nM)', 'BEQ (μg/L Narciclasine-EQ)', 'Contribution (%)']);
  const selected = rows.filter(row => row.rank === 13);
  const csv = csvText(columns, selected);
  assert.equal(csv.split('\r\n').length, 2);
  assert.ok(csv.includes(`"13"`));
  assert.ok(csv.includes(String(selected[0].beq)));
  assert.ok(csv.includes(String(selected[0].contribution)));
  assert.doesNotMatch(csv, /default|baseline|created_at|model_version|\bDE\b|\bCb\b/);
});

test('Rank component compiles with the new Data and Figure views', () => {
  const filename = new URL('../src/components/RankExplorer.vue', import.meta.url).pathname;
  const source = fs.readFileSync(new URL('../src/components/RankExplorer.vue', import.meta.url), 'utf8');
  const parsed = parse(source, { filename });
  assert.deepEqual(parsed.errors, []);
  const script = compileScript(parsed.descriptor, { id: 'rank-results' });
  const template = compileTemplate({ id: 'rank-results', source: parsed.descriptor.template.content, filename, compilerOptions: { bindingMetadata: script.bindings } });
  assert.deepEqual(template.errors, []);
});
