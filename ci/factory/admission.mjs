// Admission: allow or block a merge by comparing the evidence present for a
// commit with the evidence its risk tier requires.
//
// A record is { check, status: "pass" | "fail" | "skipped", sha, details? }.
// Only records for the exact commit being judged count.

const ICON = { pass: '✅', fail: '❌', missing: '⚪', skipped: '➖' };

// input: { sha, tier, required: [{ name, mode, about }], records, needsHuman, override, reasons }
export function decide(input) {
  const rows = [];
  const blocking = [];
  for (const req of input.required) {
    const rec = input.records.find((r) => r.check === req.name && r.sha === input.sha);
    const stale = !rec && input.records.some((r) => r.check === req.name);
    const status = rec ? rec.status : 'missing';
    const ok = status === 'pass' || (status === 'skipped' && rec.details === 'nothing affected');
    if (!ok && req.mode === 'enforce') {
      blocking.push(stale ? `${req.name} (evidence is for another commit)` : `${req.name} (${status})`);
    }
    rows.push({ ...req, status, details: rec?.details || (stale ? 'evidence is for another commit' : '') });
  }
  if (input.needsHuman) {
    const approval = input.records.find((r) => r.check === 'human-approval' && r.status === 'pass');
    rows.push({ name: 'human-approval', mode: 'enforce', about: 'Agent PR above its trust level', status: approval ? 'pass' : 'missing', details: approval?.details || '' });
    if (!approval) blocking.push('human-approval (missing)');
  }
  const allowed = blocking.length === 0;
  return { allowed, blocking, rows, summary: summary(input, rows, allowed, blocking) };
}

function summary(input, rows, allowed, blocking) {
  const lines = [
    `### Factory admission: ${allowed ? 'allowed' : 'blocked'}`,
    '',
    `Risk tier **${input.tier}**${input.reasons?.length ? ` (${input.reasons.join('; ')})` : ''}. Commit \`${input.sha.slice(0, 12)}\`.`,
  ];
  if (input.override) lines.push('', '⚠️ Boundary override in use; this is recorded with the evidence.');
  lines.push('', '| Evidence | Mode | Result | Details |', '| --- | --- | --- | --- |');
  for (const r of rows) {
    lines.push(`| ${r.name} | ${r.mode} | ${ICON[r.status] || ''} ${r.status} | ${(r.details || r.about || '').replace(/\|/g, '\\|')} |`);
  }
  if (!allowed) lines.push('', `Blocked by: ${blocking.join(', ')}.`);
  lines.push('', 'Shadow evidence is reported but never blocks.');
  return lines.join('\n');
}
