// Dependency rules on the Nx project graph, from ci/policy/invariants.yaml.
import { loadPolicy } from './lib/policy.mjs';

const area = (root) => root.split('/')[0];

// graph: Nx graph JSON ({ nodes, dependencies }). Returns violations.
export function checkDependencies(graph, policy = loadPolicy('invariants')) {
  const problems = [];
  const root = (name) => graph.nodes[name]?.data?.root;
  for (const [source, edges] of Object.entries(graph.dependencies)) {
    if (!root(source)) continue;
    const from = area(root(source));
    for (const { target, type } of edges) {
      if (!root(target)) continue; // external packages
      const to = area(root(target));
      const allowed = policy.dependencies[from] || [];
      if (!allowed.includes(to)) problems.push(`${source} (${from}) may not depend on ${target} (${to})`);
      else if (from !== to && type === 'static') problems.push(`${source} imports ${target}'s code across boundaries; depend on its published contract or release instead`);
    }
  }
  for (const cycle of findCycles(graph, policy.no_cycles)) problems.push(`dependency cycle: ${cycle.join(' -> ')}`);
  return problems;
}

function findCycles(graph, areas) {
  const inScope = (n) => graph.nodes[n] && areas.includes(area(graph.nodes[n].data.root));
  const state = {};
  const stack = [];
  const cycles = [];
  const visit = (n) => {
    state[n] = 'open';
    stack.push(n);
    for (const { target } of graph.dependencies[n] || []) {
      if (!inScope(target)) continue;
      if (state[target] === 'open') cycles.push([...stack.slice(stack.indexOf(target)), target]);
      else if (!state[target]) visit(target);
    }
    stack.pop();
    state[n] = 'done';
  };
  for (const n of Object.keys(graph.nodes)) if (inScope(n) && !state[n]) visit(n);
  return cycles;
}
