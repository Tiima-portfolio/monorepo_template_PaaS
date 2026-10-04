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
