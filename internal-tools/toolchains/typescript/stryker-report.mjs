// Converts Stryker's JSON report (mutation/stryker.json) into the factory's
// mutation/report.json: files[] with mutations[] of { line, end_line, status }.
import fs from 'node:fs';

const KILLED = new Set(['Killed', 'Timeout']);
const LIVED = new Set(['Survived', 'NoCoverage']);
const stryker = JSON.parse(fs.readFileSync('mutation/stryker.json', 'utf8'));
const files = Object.entries(stryker.files).map(([file, f]) => ({
  file_name: file,
  mutations: f.mutants
    .filter((m) => KILLED.has(m.status) || LIVED.has(m.status))
    .map((m) => ({ type: m.mutatorName, line: m.location.start.line, end_line: m.location.end.line, status: KILLED.has(m.status) ? 'KILLED' : 'LIVED' })),
}));
fs.writeFileSync('mutation/report.json', JSON.stringify({ tool: 'stryker', files }, null, 2));
