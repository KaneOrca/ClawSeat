#!/usr/bin/env python3
"""iTerm2 Python API driver for ClawSeat native-panel monitor windows.

Reads a JSON payload on stdin describing the panes to open, then drives
iTerm2 via its Python API (https://iterm2.com/python-api/) to create one
window with N native iTerm panes in a balanced grid. Each pane runs a
single-layer `tmux attach -t <session>` so the Claude / Codex / Gemini
TUI gets fully native keyboard + mouse input — no nested tmux.

SAFETY GUARANTEES (covered by tests/test_iterm_panes_driver.py):
  • This driver never executes ANY tmux command directly. The only tmux
    activity is whatever the operator-supplied `command` field runs INSIDE
    each pane (typically `tmux attach -t <session>`), which by design is
    a client operation that can never delete a session.
  • Closing an iTerm pane sends SIGHUP → bash → tmux client detach. The
    inner tmux session survives; verified by test_session_survives_pane_close.
  • Partial build failure (e.g., iTerm refuses a split because the window
    is too small) closes the half-built window so the operator never sees
    a confusing 2-pane window when 6 were requested.
  • Bad input (non-list panes, n=0, n>8, unknown keys) returns a structured
    error JSON without ever opening an iTerm window.
  • Hard cap of 8 panes (per iTerm Python API smoke testing — at 9+ the
    minimum pane size is < 80 columns on a 27" 4K display and TUIs break).

Why this path: iTerm2's official tmux-integration docs
(https://iterm2.com/documentation-tmux-integration.html) call out nested
tmux as the reason `tmux -CC` exists; AppleScript split-pane is marked
Deprecated in iTerm's docs sidebar. The Python API's async_split_pane
returns the new Session synchronously so there's no p3-style race that
bit our earlier AppleScript prototype.

Payload on stdin::

    {
      "title": "install",                  // iTerm window title (string)
      "panes": [                            // list, length 1..8
        {"label": "memory",    "command": "tmux attach -t '=install-memory-claude'"},
        {"label": "planner",   "command": "tmux attach -t '=install-planner-claude'"},
        ...
      ],
      "send_delay_ms": 250                  // optional, default 250ms before send_text
    }

Output on stdout (stdlib json):

    {"status": "ok", "panes_created": 6, "window_id": "w0"}

Failure output on stdout (driver still exits 0; ClawSeat caller checks status field):

    {"status": "error", "reason": "...", "fix": "..."}

Requires iTerm2's Python API to be enabled
(Preferences → General → Magic → Enable Python API) and the `iterm2`
module installed (`pip install --user iterm2`).
"""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

try:
    import iterm2  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover — surfaced as a friendly runtime error
    print(
        json.dumps({
            "status": "error",
            "reason": "iterm2 module not installed",
            "fix": "pip3 install --user --break-system-packages iterm2",
        }),
        file=sys.stderr,
    )
    raise SystemExit(2)


# Hard cap. At 9+ panes on a 27" 4K display each pane is below the ~80 col
# minimum that claude/codex/gemini need; testing showed they corrupt their
# own UI rather than gracefully degrade. Operators wanting more should
# split into multiple windows or tabs.
MAX_PANES = 8

# Default delay before async_send_text — the new pane's shell sources
# .zshrc / .bashrc, which can take 100-300ms (pyenv rehash, prompt setup).
# Sending text before the prompt is ready means it lands as MOTD output
# and is NEVER interpreted by the shell. 250ms covers the 95th percentile.
DEFAULT_SEND_DELAY_MS = 250

# Wall-clock guard: build never blocks longer than this. iTerm bugs
# occasionally hang async calls; better to fail loud than hang the caller.
BUILD_TIMEOUT_SECONDS = 30.0


# Layout shape → list of (parent_index, vertical) split instructions.
# parent_index is the index into the growing `sessions` list at the time
# of the split; vertical=True makes a new pane to the RIGHT of parent.
# Panes are filled in creation order, matching payload["panes"].
_LAYOUT_RECIPES: dict[int, list[tuple[int, bool]]] = {
    1: [],
    2: [(0, True)],
    3: [(0, True), (0, False)],                          # 2 cols, bottom-left
    4: [(0, True), (0, False), (1, False)],              # 2x2
    5: [(0, True), (1, True), (0, False), (1, False)],   # 3 cols top, 2 bottoms
    6: [(0, True), (1, True), (0, False), (1, False), (2, False)],  # 2x3
    7: [(0, True), (1, True), (0, False), (1, False), (2, False), (3, True)],
    8: [(0, True), (1, True), (0, False), (1, False), (2, False), (3, True), (4, True)],
}


