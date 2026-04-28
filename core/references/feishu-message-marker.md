# Feishu Message Marker

ClawSeat seats that push user-visible Feishu messages add a human-readable
prefix and a machine-readable footer. Koder can use both signals to route a
reply back to the correct TUI session.

## Format

```markdown
[Memory]
Message body.

---
_via Memory @ 2026-04-27T19:00:00Z | project=install | session=install-memory_
```

Patrol includes the mode in the prefix:

```markdown
[PATROL scope=patrol]
Message body.

---
_via Patrol @ 2026-04-27T19:00:00Z | project=install | session=install-patrol_
```

## Fields

- Prefix: `[Memory]`, `[PATROL scope=patrol]`, or `[PATROL scope=test]`.
- Seat: source seat name in the footer.
- Timestamp: UTC ISO8601, generated at send time.
- Project: from `CLAWSEAT_PROJECT`, `AGENTS_PROJECT`, payload metadata, or
  `unknown`.
- Session: from `tmux display-message -p '#S'`, or `unknown`.

## Parsing Rules

Recommended regex:

```text
^\[(?P<seat>Memory|PATROL)(?: scope=(?P<scope>patrol|test))?\]
^_via (?P=seat) @ (?P<ts>[^|]+) \| project=(?P<project>[^|]+) \| session=(?P<session>[^_]+)_$
```

Koder should require prefix and footer to agree on seat. For patrol, the prefix
scope is authoritative. If the footer is missing or malformed, Koder may still
display the message but should not use it for automatic routing.

## Anti-Spoofing

This is not cryptographic authentication. It is a dual-signal convention:
humans see the source at the top, and automation verifies the footer plus tmux
session. Forged user text without the correct footer should be treated as
unroutable.

## Sender Responsibilities

- Stop hooks add the prefix and footer automatically.
- Seats should not manually include the marker in normal prose.
- Missing tmux session must fall back to `session=unknown`.
