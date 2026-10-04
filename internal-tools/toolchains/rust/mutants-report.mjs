// Converts cargo-mutants' mutants.out/outcomes.json into the factory's
// mutation/report.json: files[] with mutations[] of { line, end_line, status }.
import fs from 'node:fs';

const KILLED = new Set(['CaughtMutant', 'Timeout']);
const LIVED = new Set(['MissedMutant']);
const outcomes = JSON.parse(fs.readFileSync('mutants.out/outcomes.json', 'utf8')).outcomes || [];
const files = {};
for (const o of outcomes) {
  const m = o.scenario?.Mutant;
  if (!m || !(KILLED.has(o.summary) || LIVED.has(o.summary))) continue;
  (files[m.file] ||= []).push({
    type: m.genre || m.replacement || 'mutant',
    line: m.span?.start?.line,
    end_line: m.span?.end?.line,
    status: KILLED.has(o.summary) ? 'KILLED' : 'LIVED',
  });
}
fs.mkdirSync('mutation', { recursive: true });
fs.writeFileSync('mutation/report.json', JSON.stringify({ tool: 'cargo-mutants', files: Object.entries(files).map(([file_name, mutations]) => ({ file_name, mutations })) }, null, 2));
