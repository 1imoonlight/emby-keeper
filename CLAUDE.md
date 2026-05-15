# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## 5. 项目上下文（emby-keeper）

- **定位**：Telegram emby bot 日常签到 / 保活自动化工具。Python 3.8–3.10。
- **主要包**：
  - `embykeeper/` — Python 主体。Telegram 侧分 `checkiner`（签到）、`messager`（水群）、`monitor`（监控）、`registrar`（注册）四类适配器，每类下按站点动态发现子模块。`emby/` 是 Emby 服务器 API 封装。
  - `embykeeperweb/` — Vue/Vite Web 控制台。
- **入口**：`cli.py` / `python -m embykeeper`（CLI），`web.py` / `python -m embykeeperweb`（Web）。
- **用户配置**：`config.toml`（用户自行编辑，**绝不提交**）；`config.example.toml` 由 `make config/generate` 在版本升级时自动生成，不要手工改。
- **文档**：`docs/`（VitePress），通过 `npm run docs:dev` 预览。

## 6. 开发命令（以 Makefile 为准）

- 安装开发环境：`make develop`
- 运行：`make run` / `make run/debug` / `make run/web`
- 检查：`make lint`（black + pre-commit + `npm run lint`）
- 测试：`make test`（pytest）
- 版本：`make version/patch|minor|major`（bump2version + 自动回写 `config.example.toml` + 推送）—— 不要手工编辑版本号。

## 7. 代码风格与依赖约束

- Python：**black, line-length=110**；pre-commit 钩子必须通过。
- Telegram 客户端：项目同时使用 **pyrogram** 和 **telethon**（`pyrogram.py` / `telethon.py`）。**不要再引入第三个 MTProto 客户端**，新功能优先复用现有 wrapper。
- 中文优先：日志、错误消息、README、注释均以中文为主；commit / PR 中文亦可。

## 8. 安全与隐私（签到工具，凭据敏感）

- **绝不提交**：`config.toml`、`*.session` / `*.session-journal`、API ID / API Hash、用户 token、手机号。
- 日志中不得输出完整 session 字符串、token、手机号；调试输出需脱敏。
- 新增站点适配如需 cookie / token，统一从 config 读取，不要硬编码。

## 9. 新增站点 / Bot 适配

- 按 `embykeeper/telegram/{checkiner,messager,monitor,registrar}/` 现有同类模块的结构和命名添加新文件；不要另起架构层。
- 通过基类继承 + 模块自动发现接入，不需要在中央注册表里手工登记。
- 添加前先读 2–3 个已有同类适配器，复用 OCR、cloudflare 绕过、apprise 通知等已在 `embykeeper/` 顶层提供的工具。
