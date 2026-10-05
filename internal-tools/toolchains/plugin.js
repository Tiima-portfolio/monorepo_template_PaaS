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
// service.yaml declares a project; each toolchain.yaml is a project too, so
// services can depend on the toolchains they use.
const GLOB = '**/{service,toolchain}.yaml';
const isService = (f) => /^(product|internal-services|internal-tools)\/.+\/service\.yaml$/.test(f);
const isToolchain = (f) => /^internal-tools\/toolchains\/[^/]+\/toolchain\.yaml$/.test(f);

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
    return value.replace(/\{(name|projectRoot|toolchainDir)\}/g, (_, key) => vars[key] ?? `{${key}}`);
  }
  if (Array.isArray(value)) return value.map((v) => fill(v, vars));
  return value;
}

// A target runs in its toolchain's pinned image (`image:` in toolchain.yaml,
// or the target's own `image:`; `image: false` keeps it on the host).
// in-image.sh decides at run time: in the image when
// FACTORY_TOOLCHAIN_IMAGES=true, on the host otherwise.
const quote = (s) => `'${s.replace(/'/g, `'\\''`)}'`;
function inImage(command, image, projectRoot) {
  const runner = path.relative(projectRoot, path.join('internal-tools/toolchains', 'in-image.sh'));
  return `sh ${runner} ${quote(image)} ${quote(command)}`;
}

// Turns one toolchain target from toolchain.yaml into an Nx target.
function toTarget(spec, vars, image) {
  const command = fill(spec.command, vars);
  const target = {
    executor: 'nx:run-commands',
    options: { command: image ? inImage(command, image, vars.projectRoot) : command, cwd: vars.projectRoot },
    cache: spec.cache !== false,
  };
  // Nx resolves {projectRoot} in inputs and outputs itself; only {name} is ours.
  const nameOnly = { name: vars.name, projectRoot: '{projectRoot}' };
  // Host and image results are cached apart.
  if (spec.inputs) target.inputs = [...fill(spec.inputs, nameOnly), ...(image ? [{ env: 'FACTORY_TOOLCHAIN_IMAGES' }] : [])];
  if (spec.outputs) target.outputs = fill(spec.outputs, nameOnly);
  if (spec.dependsOn) target.dependsOn = spec.dependsOn;
  return target;
}

// Two toolchains with a target of the same name run in the order listed,
// for example [go, container]: the Go build, then the image build.
function combine(first, second, targetName) {
  const union = (a, b) => {
    if (!a && !b) return undefined;
    const seen = new Map([...(a || []), ...(b || [])].map((x) => [JSON.stringify(x), x]));
    return [...seen.values()];
  };
  const target = {
    ...first,
    options: { ...first.options, command: `${first.options.command} && ${second.options.command}` },
    cache: first.cache && second.cache,
  };
  const dependsOn = union(first.dependsOn, second.dependsOn)?.filter((d) => d !== targetName);
  if (dependsOn?.length) target.dependsOn = dependsOn;
  else delete target.dependsOn;
  const inputs = union(first.inputs, second.inputs);
  if (inputs) target.inputs = inputs;
  const outputs = union(first.outputs, second.outputs);
  if (outputs) target.outputs = outputs;
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
      // {toolchainDir}: the toolchain's folder, relative to the project, for helper scripts.
      const image = spec.image === false ? null : spec.image || def.image || null;
      const next = toTarget(spec, { ...vars, toolchainDir: path.relative(root, path.join('internal-tools/toolchains', tc)) }, image);
      targets[targetName] = targets[targetName] ? combine(targets[targetName], next, targetName) : next;
    }
  }
  // A toolchain change re-tests and rebuilds the services that use it.
  const deps = [...(service.dependsOn || []), ...(service.consumes || []), ...used.map((tc) => `toolchain-${tc}`)];
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

function toolchainProject(file) {
  const root = path.dirname(file);
  return { root, name: `toolchain-${path.basename(root)}`, projectType: 'library', tags: ['boundary:internal-tools', 'build-tool'], targets: {} };
}

const createNodes = [
  GLOB,
  (files, _options, context) => {
    const toolchains = loadToolchains();
    return files.filter((f) => isService(f) || isToolchain(f)).map((file) => {
      if (isToolchain(file)) {
        const project = toolchainProject(file);
        return [file, { projects: { [project.root]: project } }];
      }
      const text = fs.readFileSync(path.join(context.workspaceRoot, file), 'utf8');
      const project = projectFor(file, YAML.parse(text) || {}, toolchains);
      return [file, { projects: { [project.root]: project } }];
    });
  },
];

module.exports = { createNodes, loadToolchains, projectFor };
