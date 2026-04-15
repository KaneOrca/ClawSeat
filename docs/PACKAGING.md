# ClawSeat Packaging

ClawSeat should ship as one product package.

For end users, `gstack-harness` is an internal runtime dependency, not a
separate install target. A complete ClawSeat package must therefore include
both the ClawSeat product layer and the embedded `gstack-harness` runtime
core.

## Packaging Goal

The target experience is:

1. the user gives OpenClaw a single repository URL
2. OpenClaw installs `clawseat` from that repo as a skill/plugin bundle
3. OpenClaw loads ClawSeat and runs the install/bootstrap/configure/verify flow
4. the user does not need to know `/cs`, `gstack-harness`, or internal repo layout

## Required In A Complete Package

These paths are required for a complete OpenClaw-capable ClawSeat package.

### 1. Repository entrypoints

- `README.md`
- `marketplace.json`
- `.claude-plugin/plugin.json`
- `manifest.toml`

These make the repository installable as a single OpenClaw-facing product.

### 2. Product-level ClawSeat skills

- `core/skills/clawseat/`
- `core/skills/clawseat-install/`
- `core/skills/clawseat-koder-frontstage/`
- `core/skills/cs/`

These define the product entry, install flow, frontstage behavior, and local
shortcut compatibility.

### 3. Embedded runtime core

- `core/skills/gstack-harness/`

This is the reusable orchestration core. It must ship inside ClawSeat and is
not treated as a separate end-user product dependency.

### 4. Control plane and runtime code

- `core/adapter/`
- `core/bootstrap_receipt.py`
- `core/engine/`
- `core/harness_adapter.py`
- `core/migration/`
- `core/preflight.py`
- `core/scripts/`
- `core/shell-scripts/`
- `core/templates/`
- `core/transport/`
- `adapters/harness/tmux-cli/`

These are required for bootstrap, seat instantiation, transport, migration,
preflight, and runtime adapter behavior.

### 5. OpenClaw integration layer

- `shells/openclaw-plugin/`

This is the bridge that lets OpenClaw bootstrap ClawSeat as a product.

### 6. Default starter profiles

- `examples/starter/profiles/`

These provide the canonical starter/install/full-team project profiles.

## Optional In The Product Package

These are not required for the minimum OpenClaw-facing ClawSeat package:

- `adapters/projects/cartooner/`
- `adapters/projects/openclaw/`
- `examples/arena-pretext-ui/`
- most project-specific or consumer-specific docs

They can ship in the monorepo, but they are not part of the minimum product
bundle needed to make ClawSeat installable and runnable.

## Product Boundary

For packaging purposes, think of the layers like this:

- `gstack specialist skills` = professional abilities
- `gstack-harness` = orchestration engine
- `ClawSeat` = installable product wrapper around that engine

The user installs only **ClawSeat**.
ClawSeat carries `gstack-harness` internally.

## Exporting The Product Bundle

To build a clean publishable bundle from this repo:

```bash
python3 /Users/ywf/coding/ClawSeat/core/scripts/build_product_bundle.py --clean
```

This exports the minimum complete package to:

- `/tmp/clawseat-product-bundle`

To include optional consumer adapters and extra docs too:

```bash
python3 /Users/ywf/coding/ClawSeat/core/scripts/build_product_bundle.py --clean --include-optional
```
