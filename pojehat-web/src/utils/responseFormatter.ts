export function formatDiagnosticResponse(raw: string): string {
  return raw
    .replace(
      /([○◆▸⚠●■])/g,
      '<span class="symbol-icon">$1</span>'
    )
    // 1) Target DTCs explicitly wrapped in backticks and turn them directly into pills (avoids nested <code> inside pill)
    .replace(
      /`([PBCU]\d{4,5})`/g,
      '<span class="dtc-pill">$1</span>'
    )
    // 2) Catch naked DTCs that aren't already part of an HTML tag or wrapped
    .replace(
      /(^|[^`'">a-zA-Z-])([PBCU]\d{4,5})(?=[^`'"<a-zA-Z-]|$)/g,
      '$1<span class="dtc-pill">$2</span>'
    )
    .replace(
      /\bp\/n\s+([A-Z0-9-]+)/gi,
      'p/n <span class="part-num">$1</span>'
    )
}
