#!/usr/bin/env node
// Release controller, run by .github/workflows/release.yml on every push to
// main. It walks main in history order from a cursor, so a run that is
// cancelled or starts late loses nothing: the next run picks up from the
// cursor. The cursor lives in the body of a draft release, not in a git ref:
// GitHub won't let GITHUB_TOKEN point a ref at an older commit once workflow
// files have changed since. For each release it publishes the artifact first (a draft GitHub
// release with its files, and the image in the registry) and only then
// publishes the release, which creates the <service>/v<version> tag.
//
// Env: GITHUB_REPOSITORY, GH_TOKEN, FACTORY_REGISTRY (default
// ghcr.io/<owner>/<repo>), FACTORY_DRY_RUN=true to only print the plan.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { planReleases } from './release.mjs';

const CURSOR = 'factory-release-cursor';
const LEGACY_CURSOR_TAG = 'factory/release-cursor';
const ARTIFACT = /\.(tgz|tar\.gz|whl|tar)$/;
const env = process.env;
const dry = env.FACTORY_DRY_RUN === 'true';
const repo = env.GITHUB_REPOSITORY || '';
const registry = env.FACTORY_REGISTRY || `ghcr.io/${repo.toLowerCase()}`;

const sh = (cmd, args, opts = {}) => (execFileSync(cmd, args, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, ...opts }) || '').trim();
const git = (...a) => sh('git', a);
// gh with stderr captured (and echoed), so a refusal can be recognised.
const gh = (args) => {
  try {
    return sh('gh', args, { stdio: ['ignore', 'inherit', 'pipe'] });
  } catch (e) {
    if (e.stderr) process.stderr.write(e.stderr);
    throw e;
  }
};
const tryRun = (fn) => { try { return fn(); } catch { return null; } };
const lines = (s) => (s ? s.split('\n').filter(Boolean) : []);

function releasableProjects() {
  sh('npx', ['nx', 'graph', '--file=.release-graph.json'], { stdio: 'ignore' });
  const nodes = JSON.parse(fs.readFileSync('.release-graph.json', 'utf8')).graph.nodes;
  fs.rmSync('.release-graph.json');
  const out = {};
  for (const [name, n] of Object.entries(nodes)) {
    const tags = n.data.tags || [];
    const shipped = tags.includes('boundary:product') || tags.includes('boundary:internal-services');
    if (shipped && n.data.targets?.package) out[name] = n.data.root;
  }
  return out;
}

const start = git('rev-parse', 'HEAD');
// Cursor state: { sha, pending: [release] } in the draft release's body.
function readCursor() {
  const rel = dry ? null : tryRun(() => JSON.parse(sh('gh', ['api', `repos/${repo}/releases`, '--paginate', '--jq', `[.[] | select(.tag_name == "${CURSOR}")] | first`]) || 'null'));
  if (rel?.body) return { id: rel.id, ...JSON.parse(rel.body) };
  const legacy = tryRun(() => git('rev-parse', '-q', '--verify', `refs/tags/${LEGACY_CURSOR_TAG}^{commit}`));
  return { id: rel?.id || null, sha: legacy || null, pending: [] };
}
function writeCursor(state) {
  const body = JSON.stringify({ sha: state.sha, pending: state.pending });
  if (state.id) {
    sh('gh', ['api', '-X', 'PATCH', `repos/${repo}/releases/${state.id}`, '-f', `body=${body}`], { stdio: 'ignore' });
  } else {
    const created = JSON.parse(sh('gh', ['api', `repos/${repo}/releases`, '-f', `tag_name=${CURSOR}`, '-f', `name=${CURSOR}`, '-F', 'draft=true', '-f', `body=${body}`]));
    state.id = created.id;
  }
}
const cursorState = readCursor();
const cursor = cursorState.sha;
const shas = cursor ? lines(git('rev-list', '--reverse', '--first-parent', `${cursor}..HEAD`)) : [start];
console.log(cursor ? `Cursor at ${cursor.slice(0, 12)}; ${shas.length} new commit(s) on main.` : 'No cursor yet; starting from HEAD.');

const projects = releasableProjects();
const commits = shas.map((sha) => {
  const parent = tryRun(() => git('rev-parse', `${sha}^`));
  const affected = parent
    ? JSON.parse(sh('npx', ['nx', 'show', 'projects', '--affected', `--base=${parent}`, `--head=${sha}`, '--json']))
    : Object.keys(projects);
  // The graph is today's; keep only projects that already existed at this commit.
  const existed = (p) => tryRun(() => sh('git', ['cat-file', '-e', `${sha}:${projects[p]}/service.yaml`], { stdio: ['ignore', 'pipe', 'ignore'] })) !== null;
  const files = parent ? lines(git('diff', '--name-only', parent, sha)) : [];
  // A rerun after a partial failure skips services already released from this commit.
  const done = new Set(lines(git('tag', '--points-at', sha, '*/v*')).map((t) => t.split('/v')[0]));
  const kept = affected.filter((p) => projects[p] && existed(p) && !done.has(p));
  const changed = parent ? kept.filter((p) => files.some((f) => f.startsWith(`${projects[p]}/`))) : kept;
  return { sha, title: git('log', '-1', '--format=%s', sha), affected: kept, changed };
});
const tags = lines(git('tag', '-l', '*/v*'));
const plan = planReleases(commits, tags);
console.log(plan.length ? plan.map((r) => `- ${r.tag} from ${r.sha.slice(0, 12)} (${r.bump})`).join('\n') : 'Nothing to release.');
if (dry) process.exit(0);

