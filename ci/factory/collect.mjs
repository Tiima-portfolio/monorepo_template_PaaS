// Evidence collector checks: links a PR's evidence bundle to the commit that
// landed on main.
import crypto from 'node:crypto';

export const digest = (record) => {
  const { digest: _ignored, ...rest } = record;
  return crypto.createHash('sha256').update(JSON.stringify(rest)).digest('hex');
};

// bundle: the PR's last admitted bundle. main: { sha, tree }. prHead: PR head sha.
export function linkToMain(bundle, main, prHead) {
  const problems = [];
  if (!bundle) return { ok: false, treeMatch: false, problems: ['no evidence bundle found for the PR'] };
  if (bundle.sha !== prHead) problems.push(`bundle is for ${bundle.sha?.slice(0, 12)}, PR head is ${prHead.slice(0, 12)}`);
  if (!bundle.decision?.allowed) problems.push('the bundle records a blocked decision');
  if (bundle.run?.path && !bundle.run.path.startsWith('.github/workflows/factory.yml')) problems.push(`bundle came from ${bundle.run.path}`);
  for (const r of bundle.records || []) {
    if (r.digest && r.digest !== digest(r)) problems.push(`record ${r.check} was altered`);
  }
  // Without a merge queue the squash commit can differ from what was verified,
  // if main moved on. Only an exact tree match carries the evidence over.
  const treeMatch = !!bundle.tree && bundle.tree === main.tree;
  return { ok: problems.length === 0, treeMatch, problems };
}

export function sign(body, key) {
  return crypto.createHmac('sha256', key).update(JSON.stringify(body)).digest('hex');
}

const lit = (v) => (v === null || v === undefined ? 'NULL' : typeof v === 'boolean' || typeof v === 'number' ? String(v) : `'${String(v).replace(/'/g, "''")}'`);

// SQL for the evidence index (platform/evidence/schema.sql): a row per check
// in the PR's bundle and one for the decision.
export function indexSql(body, repo, bundleUri) {
  const rows = [];
  const b = body.pr_bundle;
  for (const r of b?.records || []) rows.push([r.check, r.status, r.details]);
  rows.push(['admission', b?.decision?.allowed ? 'allowed' : 'blocked', (b?.decision?.blocking || []).join(', ') || body.problems.join('; ')]);
  const values = rows.map(([check, status, details]) => `(${[repo, body.main.sha, body.pr, body.pr_head, check, status, details, b?.tier ?? null, body.tree_match, bundleUri].map(lit).join(', ')})`);
  return `INSERT INTO evidence (repo, main_sha, pr, pr_head, check_name, status, details, tier, tree_match, bundle_uri) VALUES\n${values.join(',\n')}\nON CONFLICT (repo, main_sha, check_name) DO NOTHING;\n`;
}
