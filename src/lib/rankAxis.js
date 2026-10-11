// ECharts 5 rounds native log-axis ticks to 10 decimal places. Normalize only
// the plotted coordinates, then divide tick labels by factor; scientific
// values in records, tooltips and downloads remain unchanged.
export function rankLogAxis(values) {
  const positive = values.filter(value => Number.isFinite(value) && value > 0);
  const lowest = positive.length ? Math.min(...positive) : 1;
  const highest = positive.length ? Math.max(...positive) : 1;
  const exponent = Math.max(-300, Math.min(300,
    1 - Math.floor(Math.log10(lowest)),
    Math.floor(307 - Math.log10(highest)),
  ));
  const factor = 10 ** exponent;
  const scaledLowest = lowest * factor;
  const scaledHighest = highest * factor;
  let min = 10 ** Math.floor(Math.log10(scaledLowest));
  // A value exactly on the baseline would produce an invisible bar.
  if (min >= scaledLowest * (1 - 1e-12)) min /= 10;
  min = Math.max(Number.MIN_VALUE, min);
  const max = Math.max(min * 10, 10 ** Math.ceil(Math.log10(scaledHighest)));
  return { factor, min, max, interval: 1 };
}