const releases = JSON.parse(sh('gh', ['release', 'list', '--repo', repo, '--limit', '1000', '--json', 'tagName,isDraft']) || '[]');
const state = (tag) => releases.find((r) => r.tagName === tag);

function changelog(service, root, sha) {
  const prev = tags.filter((t) => t.startsWith(`${service}/v`)).at(-1);
  const range = prev ? `${prev}..${sha}` : sha;
  return lines(git('log', '--format=- %s (%h)', range, '--', root)).join('\n') || '- First release';
}

function publish(r) {
  const existing = state(r.tag);
  if (existing && !existing.isDraft) {
    console.log(`${r.tag} already published`);
    return;
  }
  const root = projects[r.service];
  // Packaging stamps versions into tracked files; start each release clean.
  git('reset', '-q', '--hard');
  git('checkout', '-q', r.sha);
  sh('npx', ['nx', 'run', `${r.service}:package`, '--skip-nx-cache'], { stdio: 'inherit', env: { ...env, FACTORY_VERSION: r.version } });
  const dist = path.join(root, 'dist');
  const files = fs.existsSync(dist) ? fs.readdirSync(dist).filter((f) => ARTIFACT.test(f)).map((f) => path.join(dist, f)) : [];
  // Artifact first: the image in the registry and the files on a draft release.
  for (const f of files.filter((x) => x.endsWith('-image.tar'))) {
    // An OCI layout has an oci-layout file; otherwise it's a docker save archive.
    const format = sh('tar', ['-tf', f]).split('\n').includes('oci-layout') ? 'oci-archive' : 'docker-archive';
    sh('skopeo', ['copy', '--dest-creds', `${env.GITHUB_ACTOR}:${env.GH_TOKEN}`, `${format}:${f}`, `docker://${registry}/${r.service}:${r.version}`], { stdio: 'inherit' });
  }
  const assets = files.filter((x) => !x.endsWith('-image.tar'));
  if (!existing) {
    gh(['release', 'create', r.tag, '--repo', repo, '--draft', '--target', r.sha, '--title', r.tag, '--notes', changelog(r.service, root, r.sha), ...assets]);
  } else if (assets.length) {
    gh(['release', 'upload', r.tag, '--repo', repo, '--clobber', ...assets]);
  }
  // Then the tag: publishing the draft creates <service>/v<version>.
  gh(['release', 'edit', r.tag, '--repo', repo, '--draft=false']);
  tags.push(r.tag);
  console.log(`Released ${r.tag}`);
}

// GitHub refuses a release on an older commit when the workflow files have
// changed since, unless the token may write workflows (GITHUB_TOKEN can't).
// Without FACTORY_RELEASE_TOKEN such a release is skipped with a warning
// instead of blocking every later release.
const refused = [];
function tryPublish(r) {
  try {
    publish(r);
  } catch (e) {
    const text = `${e.message}\n${e.stderr || ''}`;
    if (!/Resource not accessible by integration|refusing to allow/.test(text)) throw e;
    refused.push(r);
    console.log(`::warning::GitHub refused to create ${r.tag} with this token. Set the FACTORY_RELEASE_TOKEN secret (a GitHub App token with contents and workflows write) and re-run to release it.`);
  }
}

try {
  // Releases refused earlier are retried first, in case a token is now set.
  const retry = cursorState.pending || [];
  cursorState.pending = [];
  for (const r of retry) {
    if (!state(r.tag) || state(r.tag).isDraft) tryPublish(r);
  }
  for (const c of commits) {
    for (const r of plan.filter((x) => x.sha === c.sha)) tryPublish(r);
    cursorState.sha = c.sha;
    cursorState.pending = refused;
    writeCursor(cursorState);
  }
  if (!commits.length && retry.length) {
    cursorState.pending = refused;
    writeCursor(cursorState);
  }
  // Reconcile: a published tag whose release is still a draft gets published.
  for (const r of releases.filter((x) => x.isDraft && !plan.some((p) => p.tag === x.tagName))) {
    if (tryRun(() => git('rev-parse', '-q', '--verify', `refs/tags/${r.tagName}`))) {
      gh(['release', 'edit', r.tagName, '--repo', repo, '--draft=false']);
      console.log(`Reconciled ${r.tagName}`);
    } else {
      console.log(`::warning::Draft release ${r.tagName} has no tag yet; it will be published when its commit is released.`);
    }
  }
  if (refused.length) console.log(`Waiting for FACTORY_RELEASE_TOKEN: ${refused.map((r) => r.tag).join(', ')}`);
} finally {
  git('reset', '-q', '--hard');
  git('checkout', '-q', start);
}
