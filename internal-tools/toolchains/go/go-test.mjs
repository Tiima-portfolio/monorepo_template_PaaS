// Runs go test with coverage and a JSON event stream: prints the test output
// as usual and keeps the events in test-results/go-test.json, so the factory
// can tell which test failed.
import fs from 'node:fs';
import { spawn } from 'node:child_process';

fs.mkdirSync('coverage', { recursive: true });
fs.mkdirSync('test-results', { recursive: true });
const out = fs.createWriteStream('test-results/go-test.json');
const child = spawn('go', ['test', '-json', '-coverprofile=coverage/cover.out', './...'], { stdio: ['ignore', 'pipe', 'inherit'] });
let rest = '';
child.stdout.on('data', (chunk) => {
  out.write(chunk);
  const lines = (rest + chunk).split('\n');
  rest = lines.pop();
  for (const line of lines) {
    try {
      const e = JSON.parse(line);
      if (e.Action === 'output') process.stdout.write(e.Output);
    } catch {
      process.stdout.write(`${line}\n`);
    }
  }
});
child.on('close', (code) => out.end(() => process.exit(code ?? 1)));
