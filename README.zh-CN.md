# PatchProof

**证据优先的 PR 风险审查器：离线核心零第三方依赖。**

[English](README.md) · [规则说明](docs/rules.md) · [AI 与隐私](docs/ai-and-privacy.md) · [参与贡献](CONTRIBUTING.md)

PatchProof 读取 Git unified diff，把需要关注的审查风险变成可复核的发现：稳定的规则 ID、严重度、文件与行号、有限长度的证据片段，以及明确的处理建议。它可输出适合人工阅读的 Markdown、适合自动化的 JSON，以及适合代码扫描平台的 SARIF。

默认安装没有第三方运行时依赖，不需要账号或 API Key，在本机运行且不访问网络。只有显式开启后，才会调用 OpenAI Responses API 做可选的语义增强；关闭 AI 或 API 不可用时，确定性规则仍可独立工作。

> **当前状态：** Alpha。命令行可用于评估，但在稳定版本发布前，规则与机器可读 Schema 仍可能调整。

## 适合解决什么问题

- **结论可核对：** 每条发现都尽量指向变更文件和行号，而不是只给一个不透明分数。
- **默认可复现：** 同一 diff 与同一配置会得到相同的核心判定。
- **离线、轻量：** Python 3.11+ 核心只使用标准库。
- **便于集成：** Markdown、JSON、SARIF 来自同一份报告模型。
- **CI 默认只读：** 随附的 GitHub Action 只分析已 checkout 的差异，不默认写回仓库或 PR。
- **AI 只是建议层：** AI 需要主动开启，不能改写确定性规则，也不会控制风险分数、结论或 CI 退出状态。

PatchProof 用于确定审查优先级，不能替代测试、编译器、linter、专业安全扫描、威胁建模或人工代码审查。

## 快速开始

目前请从仓库源码安装：

```bash
git clone https://github.com/BlueArt333/patchproof.git
cd patchproof
python -m pip install .
```

检查已暂存、准备提交的改动：

```bash
patchproof review --staged
```

比较当前分支与主分支：

```bash
git fetch origin main
patchproof review --base origin/main --head HEAD
```

输出 JSON 文件：

```bash
patchproof review --staged --format json --output patchproof-report.json
```

使用 `patchproof review --help` 查看完整参数，使用 `patchproof rules` 查看内置规则，或执行 `patchproof init` 生成带注释的起始配置。

## 输入与输出

`patchproof review` 每次选择一种输入方式：

```text
--base REF --head REF    比较两个 Git revision
--diff-file PATH         读取已有 unified-diff 文件
--staged                 分析 Git 暂存区
--worktree               分析未暂存的工作区变更（默认）
```

使用 `--repo PATH` 可以从另一个仓库目录执行 Git 操作并自动查找配置。

`--output -` 表示写到标准输出，也可以指定文件路径。输出格式包括：

| 格式 | 典型用途 |
| --- | --- |
| `markdown` | 终端、CI Job Summary、人工审查记录 |
| `json` | 脚本、看板或其他自动化工具 |
| `sarif` | 支持 SARIF 2.1.0 的代码扫描系统 |

失败阈值与输出格式相互独立。默认情况下，只要出现 `high` 或 `critical` 发现，审查命令就会以非零状态退出。可用 `--fail-on` 临时覆盖；若只想报告、不想卡住 CI，可配置 `fail_on = "never"`。

## 内置审查信号

| ID | 信号 |
| --- | --- |
| `PP001` | 变更文件数或行数达到或超过配置阈值 |
| `PP002` | 变更路径命中敏感区域模式 |
| `PP003` | 修改了源码，但本次 patch 没有测试文件变更 |
| `PP004` | 依赖锁文件发生变化 |
| `PP005` | 新增行疑似包含凭据或秘密 |
| `PP006` | GitHub Actions workflow 新增了过宽的写权限 |
| `PP007` | 存在文本审查器无法检查的二进制变更 |

