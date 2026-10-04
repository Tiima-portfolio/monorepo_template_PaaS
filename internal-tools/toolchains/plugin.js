// Generic Nx plugin for the factory.
//
// Every project is declared by a `service.yaml`. Its `toolchains:` list names
// folders under internal-tools/toolchains/, and each of those folders holds a
// `toolchain.yaml` with the targets Nx runs. Adding a language therefore means
// adding one folder here; nothing else in the workspace changes.

const fs = require('node:fs');
const path = require('node:path');
const YAML = require('yaml');

const TOOLCHAINS_DIR = __dirname;
const SERVICE_GLOB = '{product,internal-services,internal-tools}/**/service.yaml';

function loadToolchains() {
  const toolchains = {};
  for (const entry of fs.readdirSync(TOOLCHAINS_DIR, { withFileTypes: true })) {
    const file = path.join(TOOLCHAINS_DIR, entry.name, 'toolchain.yaml');
    if (entry.isDirectory() && fs.existsSync(file)) {
      toolchains[entry.name] = YAML.parse(fs.readFileSync(file, 'utf8'));
    }
  }
  return toolchains;
}

// The boundary a project belongs to, from its path.
function boundaryOf(root) {
  const [top] = root.split('/');
  return top;
}

function fill(value, vars) {
  if (typeof value === 'string') {
    return value.replace(/\{(name|projectRoot)\}/g, (_, key) => vars[key]);
  }
  if (Array.isArray(value)) return value.map((v) => fill(v, vars));
  return value;
}

// Turns one toolchain target from toolchain.yaml into an Nx target.
function toTarget(spec, vars) {
  const target = {
    executor: 'nx:run-commands',
    options: { command: fill(spec.command, vars), cwd: vars.projectRoot },
    cache: spec.cache !== false,
  };
  // Nx resolves {projectRoot} in inputs and outputs itself.
  if (spec.inputs) target.inputs = spec.inputs;
  if (spec.outputs) target.outputs = spec.outputs;
  if (spec.dependsOn) target.dependsOn = spec.dependsOn;
  return target;
}

function projectFor(file, service, toolchains) {
  const root = path.dirname(file);
  const name = service.name || path.basename(root);
  const vars = { name, projectRoot: root };
  const targets = {};
  const used = service.toolchains || [];
  for (const tc of used) {
    const def = toolchains[tc];
    if (!def) {
      throw new Error(`${file}: unknown toolchain "${tc}". Known: ${Object.keys(toolchains).join(', ') || 'none'}`);
    }
    for (const [targetName, spec] of Object.entries(def.targets || {})) {
      targets[targetName] = toTarget(spec, vars);
    }
  }
  const deps = [...(service.dependsOn || []), ...(service.consumes || [])];
  return {
    root,
    name,
    projectType: service.type === 'library' ? 'library' : 'application',
    tags: [
      `boundary:${boundaryOf(root)}`,
      ...used.map((tc) => `toolchain:${tc}`),
      ...(service.criticality ? [`criticality:${service.criticality}`] : []),
    ],
    implicitDependencies: deps,
    targets,
  };
}

const createNodes = [
  SERVICE_GLOB,
  (files, _options, context) => {
    const toolchains = loadToolchains();
    return files.map((file) => {
      const text = fs.readFileSync(path.join(context.workspaceRoot, file), 'utf8');
      const project = projectFor(file, YAML.parse(text) || {}, toolchains);
      return [file, { projects: { [project.root]: project } }];
    });
  },
];

module.exports = { createNodes, loadToolchains, projectFor };
