# Skill Catalog

Generated foundation catalog for planner routing and skill discovery. Run `python3 core/scripts/rebuild_skill_catalog.py --force --update-md` to refresh this snapshot and the lazy JSON cache at `~/.agents/cache/skill-catalog.json`.

## Source Notes

- `~/.agents/skills/` - ClawSeat project and machine workflow skills.
- `~/.claude/skills/` - gstack and local Claude skills.
- `~/.claude/plugins/marketplaces/` - Anthropic/Claude marketplace plugin docs.
- `core/references/superpowers-borrowed/` - imported engineering practice references.

Total unique entries in this catalog: 187.

| Skill | Source | Purpose | When to use | Command form |
| --- | --- | --- | --- | --- |
| clawseat-decision-escalation | ~/.agents/skills/ | Routes decisions blocked by automation to operator; enforces 3-option gate. | ClawSeat seat workflow needs this role capability | Skill: clawseat-decision-escalation |
| clawseat-koder | ~/.agents/skills/ | OpenClaw Koder bridge: translates decision payloads, routes Feishu replies, enforces privacy. | ClawSeat seat workflow needs this role capability | Skill: clawseat-koder |
| clawseat-memory | ~/.agents/skills/ | L3 project-memory hub; orchestrates install-memory workflow per RFC-002. | ClawSeat seat workflow needs this role capability | Skill: clawseat-memory |
| clawseat-memory-reporting | ~/.agents/skills/ | Logs dispatch/completion events; maintains project STATUS.md registry. | ClawSeat seat workflow needs this role capability | Skill: clawseat-memory-reporting |
| clawseat-privacy | ~/.agents/skills/ | Pre-commit check gate; blocks exposure of secrets, API keys, tokens. | ClawSeat seat workflow needs this role capability | Skill: clawseat-privacy |
| en-to-zh-translator | ~/.agents/skills/ | en-to-zh-translator Skill | ClawSeat seat workflow needs this role capability | Skill: en-to-zh-translator |
| agent-base | ~/.claude/skills/ | agent-base | Use when the matching workflow is requested | Skill: agent-base |
| agent-reach | ~/.claude/skills/ | Give your AI agent eyes to see the entire internet. 17 platforms via CLI, MCP, curl, and Python scripts. Zero config... | Use when the matching workflow is requested | Skill: agent-reach |
| ast-types | ~/.claude/skills/ | AST Types ![CI](https://github.com/benjamn/ast-types/workflows/CI/badge.svg) | Use when the matching workflow is requested | Skill: ast-types |
| autoplan | ~/.claude/skills/ | Auto-review pipeline — reads the full CEO, design, and eng review skills from disk and runs them sequentially with au... | Use when the matching workflow is requested | Skill: autoplan |
| b4a | ~/.claude/skills/ | Buffer for Array | Use when the matching workflow is requested | Skill: b4a |
| bare-events | ~/.claude/skills/ | bare-events | Use when the matching workflow is requested | Skill: bare-events |
| bare-fs | ~/.claude/skills/ | bare-fs | Use when the matching workflow is requested | Skill: bare-fs |
| bare-os | ~/.claude/skills/ | bare-os | Use when the matching workflow is requested | Skill: bare-os |
| bare-path | ~/.claude/skills/ | bare-path | Use when the matching workflow is requested | Skill: bare-path |
| bare-stream | ~/.claude/skills/ | bare-stream | Use when the matching workflow is requested | Skill: bare-stream |
| bare-url | ~/.claude/skills/ | bare-url | Use when the matching workflow is requested | Skill: bare-url |
| basic-ftp | ~/.claude/skills/ | Basic FTP | Use when the matching workflow is requested | Skill: basic-ftp |
| benchmark | ~/.claude/skills/ | Performance regression detection using the browse daemon. Establishes baselines for page load times, Core Web Vitals,... | Use when the matching workflow is requested | Skill: benchmark |
| browse | ~/.claude/skills/ | Fast headless browser for QA testing and site dogfooding. Navigate any URL, interact with elements, verify page state... | Use when the matching workflow is requested | Skill: browse |
| browsers | ~/.claude/skills/ | @puppeteer/browsers | Use when the matching workflow is requested | Skill: browsers |
| buffer-crc32 | ~/.claude/skills/ | buffer-crc32 | Use when the matching workflow is requested | Skill: buffer-crc32 |
| canary | ~/.claude/skills/ | Post-deploy canary monitoring. Watches the live app for console errors, performance regressions, and page failures us... | Use when the matching workflow is requested | Skill: canary |
| careful | ~/.claude/skills/ | Safety guardrails for destructive commands. Warns before rm -rf, DROP TABLE, force-push, git reset --hard, kubectl de... | Use when the matching workflow is requested | Skill: careful |
| chromium-bidi | ~/.claude/skills/ | WebDriver BiDi for Chromium [![chromium-bidi on npm](https://img.shields.io/npm/v/chromium-bidi)](https://www.npmjs.c... | Use when the matching workflow is requested | Skill: chromium-bidi |
| cliui | ~/.claude/skills/ | cliui | Use when the matching workflow is requested | Skill: cliui |
| codex | ~/.claude/skills/ | OpenAI Codex CLI wrapper — three modes. Code review: independent diff review via codex review with pass/fail gate. Ch... | Use when the matching workflow is requested | Skill: codex |
| color-convert | ~/.claude/skills/ | color-convert | Use when the matching workflow is requested | Skill: color-convert |
| color-name | ~/.claude/skills/ | A JSON with color names and its values. Based on http://dev.w3.org/csswg/css-color/#named-colors. | Use when the matching workflow is requested | Skill: color-name |
| connect-chrome | ~/.claude/skills/ | Launch real Chrome controlled by gstack with the Side Panel extension auto-loaded. One command: connects Claude to a... | Use when the matching workflow is requested | Skill: connect-chrome |
| core | ~/.claude/skills/ | `core` | Use when the matching workflow is requested | Skill: core |
| cso | ~/.claude/skills/ | Chief Security Officer mode. Infrastructure-first security audit: secrets archaeology, dependency supply chain, CI/CD... | Use when the matching workflow is requested | Skill: cso |
| data-uri-to-buffer | ~/.claude/skills/ | data-uri-to-buffer | Use when the matching workflow is requested | Skill: data-uri-to-buffer |
| debug | ~/.claude/skills/ | debug | Use when the matching workflow is requested | Skill: debug |
| degenerator | ~/.claude/skills/ | degenerator | Use when the matching workflow is requested | Skill: degenerator |
| design-consultation | ~/.claude/skills/ | Design consultation: understands your product, researches the landscape, proposes a complete design system (aesthetic... | Use when the matching workflow is requested | Skill: design-consultation |
| design-html | ~/.claude/skills/ | Design finalization: takes an approved AI mockup from /design-shotgun and generates production-quality Pretext-native... | Use when the matching workflow is requested | Skill: design-html |
| design-review | ~/.claude/skills/ | Designer's eye QA: finds visual inconsistency, spacing issues, hierarchy problems, AI slop patterns, and slow interac... | Use when the matching workflow is requested | Skill: design-review |
| design-shotgun | ~/.claude/skills/ | Design shotgun: generate multiple AI design variants, open a comparison board, collect structured feedback, and itera... | Use when the matching workflow is requested | Skill: design-shotgun |
| devtools-protocol | ~/.claude/skills/ | devtools-protocol [![devtools-protocol on npm](https://img.shields.io/npm/v/devtools-protocol)](https://www.npmjs.com... | Use when the matching workflow is requested | Skill: devtools-protocol |
| diff | ~/.claude/skills/ | jsdiff | Use when the matching workflow is requested | Skill: diff |
| document-release | ~/.claude/skills/ | Post-ship documentation update. Reads all project docs, cross-references the diff, updates README/ARCHITECTURE/CONTRI... | Use when the matching workflow is requested | Skill: document-release |
| emoji-regex | ~/.claude/skills/ | emoji-regex [![Build status](https://travis-ci.org/mathiasbynens/emoji-regex.svg?branch=master)](https://travis-ci.or... | Use when the matching workflow is requested | Skill: emoji-regex |
| end-of-stream | ~/.claude/skills/ | end-of-stream | Use when the matching workflow is requested | Skill: end-of-stream |
| escodegen | ~/.claude/skills/ | Escodegen | Use when the matching workflow is requested | Skill: escodegen |
| esprima | ~/.claude/skills/ | [![NPM version](https://img.shields.io/npm/v/esprima.svg)](https://www.npmjs.com/package/esprima) | Use when the matching workflow is requested | Skill: esprima |
| estraverse | ~/.claude/skills/ | Estraverse [![Build Status](https://secure.travis-ci.org/estools/estraverse.svg)](http://travis-ci.org/estools/estrav... | Use when the matching workflow is requested | Skill: estraverse |
| esutils | ~/.claude/skills/ | esutils [![Build Status](https://secure.travis-ci.org/estools/esutils.svg)](http://travis-ci.org/estools/esutils) | Use when the matching workflow is requested | Skill: esutils |
| events-universal | ~/.claude/skills/ | events-universal | Use when the matching workflow is requested | Skill: events-universal |
| fast-fifo | ~/.claude/skills/ | fast-fifo | Use when the matching workflow is requested | Skill: fast-fifo |
| fd-slicer | ~/.claude/skills/ | fd-slicer | Use when the matching workflow is requested | Skill: fd-slicer |
| freeze | ~/.claude/skills/ | Restrict file edits to a specific directory for the session. Blocks Edit and Write outside the allowed path. Use when... | Use when the matching workflow is requested | Skill: freeze |
| fsevents | ~/.claude/skills/ | fsevents [![NPM](https://nodei.co/npm/fsevents.png)](https://nodei.co/npm/fsevents/) | Use when the matching workflow is requested | Skill: fsevents |
| get-caller-file | ~/.claude/skills/ | get-caller-file | Use when the matching workflow is requested | Skill: get-caller-file |
| get-uri | ~/.claude/skills/ | get-uri | Use when the matching workflow is requested | Skill: get-uri |
| gstack | ~/.claude/skills/ | Fast headless browser for QA testing and site dogfooding. Navigate pages, interact with elements, verify state, diff... | Use when the matching workflow is requested | Skill: gstack |
| gstack-upgrade | ~/.claude/skills/ | Upgrade gstack to the latest version. Detects global vs vendored install, runs the upgrade, and shows what's new. Use... | Use when the matching workflow is requested | Skill: gstack-upgrade |
| guard | ~/.claude/skills/ | Full safety mode: destructive command warnings + directory-scoped edits. Combines /careful (warns before rm -rf, DROP... | Use when the matching workflow is requested | Skill: guard |
| http-proxy-agent | ~/.claude/skills/ | http-proxy-agent | Use when the matching workflow is requested | Skill: http-proxy-agent |
| https-proxy-agent | ~/.claude/skills/ | https-proxy-agent | Use when the matching workflow is requested | Skill: https-proxy-agent |
| injected | ~/.claude/skills/ | Injected | Use when the matching workflow is requested | Skill: injected |
| internal | ~/.claude/skills/ | `internal` | Use when the matching workflow is requested | Skill: internal |
| investigate | ~/.claude/skills/ | Systematic debugging with root cause investigation. Four phases: investigate, analyze, hypothesize, implement. Iron L... | Use when the matching workflow is requested | Skill: investigate |
| ip-address | ~/.claude/skills/ | [![CircleCI](https://dl.circleci.com/status-badge/img/circleci/9fJmTZfn8d8p7GtVt688PY/JjriGjhcxBD6zYKygMZaet/tree/mas... | Use when the matching workflow is requested | Skill: ip-address |
| json-schema-to-ts | ~/.claude/skills/ | <img src="assets/header-round-medium.png" width="100%" align="center" /> | Use when the matching workflow is requested | Skill: json-schema-to-ts |
| land-and-deploy | ~/.claude/skills/ | Land and deploy workflow. Merges the PR, waits for CI and deploy, verifies production health via canary checks. Takes... | Use when the matching workflow is requested | Skill: land-and-deploy |
| learn | ~/.claude/skills/ | Manage project learnings. Review, search, prune, and export what gstack has learned across sessions. Use when asked t... | Use when the matching workflow is requested | Skill: learn |
| lru-cache | ~/.claude/skills/ | lru-cache | Use when the matching workflow is requested | Skill: lru-cache |
| mitt | ~/.claude/skills/ | <p align="center"> | Use when the matching workflow is requested | Skill: mitt |
| netmask | ~/.claude/skills/ | Netmask | Use when the matching workflow is requested | Skill: netmask |
| node | ~/.claude/skills/ | Installation | Use when the matching workflow is requested | Skill: node |
| office-hours | ~/.claude/skills/ | YC Office Hours — two modes. Startup mode: six forcing questions that expose demand reality, status quo, desperate sp... | Use when the matching workflow is requested | Skill: office-hours |
| once | ~/.claude/skills/ | once | Use when the matching workflow is requested | Skill: once |
| pac-proxy-agent | ~/.claude/skills/ | pac-proxy-agent | Use when the matching workflow is requested | Skill: pac-proxy-agent |
| pac-resolver | ~/.claude/skills/ | pac-resolver | Use when the matching workflow is requested | Skill: pac-resolver |
| partial-json-parser | ~/.claude/skills/ | Partial JSON Parser | Use when the matching workflow is requested | Skill: partial-json-parser |
| pend | ~/.claude/skills/ | Pend | Use when the matching workflow is requested | Skill: pend |
| plan-ceo-review | ~/.claude/skills/ | CEO/founder-mode plan review. Rethink the problem, find the 10-star product, challenge premises, expand scope when it... | Use when the matching workflow is requested | Skill: plan-ceo-review |
| plan-design-review | ~/.claude/skills/ | Designer's eye plan review — interactive, like CEO and Eng review. Rates each design dimension 0-10, explains what wo... | Use when the matching workflow is requested | Skill: plan-design-review |
| plan-eng-review | ~/.claude/skills/ | Eng manager-mode plan review. Lock in the execution plan — architecture, data flow, diagrams, edge cases, test covera... | Use when the matching workflow is requested | Skill: plan-eng-review |
| playwright | ~/.claude/skills/ | 🎭 Playwright | Use when the matching workflow is requested | Skill: playwright |
| playwright-core | ~/.claude/skills/ | playwright-core | Use when the matching workflow is requested | Skill: playwright-core |
| proxy-agent | ~/.claude/skills/ | proxy-agent | Use when the matching workflow is requested | Skill: proxy-agent |
| proxy-from-env | ~/.claude/skills/ | proxy-from-env | Use when the matching workflow is requested | Skill: proxy-from-env |
| pump | ~/.claude/skills/ | pump | Use when the matching workflow is requested | Skill: pump |
| puppeteer-core | ~/.claude/skills/ | Puppeteer | Use when the matching workflow is requested | Skill: puppeteer-core |
| qa | ~/.claude/skills/ | Systematically QA test a web application and fix bugs found. Runs QA testing, then iteratively fixes bugs in source c... | Use when the matching workflow is requested | Skill: qa |
| qa-only | ~/.claude/skills/ | Report-only QA testing. Systematically tests a web application and produces a structured report with health score, sc... | Use when the matching workflow is requested | Skill: qa-only |
| quickjs-emscripten | ~/.claude/skills/ | quickjs-emscripten | Use when the matching workflow is requested | Skill: quickjs-emscripten |
| retro | ~/.claude/skills/ | Weekly engineering retrospective. Analyzes commit history, work patterns, and code quality metrics with persistent hi... | Use when the matching workflow is requested | Skill: retro |
| review | ~/.claude/skills/ | Pre-landing PR review. Analyzes diff against the base branch for SQL safety, LLM trust boundary violations, condition... | Use when the matching workflow is requested | Skill: review |
| runtime | ~/.claude/skills/ | @babel/runtime | Use when the matching workflow is requested | Skill: runtime |
| sdk | ~/.claude/skills/ | <img src=".github/logo.svg" alt="" width="32"> Claude SDK for TypeScript | Use when the matching workflow is requested | Skill: sdk |
| semver | ~/.claude/skills/ | semver(1) -- The semantic versioner for npm | Use when the matching workflow is requested | Skill: semver |
| setup-browser-cookies | ~/.claude/skills/ | Import cookies from your real Chromium browser into the headless browse session. Opens an interactive picker UI where... | Use when the matching workflow is requested | Skill: setup-browser-cookies |
| setup-deploy | ~/.claude/skills/ | Configure deployment settings for /land-and-deploy. Detects your deploy platform (Fly.io, Render, Vercel, Netlify, He... | Use when the matching workflow is requested | Skill: setup-deploy |
| ship | ~/.claude/skills/ | Ship workflow: detect + merge base branch, run tests, review diff, bump VERSION, update CHANGELOG, commit, push, crea... | Use when the matching workflow is requested | Skill: ship |
| smart-buffer | ~/.claude/skills/ | smart-buffer [![Build Status](https://travis-ci.org/JoshGlazebrook/smart-buffer.svg?branch=master)](https://travis-ci... | Use when the matching workflow is requested | Skill: smart-buffer |
| socks | ~/.claude/skills/ | socks [![Build Status](https://travis-ci.org/JoshGlazebrook/socks.svg?branch=master)](https://travis-ci.org/JoshGlaze... | Use when the matching workflow is requested | Skill: socks |
| socks-proxy-agent | ~/.claude/skills/ | socks-proxy-agent | Use when the matching workflow is requested | Skill: socks-proxy-agent |
| source-map | ~/.claude/skills/ | Source Map | Use when the matching workflow is requested | Skill: source-map |
| streamx | ~/.claude/skills/ | streamx | Use when the matching workflow is requested | Skill: streamx |
| tar-fs | ~/.claude/skills/ | tar-fs | Use when the matching workflow is requested | Skill: tar-fs |
| tar-stream | ~/.claude/skills/ | tar-stream | Use when the matching workflow is requested | Skill: tar-stream |
| teex | ~/.claude/skills/ | teex | Use when the matching workflow is requested | Skill: teex |
| templates | ~/.claude/skills/ | Templated Artifacts | Use when the matching workflow is requested | Skill: templates |
| text-decoder | ~/.claude/skills/ | text-decoder | Use when the matching workflow is requested | Skill: text-decoder |
| ts-algebra | ~/.claude/skills/ | <img src="assets/header-round-medium.png" width="100%" align="center" /> | Use when the matching workflow is requested | Skill: ts-algebra |
| tslib | ~/.claude/skills/ | tslib | Use when the matching workflow is requested | Skill: tslib |
| tui-peer-bridge | ~/.claude/skills/ | >- | Use when the matching workflow is requested | Skill: tui-peer-bridge |
| typed-query-selector | ~/.claude/skills/ | 🏷 Typed `querySelector` | Use when the matching workflow is requested | Skill: typed-query-selector |
| undici-types | ~/.claude/skills/ | undici-types | Use when the matching workflow is requested | Skill: undici-types |
| unfreeze | ~/.claude/skills/ | Clear the freeze boundary set by /freeze, allowing edits to all directories again. Use when you want to widen edit sc... | Use when the matching workflow is requested | Skill: unfreeze |
| webdriver-bidi-protocol | ~/.claude/skills/ | webdriver-bidi-protocol | Use when the matching workflow is requested | Skill: webdriver-bidi-protocol |
| wrappy | ~/.claude/skills/ | wrappy | Use when the matching workflow is requested | Skill: wrappy |
| ws | ~/.claude/skills/ | ws: a Node.js WebSocket library | Use when the matching workflow is requested | Skill: ws |
| y18n | ~/.claude/skills/ | y18n | Use when the matching workflow is requested | Skill: y18n |
| yargs | ~/.claude/skills/ | <p align="center"> | Use when the matching workflow is requested | Skill: yargs |
| yargs-parser | ~/.claude/skills/ | yargs-parser | Use when the matching workflow is requested | Skill: yargs-parser |
| yauzl | ~/.claude/skills/ | Installation | Use when the matching workflow is requested | Skill: yauzl |
| zod | ~/.claude/skills/ | <p align="center"> | Use when the matching workflow is requested | Skill: zod |
| access | ~/.claude/plugins/marketplaces/ | Manage Discord channel access — approve pairings, edit allowlists, set DM/group policy. Use when the user asks to pai... | Use when the matching workflow is requested | Skill: access |
| agent-development | ~/.claude/plugins/marketplaces/ | This skill should be used when the user asks to "create an agent", "add an agent", "write a subagent", "agent frontma... | Use when the matching workflow is requested | Skill: agent-development |
| agent-sdk-dev | ~/.claude/plugins/marketplaces/ | Agent SDK Development Plugin | Use when the matching workflow is requested | Skill: agent-sdk-dev |
| block-dangerous-rm | ~/.claude/plugins/marketplaces/ | Hookify Plugin | Use when the matching workflow is requested | Skill: block-dangerous-rm |
| build-mcp-app | ~/.claude/plugins/marketplaces/ | This skill should be used when the user wants to build an "MCP app", add "interactive UI" or "widgets" to an MCP serv... | Use when the matching workflow is requested | Skill: build-mcp-app |
| build-mcp-server | ~/.claude/plugins/marketplaces/ | This skill should be used when the user asks to "build an MCP server", "create an MCP", "make an MCP integration", "w... | Use when the matching workflow is requested | Skill: build-mcp-server |
| build-mcpb | ~/.claude/plugins/marketplaces/ | This skill should be used when the user wants to "package an MCP server", "bundle an MCP", "make an MCPB", "ship a lo... | Use when the matching workflow is requested | Skill: build-mcpb |
| clangd-lsp | ~/.claude/plugins/marketplaces/ | clangd-lsp | Use when the matching workflow is requested | Skill: clangd-lsp |
| claude-automation-recommender | ~/.claude/plugins/marketplaces/ | Analyze a codebase and recommend Claude Code automations (hooks, subagents, skills, plugins, MCP servers). Use when u... | Use when the matching workflow is requested | Skill: claude-automation-recommender |
| claude-code-setup | ~/.claude/plugins/marketplaces/ | Claude Code Setup Plugin | Use when the matching workflow is requested | Skill: claude-code-setup |
| claude-md-improver | ~/.claude/plugins/marketplaces/ | Audit and improve CLAUDE.md files in repositories. Use when user asks to check, audit, update, improve, or fix CLAUDE... | Use when the matching workflow is requested | Skill: claude-md-improver |
| claude-md-management | ~/.claude/plugins/marketplaces/ | CLAUDE.md Management Plugin | Use when the matching workflow is requested | Skill: claude-md-management |
| claude-plugins-official | ~/.claude/plugins/marketplaces/ | Claude Code Plugins Directory | Use when the matching workflow is requested | Skill: claude-plugins-official |
| code-review | ~/.claude/plugins/marketplaces/ | Code Review Plugin | Use when the matching workflow is requested | Skill: code-review |
| command-development | ~/.claude/plugins/marketplaces/ | This skill should be used when the user asks to "create a slash command", "add a command", "write a custom command",... | Use when the matching workflow is requested | Skill: command-development |
| commit-commands | ~/.claude/plugins/marketplaces/ | Commit Commands Plugin | Use when the matching workflow is requested | Skill: commit-commands |
| configure | ~/.claude/plugins/marketplaces/ | Set up the Discord channel — save the bot token and review access policy. Use when the user pastes a Discord bot toke... | Use when the matching workflow is requested | Skill: configure |
| csharp-lsp | ~/.claude/plugins/marketplaces/ | csharp-lsp | Use when the matching workflow is requested | Skill: csharp-lsp |
| discord | ~/.claude/plugins/marketplaces/ | Discord | Use when the matching workflow is requested | Skill: discord |
| example-command | ~/.claude/plugins/marketplaces/ | An example user-invoked skill that demonstrates frontmatter options and the skills/<name>/SKILL.md layout | Use when the matching workflow is requested | Skill: example-command |
| example-skill | ~/.claude/plugins/marketplaces/ | This skill should be used when the user asks to "demonstrate skills", "show skill format", "create a skill template",... | Use when the matching workflow is requested | Skill: example-skill |
| explanatory-output-style | ~/.claude/plugins/marketplaces/ | Explanatory Output Style Plugin | Use when the matching workflow is requested | Skill: explanatory-output-style |
| fakechat | ~/.claude/plugins/marketplaces/ | fakechat | Use when the matching workflow is requested | Skill: fakechat |
| feature-dev | ~/.claude/plugins/marketplaces/ | Feature Development Plugin | Use when the matching workflow is requested | Skill: feature-dev |
| frontend-design | ~/.claude/plugins/marketplaces/ | Create distinctive, production-grade frontend interfaces with high design quality. Use this skill when the user asks... | Use when the matching workflow is requested | Skill: frontend-design |
| gopls-lsp | ~/.claude/plugins/marketplaces/ | gopls-lsp | Use when the matching workflow is requested | Skill: gopls-lsp |
| greptile | ~/.claude/plugins/marketplaces/ | Greptile | Use when the matching workflow is requested | Skill: greptile |
| hook-development | ~/.claude/plugins/marketplaces/ | This skill should be used when the user asks to "create a hook", "add a PreToolUse/PostToolUse/Stop hook", "validate... | Use when the matching workflow is requested | Skill: hook-development |
| imessage | ~/.claude/plugins/marketplaces/ | iMessage | Use when the matching workflow is requested | Skill: imessage |
| jdtls-lsp | ~/.claude/plugins/marketplaces/ | jdtls-lsp | Use when the matching workflow is requested | Skill: jdtls-lsp |
| kotlin-lsp | ~/.claude/plugins/marketplaces/ | Kotlin language server for Claude Code, providing code intelligence, refactoring, and analysis. | Use when the matching workflow is requested | Skill: kotlin-lsp |
| learning-output-style | ~/.claude/plugins/marketplaces/ | Learning Style Plugin | Use when the matching workflow is requested | Skill: learning-output-style |
| lua-lsp | ~/.claude/plugins/marketplaces/ | lua-lsp | Use when the matching workflow is requested | Skill: lua-lsp |
| math-olympiad | ~/.claude/plugins/marketplaces/ | Solve competition math problems (IMO, Putnam, USAMO, AIME) with adversarial | Use when the matching workflow is requested | Skill: math-olympiad |
| mcp-integration | ~/.claude/plugins/marketplaces/ | This skill should be used when the user asks to "add MCP server", "integrate MCP", "configure MCP in plugin", "use .m... | Use when the matching workflow is requested | Skill: mcp-integration |
| mcp-server-dev | ~/.claude/plugins/marketplaces/ | mcp-server-dev | Use when the matching workflow is requested | Skill: mcp-server-dev |
| php-lsp | ~/.claude/plugins/marketplaces/ | php-lsp | Use when the matching workflow is requested | Skill: php-lsp |
| playground | ~/.claude/plugins/marketplaces/ | Creates interactive HTML playgrounds — self-contained single-file explorers that let users configure something visual... | Use when the matching workflow is requested | Skill: playground |
| plugin-dev | ~/.claude/plugins/marketplaces/ | Plugin Development Toolkit | Use when the matching workflow is requested | Skill: plugin-dev |
| plugin-settings | ~/.claude/plugins/marketplaces/ | This skill should be used when the user asks about "plugin settings", "store plugin configuration", "user-configurabl... | Use when the matching workflow is requested | Skill: plugin-settings |
| plugin-structure | ~/.claude/plugins/marketplaces/ | This skill should be used when the user asks to "create a plugin", "scaffold a plugin", "understand plugin structure"... | Use when the matching workflow is requested | Skill: plugin-structure |
| pr-review-toolkit | ~/.claude/plugins/marketplaces/ | PR Review Toolkit | Use when the matching workflow is requested | Skill: pr-review-toolkit |
| pyright-lsp | ~/.claude/plugins/marketplaces/ | pyright-lsp | Use when the matching workflow is requested | Skill: pyright-lsp |
| ralph-loop | ~/.claude/plugins/marketplaces/ | Ralph Loop Plugin | Use when the matching workflow is requested | Skill: ralph-loop |
| ruby-lsp | ~/.claude/plugins/marketplaces/ | ruby-lsp | Use when the matching workflow is requested | Skill: ruby-lsp |
| rust-analyzer-lsp | ~/.claude/plugins/marketplaces/ | rust-analyzer-lsp | Use when the matching workflow is requested | Skill: rust-analyzer-lsp |
| scripts | ~/.claude/plugins/marketplaces/ | Hook Development Utility Scripts | Use when the matching workflow is requested | Skill: scripts |
| session-report | ~/.claude/plugins/marketplaces/ | Generate an explorable HTML report of Claude Code session usage (tokens, cache, subagents, skills, expensive prompts)... | Use when the matching workflow is requested | Skill: session-report |
| skill-creator | ~/.claude/plugins/marketplaces/ | Create new skills, modify and improve existing skills, and measure skill performance. Use when users want to create a... | Use when the matching workflow is requested | Skill: skill-creator |
| skill-development | ~/.claude/plugins/marketplaces/ | This skill should be used when the user wants to "create a skill", "add a skill to plugin", "write a new skill", "imp... | Use when the matching workflow is requested | Skill: skill-development |
| skill-name | ~/.claude/plugins/marketplaces/ | Trigger conditions for this skill | Use when the matching workflow is requested | Skill: skill-name |
| swift-lsp | ~/.claude/plugins/marketplaces/ | swift-lsp | Use when the matching workflow is requested | Skill: swift-lsp |
| telegram | ~/.claude/plugins/marketplaces/ | Telegram | Use when the matching workflow is requested | Skill: telegram |
| typescript-lsp | ~/.claude/plugins/marketplaces/ | typescript-lsp | Use when the matching workflow is requested | Skill: typescript-lsp |
| writing-hookify-rules | ~/.claude/plugins/marketplaces/ | This skill should be used when the user asks to "create a hookify rule", "write a hook rule", "configure hookify", "a... | Use when the matching workflow is requested | Skill: writing-hookify-rules |
| ATTRIBUTION | core/references/superpowers-borrowed/ | Attribution | Planner or specialist needs a borrowed engineering practice | Skill: ATTRIBUTION |
| brainstorming | core/references/superpowers-borrowed/ | You MUST use this before any creative work - creating features, building components, adding functionality, or modifyi... | Planner or specialist needs a borrowed engineering practice | Skill: brainstorming |
| executing-plans | core/references/superpowers-borrowed/ | Use when you have a written implementation plan to execute in a separate session with review checkpoints | Planner or specialist needs a borrowed engineering practice | Skill: executing-plans |
| finishing-a-development-branch | core/references/superpowers-borrowed/ | Use when implementation is complete, all tests pass, and you need to decide how to integrate the work - guides comple... | Planner or specialist needs a borrowed engineering practice | Skill: finishing-a-development-branch |
| receiving-code-review | core/references/superpowers-borrowed/ | Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear or tec... | Planner or specialist needs a borrowed engineering practice | Skill: receiving-code-review |
| requesting-code-review | core/references/superpowers-borrowed/ | Use when completing tasks, implementing major features, or before merging to verify work meets requirements | Planner or specialist needs a borrowed engineering practice | Skill: requesting-code-review |
| subagent-driven-development | core/references/superpowers-borrowed/ | Use when executing implementation plans with independent tasks in the current session | Planner or specialist needs a borrowed engineering practice | Skill: subagent-driven-development |
| systematic-debugging | core/references/superpowers-borrowed/ | Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes | Planner or specialist needs a borrowed engineering practice | Skill: systematic-debugging |
| test-driven-development | core/references/superpowers-borrowed/ | Use when implementing any feature or bugfix, before writing implementation code | Planner or specialist needs a borrowed engineering practice | Skill: test-driven-development |
| verification-before-completion | core/references/superpowers-borrowed/ | Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires running ver... | Planner or specialist needs a borrowed engineering practice | Skill: verification-before-completion |
| writing-plans | core/references/superpowers-borrowed/ | Use when you have a spec or requirements for a multi-step task, before touching code | Planner or specialist needs a borrowed engineering practice | Skill: writing-plans |
