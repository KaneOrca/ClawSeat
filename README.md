# ClawSeat

ClawSeat is a skill-first multi-agent control plane for OpenClaw, Claude Code, and Codex.

## OpenClaw Quickstart

macOS first-install now has one canonical path:

```bash
git clone https://github.com/KaneOrca/ClawSeat.git ~/.clawseat
export CLAWSEAT_ROOT="$HOME/.clawseat"

python3 "$CLAWSEAT_ROOT/shells/openclaw-plugin/install_openclaw_bundle.py"
python3 "$CLAWSEAT_ROOT/core/skills/clawseat-install/scripts/openclaw_first_install.py"
```

What the canonical installer does:

- repairs `~/.openclaw/skills/*` and `~/.openclaw/workspace-koder/skills/*` symlinks
- runs `python3 "$CLAWSEAT_ROOT/core/preflight.py" install --runtime openclaw --auto-fix`
- initializes or refreshes `~/.openclaw/workspace-koder`
- ensures `~/.agents/profiles/install-profile-dynamic.toml` exists and matches the current schema
- bootstraps materialized seats for the canonical `install` project
- starts `planner` only if its `tool/auth_mode/provider` are already explicitly configured

If planner is not configured yet, the installer stops at a clear configuration gate and prints the single next command to run.

## Docs

- [Install Guide](docs/INSTALL_GUIDE.md) — quickstart, dependency tiers, preflight
- [Post-Install](docs/POST_INSTALL.md) — daily use, provider swap, logs, diagnosing the gate
- [Runtime Environment](docs/RUNTIME_ENV.md) — env vars, directory contracts, checkout drift
- [Install Notes](docs/INSTALL.md) — path contract, profile placeholders, role-first bootstrap
- [Packaging](docs/PACKAGING.md)
