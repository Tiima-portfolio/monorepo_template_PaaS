// Promotion: when a service releases, every consumer that pins its version in
// a pins.yaml gets a bump PR, one per consumer, so each hop is its own PR.
import { parse } from './release.mjs';

const newer = (a, b) => {
  const [x, y] = [parse(a), parse(b)];
  return x[0] - y[0] || x[1] - y[1] || x[2] - y[2];
};

// pinsFiles: [{ path, pins: { service: version } }]
// released: [{ service, version }]
// holds: services whose promotion is on hold (an open escape).
export function planPromotions(pinsFiles, released, holds = []) {
  const latest = {};
  for (const r of released) {
    if (!latest[r.service] || newer(r.version, latest[r.service]) > 0) latest[r.service] = r.version;
  }
  const bumps = [];
  for (const file of pinsFiles) {
    for (const [service, pinned] of Object.entries(file.pins || {})) {
      const to = latest[service];
      if (!to || newer(to, String(pinned)) <= 0) continue;
      if (holds.includes(service)) continue;
      bumps.push({ path: file.path, service, from: String(pinned), to });
    }
  }
  return bumps;
}
