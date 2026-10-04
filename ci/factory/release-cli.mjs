#!/usr/bin/env node
// Release controller, run by .github/workflows/release.yml on every push to
// main. It walks main in history order from a cursor tag, so a run that is
// cancelled or starts late loses nothing: the next run picks up from the
// cursor. For each release it publishes the artifact first (a draft GitHub
// release with its files, and the image in the registry) and only then
// publishes the release, which creates the <service>/v<version> tag.
//
// Env: GITHUB_REPOSITORY, GH_TOKEN, FACTORY_REGISTRY (default
// ghcr.io/<owner>/<repo>), FACTORY_DRY_RUN=true to only print the plan.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { planReleases } from './release.mjs';

const CURSOR = 'factory/release-cursor';
const ARTIFACT = /\.(tgz|tar\.gz|whl|tar)$/;
const env = process.env;
const dry = env.FACTORY_DRY_RUN === 'true';
const repo = env.GITHUB_REPOSITORY || '';
const registry = env.FACTORY_REGISTRY || `ghcr.io/${repo.toLowerCase()}`;

const sh = (cmd, args, opts = {}) => (execFileSync(cmd, args, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, ...opts }) || '').trim();
const git = (...a) => sh('git', a);
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
const cursor = tryRun(() => git('rev-parse', '-q', '--verify', `refs/tags/${CURSOR}^{commit}`));
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
  return { sha, title: git('log', '-1', '--format=%s', sha), affected: affected.filter((p) => projects[p] && existed(p)) };
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
  git('checkout', '-q', r.sha);
  sh('npx', ['nx', 'run', `${r.service}:package`, '--skip-nx-cache'], { stdio: 'inherit', env: { ...env, FACTORY_VERSION: r.version } });
  const dist = path.join(root, 'dist');
  const files = fs.existsSync(dist) ? fs.readdirSync(dist).filter((f) => ARTIFACT.test(f)).map((f) => path.join(dist, f)) : [];
  // Artifact first: the image in the registry and the files on a draft release.
  for (const f of files.filter((x) => x.endsWith('-image.tar'))) {
    sh('skopeo', ['copy', '--dest-creds', `${env.GITHUB_ACTOR}:${env.GH_TOKEN}`, `oci-archive:${f}`, `docker://${registry}/${r.service}:${r.version}`], { stdio: 'inherit' });
  }
  const assets = files.filter((x) => !x.endsWith('-image.tar'));
  if (!existing) {
    sh('gh', ['release', 'create', r.tag, '--repo', repo, '--draft', '--target', r.sha, '--title', r.tag, '--notes', changelog(r.service, root, r.sha), ...assets], { stdio: 'inherit' });
  } else if (assets.length) {
    sh('gh', ['release', 'upload', r.tag, '--repo', repo, '--clobber', ...assets], { stdio: 'inherit' });
  }
  // Then the tag: publishing the draft creates <service>/v<version>.
  sh('gh', ['release', 'edit', r.tag, '--repo', repo, '--draft=false'], { stdio: 'inherit' });
  tags.push(r.tag);
  console.log(`Released ${r.tag}`);
}

try {
  for (const c of commits) {
    for (const r of plan.filter((x) => x.sha === c.sha)) publish(r);
    git('tag', '-f', CURSOR, c.sha);
    git('push', '-f', 'origin', `refs/tags/${CURSOR}`);
  }
  // Reconcile: a published tag whose release is still a draft gets published.
  for (const r of releases.filter((x) => x.isDraft && !plan.some((p) => p.tag === x.tagName))) {
    if (tryRun(() => git('rev-parse', '-q', '--verify', `refs/tags/${r.tagName}`))) {
      sh('gh', ['release', 'edit', r.tagName, '--repo', repo, '--draft=false'], { stdio: 'inherit' });
      console.log(`Reconciled ${r.tagName}`);
    } else {
      console.log(`::warning::Draft release ${r.tagName} has no tag yet; it will be published when its commit is released.`);
    }
  }
} finally {
  git('checkout', '-q', start);
}
