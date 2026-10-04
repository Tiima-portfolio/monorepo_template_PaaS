// Diff coverage: the share of changed executable lines that unit tests run.

// lcov text -> Map(file -> Map(line -> hits)), file relative to the project.
export function parseLcov(text) {
  const files = new Map();
  let current = null;
  for (const raw of text.split('\n')) {
    const line = raw.trim();
    if (line.startsWith('SF:')) {
      current = new Map();
      files.set(line.slice(3), current);
    } else if (line.startsWith('DA:') && current) {
      const [n, hits] = line.slice(3).split(',').map(Number);
      current.set(n, Math.max(current.get(n) || 0, hits));
    } else if (line === 'end_of_record') {
      current = null;
    }
  }
  return files;
}

// Go cover profile -> same shape. Paths are "<module>/<file>".
export function parseGoCover(text, module) {
  const files = new Map();
  for (const line of text.split('\n').slice(1)) {
    const m = /^(.+):(\d+)\.\d+,(\d+)\.\d+ \d+ (\d+)$/.exec(line.trim());
    if (!m) continue;
    const file = m[1].startsWith(`${module}/`) ? m[1].slice(module.length + 1) : m[1];
    if (!files.has(file)) files.set(file, new Map());
    const lines = files.get(file);
    for (let n = Number(m[2]); n <= Number(m[3]); n++) lines.set(n, Math.max(lines.get(n) || 0, Number(m[4])));
  }
  return files;
}

// `git diff -U0` text -> Map(file -> Set(added line numbers)), paths as in the diff.
export function addedLines(diff) {
  const files = new Map();
  let file = null;
  for (const line of diff.split('\n')) {
    if (line.startsWith('+++ ')) {
      file = line.startsWith('+++ b/') ? line.slice(6) : null;
      if (file) files.set(file, new Set());
    } else if (file && line.startsWith('@@')) {
      const m = /\+(\d+)(?:,(\d+))?/.exec(line);
      const start = Number(m[1]);
      const count = m[2] === undefined ? 1 : Number(m[2]);
      for (let n = start; n < start + count; n++) files.get(file).add(n);
    }
  }
  return files;
}

// added: Map(project-relative file -> Set(lines)); coverage: from a parser.
// Lines the coverage tool doesn't list aren't executable and don't count.
export function diffCoverage(added, coverage) {
  let covered = 0;
  let total = 0;
  const uncovered = [];
  for (const [file, lines] of added) {
    const hits = coverage.get(file);
    if (!hits) continue;
    for (const n of lines) {
      if (!hits.has(n)) continue;
      total++;
      if (hits.get(n) > 0) covered++;
      else uncovered.push(`${file}:${n}`);
    }
  }
  return { covered, total, pct: total ? Math.round((covered / total) * 1000) / 10 : null, uncovered };
}

// Line coverage of a whole project, in percent, from a parser's output.
export function totalCoverage(coverage) {
  let covered = 0;
  let total = 0;
  for (const lines of coverage.values()) {
    for (const hits of lines.values()) {
      total++;
      if (hits > 0) covered++;
    }
  }
  return total ? Math.round((covered / total) * 1000) / 10 : null;
}

// The ratchet: a project's coverage may not drop more than `tolerance` points
// below the last value recorded on main. Projects without a record pass.
export function ratchet(totals, previous, tolerance = 0.5) {
  const drops = [];
  for (const [name, pct] of Object.entries(totals)) {
    const before = previous[name]?.coverage;
    if (typeof before === 'number' && pct < before - tolerance) drops.push({ name, before, now: pct });
  }
  return drops;
}

// Mutation score on changed lines from a mutation/report.json (files[] with
// mutations[] of { line, end_line?, status }). A mutant counts when any line it
// spans changed. Only KILLED and LIVED mutants count.
export function diffMutation(added, report) {
  let killed = 0;
  let lived = 0;
  const survivors = [];
  for (const f of report.files || []) {
    const lines = added.get(f.file_name);
    if (!lines) continue;
    for (const m of f.mutations || []) {
      let hit = false;
      for (let n = m.line; n <= (m.end_line || m.line); n++) if (lines.has(n)) hit = true;
      if (!hit) continue;
      if (m.status === 'KILLED') killed++;
      else if (m.status === 'LIVED') { lived++; survivors.push(`${f.file_name}:${m.line} ${m.type || ''}`.trim()); }
    }
  }
  const total = killed + lived;
  return { killed, lived, total, pct: total ? Math.round((killed / total) * 1000) / 10 : null, survivors };
}
