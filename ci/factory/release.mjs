// Release planning: versions come from git tags, bumps from squash commit
// titles, and releases happen in main's history order.
import { checkTitle } from './checks.mjs';

const SEMVER = /^(\d+)\.(\d+)\.(\d+)$/;

export function parse(v) {
  const m = SEMVER.exec(v || '');
  if (!m) throw new Error(`not a version: ${v}`);
  return m.slice(1).map(Number);
}

// Highest version among tags like "orders/v1.2.3" for one service.
export function latestVersion(service, tags) {
  const prefix = `${service}/v`;
  const versions = tags.filter((t) => t.startsWith(prefix)).map((t) => t.slice(prefix.length)).filter((v) => SEMVER.test(v));
  if (!versions.length) return null;
  return versions.sort((a, b) => {
    const [x, y] = [parse(a), parse(b)];
    return x[0] - y[0] || x[1] - y[1] || x[2] - y[2];
  }).at(-1);
}

// New services start at 0.1.0. Below 1.0 a breaking change is a minor bump.
export function nextVersion(current, bump) {
  if (bump === 'none') return null;
  if (!current) return '0.1.0';
  let [major, minor, patch] = parse(current);
  if (bump === 'major' && major === 0) bump = 'minor';
  if (bump === 'major') return `${major + 1}.0.0`;
  if (bump === 'minor') return `${major}.${minor + 1}.0`;
  return `${major}.${minor}.${patch + 1}`;
}

// commits: [{ sha, title, affected: [service], changed: [service] }] in history
// order (oldest first). A service the commit changed gets the bump from the
// title; one affected only through a dependency is rebuilt as a patch.
// Returns the releases to make, in the same order.
export function planReleases(commits, tags) {
  const known = [...tags];
  const releases = [];
  for (const c of commits) {
    const title = checkTitle(c.title);
    const titleBump = title.ok ? title.bump : 'none';
    const changed = new Set(c.changed || c.affected);
    for (const service of [...c.affected].sort()) {
      const bump = changed.has(service) ? titleBump : titleBump === 'none' ? 'none' : 'patch';
      const version = nextVersion(latestVersion(service, known), bump);
      if (!version) continue;
      const tag = `${service}/v${version}`;
      known.push(tag);
      releases.push({ sha: c.sha, service, version, tag, bump });
    }
  }
  return releases;
}
