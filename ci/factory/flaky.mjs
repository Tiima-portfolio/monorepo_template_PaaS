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
// "quarantine: <project>:<test>" (or "<project>:test" for a whole project).
// Returns Map(project -> Set(tests)) still in quarantine; it also answers
// .has(project) like a set of projects.
export function activeQuarantine(issues, now = new Date()) {
  const active = new Map();
  for (const i of issues) {
    const m = /^quarantine: ([^:]+):(.+)$/.exec(i.title);
    if (!m || workingDaysBetween(new Date(i.created_at), now) >= QUARANTINE_WORKING_DAYS) continue;
    if (!active.has(m[1])) active.set(m[1], new Set());
    active.get(m[1]).add(m[2]);
  }
  return active;
}

// Per-test results from a project's test-results/ folder:
// Map(test id -> 'pass' | 'fail'). JUnit XML or Go's JSON test events.
export function parseJunit(xml) {
  const results = new Map();
  for (const m of xml.matchAll(/<testcase\b([^>]*?)(\/>|>([\s\S]*?)<\/testcase>)/g)) {
    const attr = (k) => new RegExp(`${k}="([^"]*)"`).exec(m[1])?.[1];
    const id = [attr('classname'), attr('name')].filter(Boolean).join('.');
    const failed = /<(failure|error)\b/.test(m[3] || '');
    if (/<skipped\b/.test(m[3] || '')) continue;
    results.set(id, failed || results.get(id) === 'fail' ? 'fail' : 'pass');
  }
  return results;
}

export function parseGoJson(text) {
  const results = new Map();
  for (const line of text.split('\n')) {
    try {
      const e = JSON.parse(line);
      if (e.Test && (e.Action === 'pass' || e.Action === 'fail')) results.set(`${e.Package}.${e.Test}`, e.Action);
    } catch {}
  }
  return results;
}

// runs: [Map(test -> status)] in order. Returns per-test verdicts for the
// tests that failed in the first run.
export function classifyTests(runs, quarantined = new Set()) {
  const verdicts = new Map();
  for (const [test, status] of runs[0]) {
    if (status !== 'fail') continue;
    const later = runs.slice(1).map((r) => r.get(test)).filter(Boolean);
    if (quarantined.has(test) || quarantined.has('test')) {
      verdicts.set(test, later.slice(0, QUARANTINE_ATTEMPTS - 1).includes('pass') ? 'pass-quarantined' : 'fail');
    } else if (later[0] !== 'pass') {
      verdicts.set(test, 'fail');
    } else {
      const confirm = later.slice(1);
      verdicts.set(test, confirm.includes('pass') && confirm.includes('fail') ? 'flaky' : 'pass-on-retry');
    }
  }
  return verdicts;
}

// runs: booleans (true = passed), in order. Classifies one project's results.
export function classify(runs, { quarantined = false } = {}) {
  if (runs[0]) return 'pass';
  if (quarantined) return runs.slice(0, QUARANTINE_ATTEMPTS).some(Boolean) ? 'pass-quarantined' : 'fail';
  if (!runs[1]) return 'fail';
  const confirm = runs.slice(2);
  return confirm.some(Boolean) && confirm.some((r) => !r) ? 'flaky' : 'pass-on-retry';
}
