import test from 'node:test';
import assert from 'node:assert/strict';
import { lintTestFile } from '../test-quality.mjs';

test('typescript', () => {
  assert.deepEqual(lintTestFile('a.test.ts', "test('ok', () => { assert.equal(1, 1); });\n"), []);
  assert.match(lintTestFile('a.test.ts', "test('empty', () => { run(); });\n")[0], /no assertion/);
  assert.match(lintTestFile('a.test.ts', "test.skip('later', () => { assert.ok(1); });\n")[0], /skipped/);
});

test('go', () => {
  assert.deepEqual(lintTestFile('a_test.go', 'func TestA(t *testing.T) {\n\tif x { t.Fatalf("x") }\n}\n'), []);
  assert.match(lintTestFile('a_test.go', 'func TestB(t *testing.T) {\n\tdo()\n}\n')[0], /no assertion/);
  assert.match(lintTestFile('a_test.go', 'func TestC(t *testing.T) {\n\tt.Skip("x")\n}\n')[0], /skipped/);
});

test('python', () => {
  assert.deepEqual(lintTestFile('tests/test_a.py', 'def test_a():\n    assert f() == 1\n'), []);
  assert.match(lintTestFile('tests/test_a.py', 'def test_b():\n    f()\n')[0], /no assertion/);
  assert.match(lintTestFile('tests/test_a.py', '@pytest.mark.skip\ndef test_c():\n    assert 1\n').join(), /skip/);
});

test('rust', () => {
  assert.deepEqual(lintTestFile('src/main.rs', '#[test]\nfn a() { assert_eq!(1, 1); }\n'), []);
  assert.match(lintTestFile('src/main.rs', '#[test]\nfn b() { run(); }\n')[0], /no assertion/);
});

test('other files are ignored', () => {
  assert.deepEqual(lintTestFile('src/a.ts', "test('x', () => {})"), []);
});

test('the example services pass', async () => {
  const fs = await import('node:fs');
  for (const f of ['product/services/catalog/src/products.test.ts', 'product/services/orders/main_test.go', 'product/services/pricing/tests/test_greeting.py', 'product/services/inventory/src/main.rs']) {
    assert.deepEqual(lintTestFile(f, fs.readFileSync(new URL(`../../../${f}`, import.meta.url), 'utf8')), [], f);
  }
});
