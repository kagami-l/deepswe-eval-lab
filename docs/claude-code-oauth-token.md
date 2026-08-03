# Claude Code OAuth Token：创建与评测使用

本文记录 Docker-only 统一评测流程所需的 `CLAUDE_CODE_OAUTH_TOKEN` 创建、注入和安全
处理方式。该 token 只用于非交互 Claude Code/SDK 运行；评测流程不会复制 macOS Keychain、
宿主 `~/.claude` 行为配置、skills、hooks、MCP、memory 或 history。

## 1. 前置条件

- 已安装 Claude Code；使用 `claude --version` 确认。
- 账号具有支持 Claude Code 的订阅或组织席位。
- 若尚未登录，执行：

  ```bash
  claude auth login
  ```

可用以下命令检查当前交互登录状态：

```bash
claude auth status --text
```

## 2. 创建长期 OAuth token

执行：

```bash
claude setup-token
```

按终端和浏览器提示完成授权。命令最终打印长期 token；不要把它发送到聊天、写进命令行
参数、提交到 Git 或保存进评测 artifacts。

Anthropic 官方说明：自动化流程可以运行 `claude setup-token`，再将打印的 token 设置为
`CLAUDE_CODE_OAUTH_TOKEN`：

- <https://support.claude.com/en/articles/14128775-claude-code-on-console-to-enterprise-migration>
- <https://docs.anthropic.com/en/docs/claude-code/getting-started>

## 3. 注入当前 zsh 会话

推荐无回显粘贴，避免 token 进入 shell history：

```bash
read -r -s "CLAUDE_CODE_OAUTH_TOKEN?Paste Claude token: "
echo
export CLAUDE_CODE_OAUTH_TOKEN
```

只检查变量是否存在，不打印其值：

```bash
test -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" \
  && echo "Claude auth: ready" \
  || echo "Claude auth: missing"
```

评测时只需保持该变量存在于启动 `uv run` 的同一个 shell。`DeepSweAgent` 将其转发到 trial
进程，不把值写入 prompt、run manifest 或 artifacts。

## 4. 可选：保存在本地 `.env`

可将以下内容写入 `wip/scripts/.env`：

```dotenv
CLAUDE_CODE_OAUTH_TOKEN='replace-with-token'
```

该路径已被仓库 `.gitignore` 忽略，但仍应限制本机读取权限：

```bash
chmod 600 scripts/.env
```

统一评测 CLI 不会自动加载 `.env`。从 `wip` 目录运行评测前显式导入：

```bash
set -a
source scripts/.env
set +a
```

不要同时设置多个 Claude/Anthropic credential，避免认证优先级造成错误账号或计费来源。
若使用 Console API key 回退，应只设置 `ANTHROPIC_API_KEY`。

## 5. 运行与清理

示例：

```bash
cd /Users/kgm/Projects/merico/deep-swe/wip
uv run python scripts/run_agent_eval.py eval \
  --task-list one_task.txt \
  --agent claude \
  --max-agent-attempts 1 \
  --n-concurrent 1
```

当前 shell 不再需要 token 时清除：

```bash
unset CLAUDE_CODE_OAUTH_TOKEN
```

若怀疑 token 泄露，应停止使用并重新生成/替换，而不是继续复用旧值。

## 6. 常见问题

- `Claude auth: missing`：变量未导入当前 shell；若使用 `.env`，重新执行第 4 节的三条命令。
- `claude setup-token` 不可用：先更新 Claude Code，并确认账号订阅或组织权限。
- 交互式 `claude` 可用但评测缺少认证：交互登录可能保存在 macOS Keychain；隔离的 Docker
  trial 不继承 Keychain，必须显式提供 `CLAUDE_CODE_OAUTH_TOKEN` 或 `ANTHROPIC_API_KEY`。
- token 已设置但账号不符：检查并清除旧的 `ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN` 或
  `CLAUDE_CODE_OAUTH_TOKEN`，再只设置本次 treatment 使用的一种 credential。
