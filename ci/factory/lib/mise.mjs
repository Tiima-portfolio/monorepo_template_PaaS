// A tool is a version string or a table, for example
// rust: { version: "1.99.0", components: "rustfmt,clippy" }.
export function miseToml(tools) {
  const value = (v) => (v && typeof v === 'object'
    ? `{ ${Object.entries(v).map(([k, x]) => `${k} = ${JSON.stringify(String(x))}`).join(', ')} }`
    : JSON.stringify(String(v)));
  return `[tools]\n${Object.entries(tools).map(([k, v]) => `${JSON.stringify(k)} = ${value(v)}`).join('\n')}\n`;
}