这些都是“值得进一步确认”的信号，并不直接证明代码错误、存在漏洞或具有恶意。详细证据逻辑与局限见 [docs/rules.md](docs/rules.md)。

## 配置

PatchProof 会依次查找 `patchproof.toml`、`.patchproof.toml`，以及 `pyproject.toml` 中的 `[tool.patchproof]`。显式传入的 `--config PATH` 优先级最高。

```bash
patchproof init
```

最小配置示例：

```toml
[patchproof]
fail_on = "high"
large_pr_files = 20
large_pr_lines = 500
ignore_rules = []
```

源码、测试、敏感区域和排除路径都可以配置。建议从 [examples/patchproof.toml](examples/patchproof.toml) 开始，并谨慎使用排除项：被排除的路径不会产生任何发现。
审查不可信分支时，可用 `--no-config` 强制使用内置默认值。自动发现会读取被审 checkout 中的配置，而该配置能够改变排除项与规则抑制。


## 可选 AI 审查

安装可选依赖并通过环境变量提供凭据：

```bash
python -m pip install ".[ai]"
export OPENAI_API_KEY="..."
patchproof review --staged --ai
```

PowerShell：

```powershell
$env:OPENAI_API_KEY = "..."
patchproof review --staged --ai
```

仅仅设置 API Key 不会自动开启 AI；必须显式传入 `--ai`。模型可通过 `--model`、`PATCHPROOF_MODEL` 或 `OPENAI_MODEL` 选择，其中命令行参数优先。

在专有代码或安全敏感代码上启用前，请阅读 [AI 与隐私说明](docs/ai-and-privacy.md)。关键边界如下：

- 选中的 patch 上下文会离开本机；
- 请求会设置 `store: false`，但这不等同于“保证零保留”；
- 模型输出按不可信数据处理，只有能映射回已解析 patch 的证据才会被接受；
- AI 发现使用固定严重度，只作为建议，不能阻断 CI；
- API 调用可能产生费用，受你的 OpenAI 账户设置与当期条款约束；
- 未安装 AI 依赖、没有凭据或没有网络时，确定性审查仍然可用。

## GitHub Actions 安全边界

仓库提供默认只读的 Action 和示例 workflow。未传入 `config` 时，Action 使用内置默认值，不会从 PR checkout 自动读取配置；显式 `config` 路径应被视为受信策略输入。调用方应只授予 `contents: read`，并且不要把付费 API 凭据暴露给来自 fork 的不可信 PR。

生产环境引用第三方 Action 时，应固定到审核过的完整 commit SHA。README 中不提供虚构的版本号或 SHA；请在仓库发布后，从 GitHub 页面复制真实值。

默认路径只读取 Git 历史并生成报告，不会批准、合并、打标签、评论或修改 PR。若要开启 AI 或上传 SARIF，请结合自己的仓库权限和威胁模型单独评审。

## 如何理解结果

- `rule_id` 是稳定的配置和集成键。
- 严重度表达审查紧迫度，不等于漏洞确定性。
- 证据应能回到变更路径与行号。
- 风险分数上限为 100，只是排序辅助，不是概率、CVSS 分数或安全保证。
- 原始 diff 始终是事实来源，维护者保留最终判断。

## 开发与治理

- [CONTRIBUTING.md](CONTRIBUTING.md)：开发环境、测试、规则设计与 PR 要求
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)：Contributor Covenant 2.1
- [SECURITY.md](SECURITY.md)：私密漏洞报告与安全边界
- [ROADMAP.md](ROADMAP.md)：项目方向与明确的非目标
- [CHANGELOG.md](CHANGELOG.md)：用户可见变更

## 许可证

PatchProof 使用 [MIT License](LICENSE)。

PatchProof 是独立的开源项目，不代表 OpenAI 或 GitHub 官方，也未获得其背书。OpenAI、GitHub 及相关产品名称归各自权利人所有。
