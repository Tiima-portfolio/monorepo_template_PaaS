// Weekly factory metrics: flow and outcomes, not activity. Pure functions;
// metrics-report-cli.mjs fetches the data.

const hours = (a, b) => (new Date(b) - new Date(a)) / 3600000;
function pct(values, p) {
  if (!values.length) return null;
  const s = [...values].sort((x, y) => x - y);
  return Math.round(s[Math.min(s.length - 1, Math.floor((p / 100) * s.length))] * 10) / 10;
}

// prs: merged PRs [{ number, author, createdAt, mergedAt, labels, body }]
// issues: [{ title, labels, createdAt, closedAt, state }]
// runs: factory runs on PRs [{ conclusion }]
export function report({ prs, issues, runs, agents = [], since, until }) {
  const lead = prs.map((p) => hours(p.createdAt, p.mergedAt));
  const features = {};
  for (const p of prs) {
    const f = /^Feature-Id:\s*(\S+)/m.exec(p.body || '')?.[1];
    if (f) (features[f] ||= []).push(hours(p.createdAt, p.mergedAt));
  }
  const label = (l) => issues.filter((i) => i.labels.includes(l));
  const openedThisWeek = (l) => label(l).filter((i) => i.createdAt >= since).length;
  const openNow = (l) => label(l).filter((i) => i.state === 'open');
  const failed = runs.filter((r) => r.conclusion === 'failure').length;
  const agentPrs = prs.filter((p) => agents.includes(p.author));
  const lines = [
    `## Factory metrics, ${since.slice(0, 10)} to ${until.slice(0, 10)}`,
    '',
    '| Measure | Value |',
    '| --- | --- |',
    `| PRs merged | ${prs.length} (${agentPrs.length} by agents) |`,
    `| Lead time, PR opened to merged | median ${pct(lead, 50) ?? '-'} h, p90 ${pct(lead, 90) ?? '-'} h |`,
    `| Factory runs blocked | ${runs.length ? Math.round((failed / runs.length) * 100) : 0}% of ${runs.length} |`,
    `| Boundary overrides | ${prs.filter((p) => p.labels.includes('boundary-override')).length} |`,
    `| Hotfixes | ${prs.filter((p) => p.labels.includes('hotfix')).length} |`,
    `| Escapes opened / open now | ${openedThisWeek('escape')} / ${openNow('escape').length} |`,
    `| Quarantined tests open | ${openNow('quarantine').length}${openNow('quarantine').length ? ` (oldest ${Math.round(Math.max(...openNow('quarantine').map((i) => hours(i.createdAt, until))) / 24)} days)` : ''} |`,
    `| Test strength drops open | ${openNow('test-adequacy').length} |`,
  ];
  const fs = Object.entries(features);
  if (fs.length) {
    lines.push('', '| Feature | PRs | Lead time, p90 |', '| --- | --- | --- |');
    for (const [f, v] of fs.sort((a, b) => b[1].length - a[1].length).slice(0, 15)) lines.push(`| ${f} | ${v.length} | ${pct(v, 90)} h |`);
  }
  return lines.join('\n');
}
