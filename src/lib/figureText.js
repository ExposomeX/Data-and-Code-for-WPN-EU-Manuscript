// Manuscript asset identifiers stay unchanged; visible numbering belongs to each page.
export function unnumberedFigureText(value = '') {
  return value.replace(/^(?:Extended Data\s+)?Fig(?:ure)?\.?\s*S?\d+[a-z]?\s*(?:[.|:–—-]\s*)?/i, '').trim();
}
