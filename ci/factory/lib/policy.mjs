import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import YAML from 'yaml';

const here = path.dirname(fileURLToPath(import.meta.url));
export const POLICY_DIR = process.env.FACTORY_POLICY_DIR || path.resolve(here, '../../policy');

export function loadPolicy(name, dir = POLICY_DIR) {
  return YAML.parse(fs.readFileSync(path.join(dir, `${name}.yaml`), 'utf8'));
}
