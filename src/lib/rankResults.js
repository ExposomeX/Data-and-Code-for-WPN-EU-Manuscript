// One display record feeds the table, chart and download. Stored ranks and
// contributions are retained when the table is searched or the chart is zoomed.
export function currentRankRows(result) {
  return (result?.rows || []).map(row => ({
    chemical: row.chemical, rank: row.beqRank, ww: row.ww,
    beq: row.beq, contribution: row.beqContribution,
  })).sort((a, b) => a.rank - b.rank);
}

export function studyRankRows(records) {
  const wwById = new Map(records.filter(row => row.metric === 'WW_nM').map(row => [row.chemical, row.mean]));
  return records.filter(row => row.metric === 'BEQ_ugL').map(row => ({
    chemical: row.chemical, rank: row.meanRank, ww: wwById.get(row.chemical) ?? null,
    beq: row.mean, contribution: row.contribution,
  })).sort((a, b) => a.rank - b.rank);
}

export function cumulativeRankRows(rows) {
  let total = 0;
  return rows.map(row => {
    total += row.contribution;
    // Round only floating-point noise at 100%; keep original row contributions.
    const cumulative = Math.abs(total - 100) < 1e-9 ? 100 : total;
    return { ...row, cumulative };
  });
}

export function rankCsvColumns(labelFor) {
  return [
    { header: 'Rank', value: 'rank' },
    { header: 'Chemical', value: row => labelFor(row.chemical) },
    { header: 'WW input (nM)', value: 'ww' },
    { header: 'BEQ (μg/L Narciclasine-EQ)', value: 'beq' },
    { header: 'Contribution (%)', value: 'contribution' },
  ];
}
