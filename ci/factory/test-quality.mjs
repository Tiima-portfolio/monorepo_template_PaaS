// Test quality lint: tests that can't fail, or that don't run.
// A heuristic per language, applied to the test files a PR changes.

const LANGS = [
  { match: /\.(test|spec)\.[cm]?[jt]sx?$/, start: /^\s*(?:test|it)(\.\w+)?\(\s*['"`](.+?)['"`]/m, assert: /\bassert\b|\bexpect\(|\.throws\(|\.rejects\(/, skip: /^\s*(?:test|it|describe)\.(?:skip|todo)\(|\{\s*skip:\s*true/m },
  { match: /_test\.go$/, start: /^func (Test\w+)\(/m, assert: /\bt\.(Error|Errorf|Fatal|Fatalf|Fail|FailNow)\b|\bassert\.|\brequire\./, skip: /\bt\.Skip(?:f|Now)?\(/ },
  { match: /(^|\/)test_[^/]*\.py$|_test\.py$/, start: /^\s*def (test_\w+)\(/m, assert: /\bassert\b|pytest\.raises|self\.assert/, skip: /@pytest\.mark\.skip|pytest\.skip\(/ },
  { match: /\.rs$/, start: /#\[test\]\s*(?:#\[[^\]]+\]\s*)*fn (\w+)/m, assert: /\bassert(_eq|_ne)?!|panic!|\.unwrap_err\(\)|should_panic/, skip: /#\[ignore\]/ },
];

// Splits text into test blocks: from one test's start to the next one's.
function blocks(text, start) {
  const re = new RegExp(start.source, 'gm');
  const starts = [...text.matchAll(re)].map((m) => ({ index: m.index, name: m[2] || m[1] }));
  return starts.map((s, i) => ({ name: s.name, body: text.slice(s.index, starts[i + 1]?.index ?? text.length) }));
}

// Returns problems for one file, or [] when it isn't a test file it knows.
export function lintTestFile(file, text) {
  const lang = LANGS.find((l) => l.match.test(file));
  if (!lang) return [];
  const problems = [];
  for (const b of blocks(text, lang.start)) {
    if (lang.skip.test(b.body.split('\n')[0]) || (lang === LANGS[1] && lang.skip.test(b.body))) {
      problems.push(`${file}: "${b.name}" is skipped`);
    } else if (!lang.assert.test(b.body)) {
      problems.push(`${file}: "${b.name}" has no assertion, so it can't fail`);
    }
  }
  if (lang.skip.test(text) && !problems.some((p) => p.includes('skipped'))) problems.push(`${file}: skips tests`);
  return problems;
}
