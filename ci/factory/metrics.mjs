#!/usr/bin/env node
// Merges new coverage totals into main's metrics file.
//   metrics.mjs <metrics.json> <coverage-totals.json> <sha>
import fs from 'node:fs';

const [file, totalsFile, sha] = process.argv.slice(2);
const metrics = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : {};
const totals = fs.existsSync(totalsFile) ? JSON.parse(fs.readFileSync(totalsFile, 'utf8')) : {};
const at = new Date().toISOString();
for (const [name, coverage] of Object.entries(totals)) metrics[name] = { coverage, sha, at };
fs.writeFileSync(file, JSON.stringify(metrics, null, 2));
console.log(`metrics: ${Object.keys(totals).length} project(s) updated`);
