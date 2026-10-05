// Runs docker buildx build with the factory's builder: the shared BuildKit
// service (internal-services/buildkit) when FACTORY_BUILDKIT_ADDR is set and
// answers, the runner's local BuildKit otherwise. Unset, nothing changes.
//
//   node buildx.mjs <service name> <docker buildx build arguments...>
//
// FACTORY_BUILDKIT_ADDR         the service, e.g. tcp://buildkit.buildkit-pr.svc:1234
// FACTORY_BUILDKIT_TLS_DIR      folder with the client's ca.crt, tls.crt and tls.key
// FACTORY_BUILDKIT_CACHE_REF    registry repository for the layer cache, one tag per service
// FACTORY_BUILDKIT_CACHE_WRITE  "true" on main runners only: also write the cache
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

export const BUILDER = 'factory-buildkit';

// `docker buildx create` arguments for the service's remote builder.
export function createArgs(env) {
  const args = ['buildx', 'create', '--name', BUILDER, '--driver', 'remote'];
  const dir = env.FACTORY_BUILDKIT_TLS_DIR;
  if (dir) {
    for (const [opt, file] of [['cacert', 'ca.crt'], ['cert', 'tls.crt'], ['key', 'tls.key']]) {
      args.push('--driver-opt', `${opt}=${dir}/${file}`);
    }
  }
  return [...args, env.FACTORY_BUILDKIT_ADDR];
}

// `docker buildx build` arguments. remote: the service answered. The layer
// cache is only used through the service: the local docker driver can't
// export it.
export function buildArgs(env, name, rest, remote) {
  if (!remote) return ['buildx', 'build', ...rest];
  const args = ['buildx', 'build', '--builder', BUILDER];
  const ref = env.FACTORY_BUILDKIT_CACHE_REF;
  if (ref) {
    args.push('--cache-from', `type=registry,ref=${ref}:${name}`);
    if (env.FACTORY_BUILDKIT_CACHE_WRITE === 'true') args.push('--cache-to', `type=registry,ref=${ref}:${name},mode=max`);
  }
  return [...args, ...rest];
}

const docker = (args, opts = {}) => spawnSync('docker', args, { encoding: 'utf8', ...opts });

// Creates the remote builder if needed and checks the service answers.
function serviceReady(env) {
  const addr = env.FACTORY_BUILDKIT_ADDR;
  if (!addr) return false;
  const current = docker(['buildx', 'inspect', BUILDER]);
  if (current.status !== 0 || !current.stdout.includes(addr)) {
    if (current.status === 0) docker(['buildx', 'rm', BUILDER]);
    // A parallel target may create it first; the check below decides.
    docker(createArgs(env));
  }
  if (docker(['buildx', 'inspect', '--bootstrap', BUILDER], { timeout: 30_000 }).status === 0) return true;
  console.warn(`::warning::The BuildKit service at ${addr} did not answer; building with the local BuildKit.`);
  return false;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [name, ...rest] = process.argv.slice(2);
  const run = spawnSync('docker', buildArgs(process.env, name, rest, serviceReady(process.env)), { stdio: 'inherit' });
  process.exit(run.status ?? 1);
}
