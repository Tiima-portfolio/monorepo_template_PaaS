// Browser entry: polls the API and redraws the radiator. The ingress sends
// /api to radiator-api, so the page and the API share one origin.
import { render, type Radiator } from './radiator.ts';

const REFRESH_MS = 15_000;

async function refresh(app: HTMLElement): Promise<void> {
  try {
    const response = await fetch('/api/radiator');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    app.innerHTML = render((await response.json()) as Radiator, new Date());
  } catch (error) {
    app.querySelector('header')?.classList.add('stale');
    console.error('radiator refresh failed', error);
  }
}

const app = document.getElementById('app');
if (app) {
  void refresh(app);
  setInterval(() => void refresh(app), REFRESH_MS);
}
