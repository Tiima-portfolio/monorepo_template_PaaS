# Trust zones

Templates for running PR code and the trusted factory in separate Kubernetes
namespaces. Nothing here is applied automatically; the CI/platform team
adapts and applies it with its own tooling.

Everything that runs in a PR can be malicious: verify runs the PR's lint,
build, tests, mutation runs and container builds. The trusted factory (gate,
admission, evidence signing, release, merge control) decides what that code
is allowed to do. The two must be security boundaries, not runner labels.

| | `factory-pr` | `factory-trusted` |
| --- | --- | --- |
| Runs | Verify jobs of PRs and of the merge queue | Gate, admission, collector and signing, release, queue controller, `main` verify |
| Runner pools | `pr`, `queue` | `trusted`, `main` |
| Service account | `pr-runner`: no cluster API access, no secrets mounted | `factory-runner`: only the secrets its jobs name |
| Network | DNS, package and image mirror, the `buildkit-pr` instance | GitHub, evidence bucket and index, registry with write access, `buildkit-main` |
| Lifetime | One job per pod; the pod is destroyed after it | Ephemeral runners as well; long-lived services only for the controller |

[`zones.yaml`](zones.yaml) holds the namespaces, service accounts and network
policies. Points to adapt:

- **Mirror and BuildKit selectors.** The policies admit the mirror and the PR
  BuildKit instance by namespace label; use your own labels.
- **Cloud metadata.** Egress to the node metadata address (169.254.169.254) is
  not in any allow rule, so a PR pod can't read node credentials. Check that
  your CNI enforces egress policies.
- **No cluster API.** `automountServiceAccountToken: false` on the PR service
  account, and no RBAC bound to it.
- **Distinct nodes.** Where the threat model asks for hardware separation, add
  a node pool and taint for the PR zone and a matching toleration in
  [`runners/pr.values.yaml`](../runners/pr.values.yaml) and
  [`runners/queue.values.yaml`](../runners/queue.values.yaml).
- **Workflow side.** Set `FACTORY_RUNNER_TRUSTED` (a repository variable) so
  the gate and admission jobs use the `trusted` pool; unset, they use the
  same pool as before.

What stays true in either zone: PR jobs get a job token with read access only,
the registry login exists only while the toolchain images are pulled, and
admission reads job conclusions from GitHub, never from a record the PR zone
wrote.
