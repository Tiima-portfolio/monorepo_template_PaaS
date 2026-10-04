#!/usr/bin/env node
// Prints a mise config with the tools of every toolchain, for jobs that may
// build any service (the release job).
import fs from 'node:fs';
import path from 'node:path';
import YAML from 'yaml';
import { miseToml } from './lib/mise.mjs';

const dir = 'internal-tools/toolchains';
const tools = {};
for (const name of fs.readdirSync(dir)) {
  const file = path.join(dir, name, 'toolchain.yaml');
  if (fs.existsSync(file)) Object.assign(tools, YAML.parse(fs.readFileSync(file, 'utf8'))?.setup?.mise || {});
}
process.stdout.write(miseToml(tools));
