import test from 'node:test';
import assert from 'node:assert/strict';
import { miseToml } from '../lib/mise.mjs';

test('versions and tables', () => {
  const toml = miseToml({ go: '1.25', rust: { version: '1.99.0', components: 'rustfmt,clippy' } });
  assert.equal(toml, '[tools]\n"go" = "1.25"\n"rust" = { version = "1.99.0", components = "rustfmt,clippy" }\n');
});
