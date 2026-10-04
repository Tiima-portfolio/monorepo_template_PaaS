#!/usr/bin/env node
// Writes one evidence record for a verify step.
// Usage: verify-record.mjs <check> <exit-code> [details]
import fs from 'node:fs';
import path from 'node:path';

const [check, code, details = ''] = process.argv.slice(2);
const out = path.join(process.env.FACTORY_OUT || 'factory-out', 'evidence');
fs.mkdirSync(out, { recursive: true });
const affected = Number(process.env.FACTORY_AFFECTED || '0');
const status = affected === 0 ? 'skipped' : code === '0' ? 'pass' : 'fail';
const rec = { check, status, sha: process.env.FACTORY_SHA, details: affected === 0 ? 'nothing affected' : details };
fs.writeFileSync(path.join(out, `${check}.json`), JSON.stringify(rec, null, 2));
console.log(`${check}: ${status}`);
