// Flaky test handling, per project test target.
//
// A failing test target is retried once. A pass on the retry only makes it a
// suspect: the factory reruns it FLAKE_RERUNS times on the same commit, and it
// is a confirmed flake only if those runs both pass and fail. A quarantine
// lasts at most 5 working days; while it lasts the target must still pass at
// least one of three runs, so a broken test can't hide behind it.

export const FLAKE_RERUNS = 20;
export const QUARANTINE_WORKING_DAYS = 5;
export const QUARANTINE_ATTEMPTS = 3;

export function workingDaysBetween(from, to) {
  let days = 0;
  const d = new Date(from);
  while (d < to) {
    d.setUTCDate(d.getUTCDate() + 1);
    const wd = d.getUTCDay();
    if (wd !== 0 && wd !== 6 && d <= to) days++;
  }
  return days;
}

// issues: [{ title, created_at }] open issues labelled "quarantine", titled
// "quarantine: <project>:test". Returns the projects still in quarantine.
export function activeQuarantine(issues, now = new Date()) {
  const active = new Set();
  for (const i of issues) {
    const m = /^quarantine: (.+):test$/.exec(i.title);
    if (m && workingDaysBetween(new Date(i.created_at), now) < QUARANTINE_WORKING_DAYS) active.add(m[1]);
  }
  return active;
}

// runs: booleans (true = passed), in order. Classifies one project's results.
export function classify(runs, { quarantined = false } = {}) {
  if (runs[0]) return 'pass';
  if (quarantined) return runs.slice(0, QUARANTINE_ATTEMPTS).some(Boolean) ? 'pass-quarantined' : 'fail';
  if (!runs[1]) return 'fail';
  const confirm = runs.slice(2);
  return confirm.some(Boolean) && confirm.some((r) => !r) ? 'flaky' : 'pass-on-retry';
}
