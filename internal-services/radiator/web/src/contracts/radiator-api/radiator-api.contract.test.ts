// Consumer contract test: every field the radiator reads is in radiator-api's
// published schema (a copy of its openapi.json, refreshed when the API changes).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const spec = JSON.parse(fs.readFileSync(new URL('./openapi.json', import.meta.url), 'utf8'));
const schemas = spec.components.schemas;
const READS: Record<string, string[]> = {
  Radiator: ['generated_at', 'services', 'queue', 'releases'],
  Service: ['name', 'owner', 'status', 'build_minutes', 'coverage'],
  Queue: ['depth', 'oldest_minutes', 'by_priority'],
  Release: ['service', 'version', 'released_at'],
};

test('GET /api/radiator returns a Radiator', () => {
  const ok = spec.paths['/api/radiator'].get.responses['200'];
  assert.equal(ok.content['application/json'].schema.$ref, '#/components/schemas/Radiator');
});

for (const [name, fields] of Object.entries(READS)) {
  test(`${name} has every field the radiator reads, all required`, () => {
    const schema = schemas[name];
    assert.ok(schema, `${name} is missing`);
    for (const f of fields) assert.ok(schema.properties[f], `${name}.${f} is missing`);
    assert.deepEqual([...schema.required].sort(), [...fields].sort());
  });
}

test('service status is one of the three the radiator colours', () => {
  assert.deepEqual([...schemas.Service.properties.status.enum].sort(), ['failing', 'passing', 'running']);
});
