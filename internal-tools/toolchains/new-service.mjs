#!/usr/bin/env node
// Creates a new project from a toolchain template.
//
//   node internal-tools/toolchains/new-service.mjs --name orders --lang go \
//     --owner team-orders [--kind product|internal-service|internal-tool] [--with container]
//
// The project gets the toolchain's template, a service.yaml and a
// guardrails.yaml with defaults its owner can tighten.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';

const here = path.dirname(fileURLToPath(import.meta.url));
const PLACES = {
  product: 'product/services',
  'internal-service': 'internal-services',
  'internal-tool': 'internal-tools',
};

export function createService({ name, lang, owner, kind = 'product', extra = [], root = process.cwd() }) {
  if (!/^[a-z][a-z0-9-]*$/.test(name || '')) throw new Error('--name must be lowercase letters, digits and dashes');
  if (!owner) throw new Error('--owner is required, for example team-orders');
  if (!PLACES[kind]) throw new Error(`--kind must be one of ${Object.keys(PLACES).join(', ')}`);
  const template = path.join(here, lang, 'template');
  if (!fs.existsSync(path.join(here, lang, 'toolchain.yaml'))) throw new Error(`unknown toolchain: ${lang}`);
  const dest = path.join(root, PLACES[kind], name);
  if (fs.existsSync(dest)) throw new Error(`${path.relative(root, dest)} already exists`);

  const vars = { __NAME__: name, __OWNER__: owner, __PKG__: name.replace(/-/g, '_') };
  const fill = (s) => s.replace(/__NAME__|__OWNER__|__PKG__/g, (k) => vars[k]);
  const copy = (from, to) => {
    for (const e of fs.readdirSync(from, { withFileTypes: true })) {
      const src = path.join(from, e.name);
      const dst = path.join(to, fill(e.name));
      if (e.isDirectory()) {
        fs.mkdirSync(dst, { recursive: true });
        copy(src, dst);
      } else {
        fs.writeFileSync(dst, fill(fs.readFileSync(src, 'utf8')));
      }
    }
  };
  fs.mkdirSync(dest, { recursive: true });
  if (fs.existsSync(template)) copy(template, dest);

  const toolchains = [lang, ...extra];
  fs.writeFileSync(path.join(dest, 'service.yaml'), [
    `name: ${name}`,
    `owner: ${owner}`,
    `toolchains: [${toolchains.join(', ')}]`,
    'criticality: normal',
    'consumes: []',
    'contract: []',
    '',
  ].join('\n'));
  if (!fs.existsSync(path.join(dest, 'guardrails.yaml'))) {
    fs.writeFileSync(path.join(dest, 'guardrails.yaml'), [
      `# Guardrails set by ${owner}. They can only be stricter than ci/policy/.`,
      'protected_paths: []',
      'required_checks: []',
      'thresholds: {}',
      'agents:',
      '  max_autonomous_tier: R1',
      '  forbidden_paths: []',
      'contributors: []',
      '',
    ].join('\n'));
  }
  return dest;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const { values } = parseArgs({
    options: {
      name: { type: 'string' },
      lang: { type: 'string' },
      owner: { type: 'string' },
      kind: { type: 'string', default: 'product' },
      with: { type: 'string', multiple: true, default: [] },
    },
  });
  try {
    const dest = createService({ ...values, extra: values.with });
    console.log(`Created ${path.relative(process.cwd(), dest)}`);
  } catch (e) {
    console.error(e.message);
    process.exit(1);
  }
}