def _validate_payload(payload: Any) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return (validated_payload, error). Exactly one is non-None."""
    if not isinstance(payload, dict):
        return None, {"status": "error", "reason": "payload must be a JSON object"}
    panes = payload.get("panes")
    if not isinstance(panes, list):
        return None, {"status": "error", "reason": "panes must be a list"}
    n = len(panes)
    if n < 1:
        return None, {"status": "error", "reason": "panes list is empty"}
    if n > MAX_PANES:
        return None, {
            "status": "error",
            "reason": f"{n} panes exceeds MAX_PANES={MAX_PANES}",
            "fix": "split into multiple windows/tabs",
        }
    cleaned: list[dict[str, str]] = []
    for i, p in enumerate(panes):
        if not isinstance(p, dict):
            return None, {"status": "error", "reason": f"pane[{i}] must be an object"}
        label = p.get("label", "")
        command = p.get("command", "")
        if not isinstance(label, str):
            return None, {"status": "error", "reason": f"pane[{i}].label must be string"}
        if not isinstance(command, str):
            return None, {"status": "error", "reason": f"pane[{i}].command must be string"}
        # Strip control characters from labels — iTerm rejects \n in titles.
        label = "".join(c for c in label if c.isprintable())[:64]
        cleaned.append({"label": label, "command": command})
    title = payload.get("title", "ClawSeat")
    if not isinstance(title, str):
        title = "ClawSeat"
    title = "".join(c for c in title if c.isprintable())[:128]
    delay = payload.get("send_delay_ms", DEFAULT_SEND_DELAY_MS)
    if not isinstance(delay, (int, float)) or delay < 0 or delay > 5000:
        delay = DEFAULT_SEND_DELAY_MS

    # Optional `recipe` field overrides _LAYOUT_RECIPES[n] for callers that
    # need non-balanced layouts (e.g. v2 workers window with planner main left
    # 50% + N-1 workers in right grid; or v2 memories window with max-2-rows
    # column-major fill). Recipe is a list of [parent_idx, vertical_bool] pairs;
    # length must equal n-1.
    recipe = payload.get("recipe")
    if recipe is not None:
        if not isinstance(recipe, list):
            return None, {"status": "error", "reason": "recipe must be a list when provided"}
        if len(recipe) != n - 1:
            return None, {
                "status": "error",
                "reason": f"recipe length {len(recipe)} != n-1 ({n - 1})",
                "fix": "recipe must contain exactly n-1 split steps",
            }
        cleaned_recipe: list[tuple[int, bool]] = []
        for i, step in enumerate(recipe):
            if not isinstance(step, list) or len(step) != 2:
                return None, {"status": "error", "reason": f"recipe[{i}] must be [parent_idx, vertical_bool]"}
            parent_idx, vertical = step
            if not isinstance(parent_idx, int) or parent_idx < 0 or parent_idx > i:
                return None, {"status": "error", "reason": f"recipe[{i}] parent_idx invalid: {parent_idx}"}
            if not isinstance(vertical, bool):
                return None, {"status": "error", "reason": f"recipe[{i}] vertical must be bool"}
            cleaned_recipe.append((parent_idx, vertical))
        return {"title": title, "panes": cleaned, "send_delay_ms": int(delay), "recipe": cleaned_recipe}, None
    return {"title": title, "panes": cleaned, "send_delay_ms": int(delay)}, None


async def _safe_close_window(window: Any) -> None:
    """Best-effort close of a half-built window. Never raises."""
    if window is None:
        return
    try:
        await window.async_close(force=True)
    except Exception:  # noqa: BLE001 silent-ok: cleanup best-effort
        pass


async def _build_layout(connection: Any, payload: dict[str, Any]) -> dict[str, Any]:
    title = payload["title"]
    panes = payload["panes"]
    delay_s = payload["send_delay_ms"] / 1000.0
    n = len(panes)

    # Materialize the App first — without it, window.current_tab can be None
    # (the SDK populates the tree as part of get_app, not Window.create).
    try:
        await iterm2.async_get_app(connection)
    except Exception as exc:  # noqa: BLE001 broad catch is correct: we want to surface
        return {"status": "error", "reason": f"async_get_app failed: {exc!r}"}

    window = None
    try:
        window = await iterm2.Window.async_create(connection)
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "reason": f"async_create window failed: {exc!r}"}
    if window is None:
        return {"status": "error", "reason": "iTerm refused to create a window"}

    try:
        try:
            await window.async_set_title(title)
        except Exception:  # noqa: BLE001 silent-ok: title is cosmetic, older iTerm may lack it
            pass

        if window.current_tab is None or window.current_tab.current_session is None:
            await _safe_close_window(window)
            return {
                "status": "error",
                "reason": "iTerm window has no initial session",
                "fix": "upgrade iTerm to 3.4+ with Python API enabled",
            }

        # Use payload-supplied recipe if provided, else fall back to balanced
        # _LAYOUT_RECIPES[n] for backwards compat with v1 callers.
        recipe = payload.get("recipe") or _LAYOUT_RECIPES[n]
        sessions: list[Any] = [window.current_tab.current_session]
        for step_idx, (parent_idx, vertical) in enumerate(recipe, start=1):
            try:
                parent = sessions[parent_idx]
                new_pane = await parent.async_split_pane(vertical=vertical)
            except Exception as exc:  # noqa: BLE001
                await _safe_close_window(window)
                return {
                    "status": "error",
                    "reason": (
                        f"split-pane step {step_idx}/{len(recipe)} failed: "
                        f"{exc!r}"
                    ),
                    "fix": "iTerm window may be too small for the layout",
                }
            if new_pane is None:
                await _safe_close_window(window)
                return {
                    "status": "error",
                    "reason": (
                        f"split-pane step {step_idx} returned None — "
                        "iTerm refused (window too small?)"
                    ),
                    "fix": "resize the iTerm window or reduce the pane count",
                }
            sessions.append(new_pane)

        # Wait for shell prompts to be ready before sending commands.
        # Without this, send_text races shell startup and commands can be
        # dropped (observed in early prototypes).
        if delay_s > 0:
            await asyncio.sleep(delay_s)

        for session, spec in zip(sessions, panes):
            label = spec["label"]
            command = spec["command"]
            if label:
                try:
                    await session.async_set_name(label)
                except Exception:  # noqa: BLE001 silent-ok: label is cosmetic
                    pass
                setter = getattr(session, "async_set_variable", None)
                if setter is not None:
                    try:
                        await setter("user.seat_id", label)
                    except Exception:  # noqa: BLE001 silent-ok: metadata is best-effort
                        pass
            if command:
                try:
                    await session.async_send_text(command + "\n")
                except Exception as exc:  # noqa: BLE001
                    # Don't tear down — partial command failure leaves a
                    # usable window with at least the other commands run.
                    print(
                        f"warn: send_text failed for pane {label!r}: {exc!r}",
                        file=sys.stderr,
                    )

        return {
            "status": "ok",
            "panes_created": len(sessions),
            "window_id": window.window_id,
        }
    except Exception as exc:  # noqa: BLE001 - bubble unknown failures with cleanup
        await _safe_close_window(window)
        return {"status": "error", "reason": f"unexpected: {exc!r}"}


async def _main(connection):
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"status": "error", "reason": f"bad json on stdin: {exc}"}))
        return
    validated, err = _validate_payload(payload)
    if err is not None:
        print(json.dumps(err))
        return
    assert validated is not None  # for type checkers
    try:
        result = await asyncio.wait_for(
            _build_layout(connection, validated),
            timeout=BUILD_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        result = {
            "status": "error",
            "reason": f"build timed out after {BUILD_TIMEOUT_SECONDS}s",
            "fix": "iTerm may be hung; try `killall iTerm2` and rerun",
        }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    # iTerm's API server can take a moment to accept the first connection
    # after app launch or preference changes. Retry inside the SDK, but the
    # caller still wraps us in a wall-clock timeout so we never hang forever.
    iterm2.run_until_complete(_main, retry=True)
