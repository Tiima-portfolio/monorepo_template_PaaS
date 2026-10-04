# Evidence-Driven Software Factory

## High-Level Vision

The Software Factory is a controlled production system for verified software changes.

Humans and agents create candidate changes. The factory determines:

- what changed
- what is affected
- which operational boundary owns the change
- what risk the change introduces
- what evidence is required
- whether the available evidence is sufficient
- whether the change is safe to integrate

The core principle is:

> **Humans and agents create changes. The factory decides, based on deterministic evidence and policy, whether those changes are safe to integrate.**

The target flow is:

```text
Intent
  ↓
Bounded change
  ↓
Impact + risk analysis
  ↓
Required evidence
  ↓
Verification
  ↓
Admission decision
  ↓
Controlled integration
  ↓
Main
  ↓
Deployment
  ↓
Production evidence
```

Humans and agents use the same factory:

```text
Human ─┐
       ├──> Change ──> Factory
Agent ─┘
```

The factory should not primarily care who wrote the code. It should care about:

- what changed
- what is affected
- who owns it
- what risk it creates
- what evidence exists
- whether policy allows integration

---

# Core Tenets

## 1. Main Is the Integrated Product

`main` is not a dumping ground waiting for stabilization.

> **If a change is not safe enough to integrate, it does not enter main.**

Desired model:

```text
change
  ↓
verify
  ↓
integrate
  ↓
main remains releasable
```

Avoid:

```text
merge everything
  ↓
stabilization
  ↓
integration testing
  ↓
fix problems
  ↓
release
```

Release branches may temporarily exist, but integration should move toward trunk.

---

## 2. Every Change Stays Within One Operational Boundary

The repository is divided into a small number of deliberately defined operational boundaries.

Example:

```text
monorepo/
├── product/
│   ├── frontend/
│   ├── backend/
│   ├── services/
│   ├── libraries/
│   └── tests/
│
├── tools/
├── ci/
├── platform/
└── test-framework/
```

Typical boundaries:

- **Product**
- **Tools**
- **CI / Software Factory**
- **Platform**
- **Shared test infrastructure**

A normal change belongs to exactly one operational boundary.

Examples:

```text
Feature change
→ product/**

CI optimization
→ ci/**

Developer tooling change
→ tools/**

Kubernetes/runtime infrastructure change
→ platform/**
```

A change crossing boundaries is exceptional and must be explicitly justified or split.

Example:

```text
product/** changed
+
ci/** changed
+
platform/** changed

→ cross-boundary change
→ reject, split, or require explicit approval
```

Inside the `product/` boundary, frontend, backend, services and tests can evolve together when they belong to one coherent product change.

The important distinction is:

```text
Boundary
    ↓
Which operational area owns the change?

Component impact
    ↓
What parts of the system can break because of it?
```

A product change can affect multiple product components while still remaining within a single operational boundary.

---

## 3. Integration Is Evidence-Based, Not Approval-Based

A green pipeline should not merely mean that some jobs happened to pass.

It should mean:

> **All evidence required by policy exists for this exact change.**

Example:

```text
R1 change

✓ build
✓ unit tests
✓ dependency validation
✓ static analysis
✓ independent review
```

The admission decision is:

```text
policy
+
evidence
=
merge allowed / merge denied
```

---

## 4. Validation Follows Impact, Not Repository Size

A monorepo must not mean:

```text
one changed file
→ rebuild everything
→ test everything
```

The factory determines:

```text
what changed?
      ↓
what depends on it?
      ↓
what could realistically break?
      ↓
what must be verified?
```

The dependency graph is therefore a foundational asset of the factory.

A key scalability rule is:

> **The cost of verification should scale with the blast radius of the change, not with the size of the repository.**

---

## 5. Human Attention Is Reserved for Uncertainty

Human review is expensive and limited.

Machines should prove things that machines can prove:

- compilation
- test results
- API compatibility
- dependency rules
- security rules
- formatting
- policy compliance
- reproducibility

Humans should primarily decide:

- Is this actually the intended behavior?
- Is the architecture appropriate?
- Are the tradeoffs acceptable?
- Is this unusual enough to require judgment?

Therefore:

> **Machines verify properties. Humans resolve uncertainty.**

---

## 6. Creation May Be Probabilistic; Integration Must Be Deterministic

LLMs and agents may:

- generate code
- propose tests
- refactor
- review
- repair
- investigate

Those activities may be probabilistic.

Admission into the product should rely as much as possible on deterministic mechanisms:

```text
tests
contracts
schemas
dependency graphs
policies
reproducible builds
security controls
```

Therefore:

> **Never use confidence in an agent as a substitute for verification.**

---

## 7. Agents Are Workers, Not Exceptions

