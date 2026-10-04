// Air-gap check: added lines in lock files, Dockerfiles and toolchain configs
// may only reference allowed package and image hosts.
import { matchesAny } from './lib/glob.mjs';

// added: Map(file -> [line text]).
export function networkProblems(added, policy) {
  const allowed = new Set(policy.allowed_hosts);
  const problems = [];
  for (const [file, lines] of added) {
    if (!matchesAny(file, policy.checked_files)) continue;
    for (const text of lines) {
      const hosts = [...text.matchAll(/https?:\/\/([a-z0-9.-]+)/gi)].map((m) => m[1].toLowerCase());
      // FROM image without a registry host comes from docker.io.
      const from = /^\s*FROM\s+(\S+)/i.exec(text)?.[1];
      if (from && from !== 'scratch' && !from.startsWith('$')) {
        const first = from.split('/')[0];
        hosts.push(from.includes('/') && /[.:]/.test(first) ? first : 'docker.io');
      }
      for (const h of hosts) if (!allowed.has(h)) problems.push(`${file} uses ${h}, which isn't an allowed host in ci/policy/network.yaml`);
    }
  }
  return [...new Set(problems)];
}
