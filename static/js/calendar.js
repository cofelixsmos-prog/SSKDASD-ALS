/**
 * Render a monthly attendance calendar into containerId.
 * records: array of { date: "YYYY-MM-DD", status: "present"|"absent"|"late" }
 * Returns { year, month } of what was rendered.
 */
export function renderCalendar(containerId, year, month, records) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const lookup = {};
  records.forEach(r => { lookup[r.date] = r.status; });

  const days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  const monthNames = ['January','February','March','April','May','June',
                      'July','August','September','October','November','December'];

  const firstDay = new Date(year, month - 1, 1).getDay();
  const startOffset = firstDay === 0 ? 6 : firstDay - 1;
  const daysInMonth = new Date(year, month, 0).getDate();

  let html = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.75rem">
      <button class="btn btn-secondary btn-sm" id="cal-prev">←</button>
      <strong style="font-size:.95rem">${monthNames[month-1]} ${year}</strong>
      <button class="btn btn-secondary btn-sm" id="cal-next">→</button>
    </div>
    <div class="calendar-grid">
      ${days.map(d => `<div class="cal-header">${d}</div>`).join('')}
      ${Array(startOffset).fill('<div class="cal-day"></div>').join('')}`;

  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year}-${String(month).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
    const status = lookup[dateStr];
    let cls = 'cal-noclass';
    if (status === 'present') cls = 'cal-present';
    else if (status === 'absent') cls = 'cal-absent';
    else if (status === 'late') cls = 'cal-late';
    html += `<div class="cal-day ${cls}" title="${status || 'no class'}">${d}</div>`;
  }

  html += `</div>
    <div style="display:flex;gap:1rem;flex-wrap:wrap;margin-top:.75rem;font-size:.75rem;font-weight:700;color:var(--text-light)">
      <span><span style="display:inline-block;width:12px;height:12px;border-radius:3px;background:var(--success);margin-right:4px;vertical-align:middle"></span>Present</span>
      <span><span style="display:inline-block;width:12px;height:12px;border-radius:3px;background:var(--danger);margin-right:4px;vertical-align:middle"></span>Absent</span>
      <span><span style="display:inline-block;width:12px;height:12px;border-radius:3px;background:var(--warning);margin-right:4px;vertical-align:middle"></span>Late</span>
      <span><span style="display:inline-block;width:12px;height:12px;border-radius:3px;background:var(--surface2);margin-right:4px;vertical-align:middle"></span>No Class</span>
    </div>`;

  container.innerHTML = html;
}