Do not create separate CI systems for humans and agents.

Avoid:

```text
human CI
agent CI
```

Use:

```text
Change
  ↓
same factory
```

Agent-generated changes carry additional provenance such as:

- agent identity
- model
- task
- initiating human or system
- tool usage
- execution context

But they use the same:

```text
impact analysis
risk evaluation
evidence requirements
admission
integration
```

---

## 8. Autonomy Is Earned

Agents should not receive blanket autonomy.

Their autonomy should increase based on observed performance, risk and scope.

Example:

```text
experimental
    ↓
observed
    ↓
trusted
    ↓
autonomous
```

Autonomy should depend on:

```text
agent
+
component
+
change type
+
risk level
```

A documentation agent may become autonomous quickly.

An agent modifying authentication, database schemas or critical infrastructure may always require human approval.

---

## 9. Integration Capacity Is Centrally Controlled

Hundreds of humans and agents must not race directly into `main`.

Avoid:

```text
300 agents
→ 300 simultaneous merges
```

Use:

```text
candidate changes
      ↓
admission passed
      ↓
merge queue
      ↓
compatibility / ordering
      ↓
merge train
      ↓
main
```

Integration throughput is an explicit factory resource.

Useful metrics include:

- merge queue time
- verification time
- revalidation time
- merge conflict rate
- abandoned changes
- rework after integration

Interactive human work should not be starved by background agent work.

Possible priority model:

```text
P0 emergency
P1 human interactive work
P2 release-critical agent work
P3 normal agent work
P4 maintenance / background work
```

---

## 10. Measure Flow and Outcomes, Not Activity

Do not optimize for:

```text
commits/day
agent runs/day
pipelines/day
lines of code
```

These metrics become increasingly meaningless in an agentic environment.

Measure instead:

```text
Intent → Production Lead Time
```

and its components:

- planning time
- implementation time
- queue time
- verification time
- human attention time
- integration time
- deployment time

Quality and outcome metrics should include:

- change failure rate
- rollback rate
- escaped defects
- rework
- failed agent attempts
- human intervention rate
- defect escape rate

The factory should answer:

> **What limits our ability to safely deliver?**

---

# Additional Factory Principles

## Everything Is Attributable

Every action must trace back to:

```text
intent
→ actor
→ change
→ evidence
→ decision
```

The actor can be:

- human
- agent
- automation

---

## Failure Is Contained

A bad candidate change should fail inside its own boundary.

Prefer:

```text
candidate fails
```

over:

```text
main breaks
→ everyone investigates
```

Isolation is therefore a first-class architectural property.

---

## Quality Cannot Be Silently Traded Away

Testing, security, architecture checks and other quality activities are part of the definition of a valid change.

Deadline pressure must not silently transform:

```text
required evidence
```

into:

```text
optional evidence
```

If policy is overridden, the override must itself be explicit, attributable and visible.

---

# Scaling Target

The architecture should be designed for agent-era throughput from the beginning.

A reasonable target is:

```text
Normal operation:
~300 changes / merge requests per day

Design target:
~1000 changes / merge requests per day

Burst tolerance:
significantly above the daily average
```

The factory must therefore support:

- queues
- backpressure
- priorities
- rate limits
- fair scheduling
- impact-based validation
- reusable build/test results
- selective integration environments

The system must not assume:

```text
1 MR
=
full system build
+
full integration environment
+
all E2E tests
+
mandatory human review
```

Instead validation should scale by risk and impact.

Example:

```text
R0
→ static checks / lint

R1
→ build + unit + targeted tests

R2
→ build + unit + contracts + selected integration

R3
→ broad integration + high-risk validation + human approval
```

The real factory throughput is approximately:

```text
Throughput =
min(
  change-analysis capacity,
  build capacity,
  test capacity,
  environment capacity,
  human-attention capacity,
  integration capacity
)
```

Every queue should therefore be observable.

Example:

```text
Intent → Code               4 min
Code → Verification         1 min
Verification                7 min
Waiting for environment    18 min  ← bottleneck
Waiting for human           2 min
Merge queue                 3 min
Deployment                  5 min
```

The objective is to continuously identify and remove the real constraint.

---

# Summary

The Evidence-Driven Software Factory follows a simple philosophy:

> **Do not trust changes. Prove them.**

Humans and agents create bounded candidate changes.

The factory:

1. identifies the operational boundary
2. determines component impact
3. assesses risk
4. defines required evidence
5. runs only relevant verification
6. admits or rejects the change
7. controls integration into `main`
8. records production outcomes
9. feeds those outcomes back into future policy and improvement

The desired end state is not simply faster CI/CD.

It is a system where:

> **High development throughput can increase without proportionally increasing integration risk, human review load, or stabilization work.**
