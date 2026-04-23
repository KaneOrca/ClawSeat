# Sandbox HOME leak audit (#15)

Scanner: gemini session, 2026-04-24
Scope: /Users/ywf/ClawSeat (experimental)

## Call site inventory

| file:line | expr | seat context? | classification | recommendation |
|-----------|------|---------------|----------------|----------------|
| `core/tui/ancestor_brief.py:129` | Path.home() | yes | **SWITCH** | Used to tilde-ify paths; in seat context, it uses sandbox HOME. |
| `core/tui/ancestor_brief.py:168` | Path.home() | yes | **SWITCH** | Used to find `~/.openclaw`; will miss operator's real config. |
| `core/tui/ancestor_brief.py:335` | Path.home() | yes | **SWITCH** | Default path for writing brief; currently lands in sandbox. |
| `core/launchers/agent-launcher-discover.py:46` | Path.home() | yes | **SWITCH** | Discovery home for project search. |
| `core/launchers/agent-launcher-fuzzy.py:11` | Path.home() | yes | **SWITCH** | Fallback for recent project search. |
| `core/scripts/seat_claude_template.py:15` | Path.home() | yes | **SWITCH** | Root for engineer profiles; misses real `~/.agents/engineers`. |
| `core/scripts/agent_admin_session.py:126` | Path.home() | yes | **SWITCH** | Fallback in `_real_home_for_tool_seeding`. |
| `core/scripts/agent_admin_session.py:402` | Path.home() | yes | **SWITCH** | **HIGH RISK**: used to locate launcher secret targets. |
| `core/scripts/agent_admin_session.py:535` | Path.home() | yes | **SWITCH** | **HIGH RISK**: used to construct runtime identity dirs. |
| `core/migration/dynamic_common.py:295` | Path.home() | yes | **SWITCH** | Default `session_root`; leads to nested identity dirs. |
| `core/lib/real_home.py:* ` | Path.home() | N/A | **OK** | Canonical implementation of the resolver. |
| `scripts/env_scan.py:32` | Path.home() | no | **KEEP** | User-level preflight tool. |
| `core/scripts/modal_detector.py:266` | Path.home() | no | **KEEP** | Installs system-level LaunchAgent. |
| `scripts/install.sh:* ` | $HOME | yes/no | **KEEP/SWITCH** | Multiple sites; some need REAL_HOME for persistent state. |
| `tests/*` | Path.home() | N/A | **OK** | Test fixtures often use/mock Path.home(). |

## Summary counts

- Total `Path.home()` / `expanduser` / `$HOME` sites audited: ~150 (including comments/docs)
- KEEP (user-level only): ~5
- SWITCH to real_user_home(): 12  â† HIGH PRIORITY
- OK as-is: ~100 (canonical helpers, tests, docstrings)
- AMBIGUOUS: 2 (flagged for review)

## High-risk summary

The most critical "leaks" are in `agent_admin_session.py` and `dynamic_common.py`. When a "Manager" seat (ancestor) tries to spawn a new sub-agent, it uses `Path.home()` to decide where to write the new agent's secret files and where to create its identity directory. Because the Manager itself is sandboxed, it nests the new agent's entire world INSIDE its own sandbox (`~/.agent-runtime/identities/...`), making the child agent's state invisible to the operator and prone to deletion when the Manager session ends.

### Immediate Action
Switch `core/scripts/agent_admin_session.py` to use `core.lib.real_home.real_user_home()` for all operator-level path construction.
