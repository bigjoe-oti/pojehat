export function formatDiagnosticResponse(raw: string): string {
  return raw
    .replace(
      /\[\[BAR:(\d+)\]\]/g,
      (_, pctStr) => {
        const pct = parseInt(pctStr, 10);
        let color = '#e24b4a'; // Red
        if (pct >= 70) color = '#639922'; // Green
        else if (pct >= 40) color = '#ef9f27'; // Orange

        return `<div style="display:flex;flex-direction:column;align-items:flex-start;gap:4px;margin-bottom:8px">
<span class="poj-bar-track" style="margin-left:0;width:120px;height:8px;background-color:#eee;border-radius:4px;overflow:hidden">
<span class="poj-bar-fill" style="display:block;height:100%;width:${pct}%;background-color:${color};transition:width 0.3s ease"></span>
</span>
<span style="font-size:0.95em;font-weight:800;color:${color};line-height:1.2">${pct}%</span>
</div>`;
      }
    )
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
