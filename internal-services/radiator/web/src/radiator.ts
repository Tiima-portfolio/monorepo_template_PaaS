// The radiator's view: turns /api/radiator data into HTML. No DOM access here,
// so it runs under node --test as well as in the browser.

export type Status = 'passing' | 'failing' | 'running';

export interface Service {
  name: string;
  owner: string;
  status: Status;
  build_minutes: number;
  coverage: number;
}

export interface Queue {
  depth: number;
  oldest_minutes: number;
  by_priority: Record<string, number>;
}

export interface Release {
  service: string;
  version: string;
  released_at: string;
}

export interface Radiator {
  generated_at: string;
  services: Service[];
  queue: Queue;
  releases: Release[];
}

const ESCAPES: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

export function escape(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ESCAPES[c] ?? c);
}

// The whole wall goes red when any build fails, so it is seen across the room.
export function overall(services: Service[]): Status {
  if (services.some((s) => s.status === 'failing')) return 'failing';
  if (services.some((s) => s.status === 'running')) return 'running';
  return 'passing';
}

export function percent(fraction: number): string {
  return `${Math.round(fraction * 100)}%`;
}

// "5 min ago", "3 h ago": release ages at a glance.
export function age(at: string, now: Date): string {
  const minutes = Math.max(0, Math.round((now.getTime() - new Date(at).getTime()) / 60_000));
  return minutes < 60 ? `${minutes} min ago` : `${Math.round(minutes / 60)} h ago`;
}

function serviceTile(s: Service): string {
  return `<li class="tile ${s.status}">
  <span class="name">${escape(s.name)}</span>
  <span class="owner">${escape(s.owner)}</span>
  <span class="facts">${escape(s.status)} · ${s.build_minutes} min · coverage ${percent(s.coverage)}</span>
</li>`;
}

function queueTile(q: Queue): string {
  const lanes = Object.entries(q.by_priority)
    .map(([p, n]) => `<span class="lane">${escape(p)} ${n}</span>`)
    .join('');
  return `<section class="queue">
  <h2>Merge queue</h2>
  <p class="depth">${q.depth}</p>
  <p class="oldest">${q.depth ? `oldest ${q.oldest_minutes} min` : 'empty'}</p>
  <p class="lanes">${lanes}</p>
</section>`;
}

function releaseList(releases: Release[], now: Date): string {
  const items = releases
    .map((r) => `<li>${escape(r.service)} <b>${escape(r.version)}</b> <span>${age(r.released_at, now)}</span></li>`)
    .join('');
  return `<section class="releases">
  <h2>Recent releases</h2>
  <ul>${items}</ul>
</section>`;
}

export function render(data: Radiator, now: Date): string {
  return `<header class="${overall(data.services)}"><h1>Factory radiator</h1></header>
<ul class="services">${data.services.map(serviceTile).join('')}</ul>
${queueTile(data.queue)}
${releaseList(data.releases, now)}`;
}
