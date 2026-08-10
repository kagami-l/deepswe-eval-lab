# DeepSWE v1.1 筛选数据

本目录保存用于筛选高区分度任务的官方公开数据快照，以及可复现的逐层筛选结果。

## `official-v1.1/`

下载自 DeepSWE 官网 `https://deepswe.datacurve.ai/artifacts/v1.1/`，当前快照下载于 2026-08-07，对应官方 2026-08-06 生成的数据（52 个 config、23,490 次 rollout）。官方仍在向 v1.1 追加新 config，本地快照与远端最新版的差异见下方「官方数据更新记录」。完整性校验见 `SHA256SUMS`。

| 文件 | 含义 | 是否进入主筛选 |
| --- | --- | --- |
| `tasks.json` | 113 个任务的 ID、语言、仓库、base commit、prompt 长度等元数据 | 是 |
| `trials.json` | 23,490 次 rollout 的系统配置、通过/错误、分项分数、成本、tokens、steps 和工件状态 | 是，核心输入 |
| `v1-delta.json` | 同一批共享 rollout 在 v1 和 v1.1 评分下的 task/config 差异 | 是，用于标记评分敏感题 |
| `leaderboard-live.json` | 官网 configuration 级榜单及 pass@k、置信区间、成本等汇总 | 否，用于交叉核验 |
| `release.json` | trajectory、patch、agent log、verifier 输出的公开下载 URL 模板 | 否，用于后续人工审计 |

主筛选只使用 `source=deep-swe`、`eval_scope=full`、`included_in_score=true` 且 `errored=false` 的 trial。被排除 trial 不进入通过率分母，但会进入错误率和 verifier timeout 统计。

### 官方数据更新记录

官方对 v1.1 的每次更新都只追加新 config 的 rollout，已有 rollout 与指标从未被改动；实际变动的文件只有 `trials.json` 和 `leaderboard-live.json`（`tasks.json`、`v1-delta.json`、`release.json` 自 2026-07-25 起未变）。

| 官方生成时间 | configs | rollouts | 变化 | 本地快照 |
| --- | --- | --- | --- | --- |
| 2026-07-25 | 50 | 22,586 | 初始下载版本 | 已被替换 |
| 2026-08-06 | 52 | 23,490 | 新增 `mini_swe_agent_deepseek_v4_flash_max`、`mini_swe_agent_qwen3_8_max_xhigh` | **当前快照** |
| 2026-08-07 | 53 | 23,942 | 新增 `mini_swe_agent_muse_spark_1_2_xhigh`（muse-spark-1.2，xhigh，pass@1 ≈ 0.549） | 暂未更新（2026-08-08 核对，近期对比不涉及该模型） |

后续更新参考：

- 检查远端是否有新版本，无需下载大文件：`curl -sI https://deepswe.datacurve.ai/artifacts/v1.1/trials.json` 看 `last-modified`/`content-length`，或将各文件的 `etag` 与本地 `md5 -q <file>` 对比（S3 单段上传的 etag 即内容 md5）；具体新增了哪些 config 可只下载 66KB 的 `leaderboard-live.json` 与本地 diff。
- `trials.json` 的 rows 按 task 分组存储，新 config 的行穿插在全文件各处，无法用 Range 请求做增量下载，更新必须重下完整文件（约 39MB）。
- 更新流程：替换 `official-v1.1/` 下变动的文件 → 重新生成 `SHA256SUMS` → 重跑 `official_trials_to_pier_jobs.py`（可用 `--config` 只转换新增 config，追加进 `official-v1.1-jobs/`，不必 `--clean` 全量重建）→ 同步本表和文中的 config/rollout 数字。

### 用 pier view 查看官方数据

`wip/scripts/official_trials_to_pier_jobs.py` 把 `trials.json` 按 config（harness + model + reasoning effort）展开成 pier 兼容的 jobs 目录 `official-v1.1-jobs/`（每个 config 一个 job，每个 trial 一个 `result.json`，只含指标数据，不含 trajectory 等工件），可在本地 viewer 中多选 config 做 heatmap 对比：

```bash
cd wip

# 转换（--config 可用 glob 只转换部分 config，重跑加 --clean）
uv run python scripts/official_trials_to_pier_jobs.py --clean

# 查看
uv run pier view data/official-v1.1-jobs --jobs
```

被官方排除的 trial（provider/verifier/网络错误）带有 `exception_info`，在 viewer 中勾选 "exclude errored" 后通过率口径与官方 leaderboard 一致。

## `selection/`

由 `wip/scripts/select_discriminative_tasks.py` 生成。每一层同时保存 CSV 和 JSON，后层只包含通过前层和本层条件的任务：

| 层 | 文件 | 含义 |
| --- | --- | --- |
| 00 | `00_all.*` | 全部任务及完整派生指标、各层布尔值和排除原因 |
| 01 | `01_stable.*` | 高覆盖、每 config 至少 3 个有效重复、总错误率不高于 5%、verifier timeout 不超过 1 次 |
| 02 | `02_broad_discriminative.*` | 难度 0.20–0.80，且至少 3 个低通过 base model 和 3 个高通过 base model |
| 03 | `03_core_discriminative.*` | 难度收紧到 0.30–0.70，强弱端至少 4/4，config item-rest correlation 至少 0.30 |
| 04 | `04_core_ranked.*` | 按区分度、重复稳定性和非极端难度综合排序的核心池 |
| 05 | `05_sample_dev.*`、`05_sample_confirm.*` | 两组互斥的平衡抽样，默认每组 12 题 |
| - | `manifest.json` | 输入哈希、阈值、随机种子、逐层数量和两组 task ID |

逐层结果及集合关系如下。这种表示通常可以叫“树状图”或更准确地叫“层级关系示意图”：

```text
00_all：113 题
└── 01_stable：99 题
    └── 02_broad_discriminative：51 题
        └── 03_core_discriminative：30 题
            └── 04_core_ranked：同一批 30 题，仅重新排序
                ├── 05_sample_dev：12 题（2026-08-08 起运行清单为 11 题，见「本机运行排除」）
                ├── 05_sample_confirm：12 题，与 dev 互斥
                └── 未抽入本轮样本：6 题
```

因此，`03_core_discriminative` 是 `02_broad_discriminative` 经更严格条件筛出的子集；`04_core_ranked` 与 `03_core_discriminative` 的任务集合完全相同，不是另一套独立筛选，只是按照综合分数改变行顺序。两组 `05_sample_*` 都从这 30 题中抽取，也就是同时属于 `03_core_discriminative` 和 `04_core_ranked`；confirm 在抽样时明确排除了已经进入 dev 的题。

难度条件同时检查 config 等权和 base-model 等权口径。前者更接近“模型 + effort + mini-swe-agent”这个完整系统，后者防止拥有五档 effort 的模型族在选题时获得五倍权重。

排序中的组内噪声使用 `(task, config)` 重复均值的估计方差 `p(1-p)/n`，再与 config 间方差构造 signal ratio；它只影响核心池内部优先级，不作为额外硬过滤条件。

运行：

```bash
cd wip
uv run python scripts/select_discriminative_tasks.py
```

可以用 `--sample-size`、`--seed`、`--input-dir`、`--output-dir` 调整抽样和路径。筛选脚本只依赖 Python 标准库。脚本默认校验 `SHA256SUMS` 并拒绝对意外变化的输入运行；明确要分析更新后的官网快照时，先人工核查差异，再使用 `--allow-input-hash-mismatch`。

如果待测 agent system 使用了官网公开结果中的模型，应做 leave-target-model-out，且可重复传入多个模型：

```bash
uv run python scripts/select_discriminative_tasks.py \
  --exclude-model gpt-5-5 \
  --exclude-model claude-opus-5
```

未指定 `--output-dir` 时，这类结果会自动写入独立的 `selection-leaveout-*` 目录，不覆盖全量基准结果。覆盖门槛会按剩余 base model 数同比例调整。

### 本机运行排除（2026-08-08 修订）

`05_sample_dev.txt` 自 2026-08-08 起从 12 题修订为 11 题：移除 `skrub-duration-encoding`。这是宿主机环境约束，不是任务质量问题：本机（Apple Silicon，Docker Desktop 以 Rosetta 模拟 linux/amd64）上，任务镜像内的 polars 主线 x86_64 wheel 在特定 SIMD 路径原生段错误（`import polars` 和简单整型 Series 正常，含 null/nan 的 DataFrame 构造、duration API 等路径直接崩溃），verifier 的 base/new pytest 均在收集阶段退出，历史 6 个 job 的全部 13 个 skrub trial 无一有效评分；官方 x86_64 基础设施上同任务 verifier 正常（如 `skrub-duration-encoding__vt9Upt6`：F2P 130/130）。完整证据链见 [unified-codex dev 结果分析](../docs/results/unified-codex-05_sample_dev-12-tasks-20260805-172604.md)。

要点：

- 任务定义 `tasks/skrub-duration-encoding/` 保持原样，未做任何修改；将来在 x86_64 Linux 上（或修复 polars 运行环境后，如换用 `polars-lts-cpu`，需接受 1.39.3→1.33.1 降级）可零漂移重新纳入。
- `host-excluded.txt` 是本机不可评分任务的机器可读清单，供抽样和生成 job 时机械扣除：`skrub-duration-encoding`（核心池 30 题内唯一受影响任务）和 `narwhals-rolling-window-suite`（同样依赖 polars；已在 02 层被筛除，仅在对全池重新抽样时相关）。
- 口径：此后 dev 集按 11 题报告 task coverage；与官方 v1.1 对照时，官方侧同步剔除 `skrub-duration-encoding` 或明确标注 coverage。历史 job 无需重算——其有效口径本来就是 11 题（所有本地 skrub trial 均为 verifier-invalid）。
- 重新运行 `select_discriminative_tasks.py` 会按原逻辑重新生成 `05_sample_*.txt`（可能重新包含 skrub）；重跑后需对照 `host-excluded.txt` 重新应用本排除。
- `05_sample_dev.csv`（脚本原始输出）与 `04_core.txt`（核心池 30 题）保持不变：排除只作用于运行清单，不改写筛选统计与池定义。

### 手工维护的子集

`selection/complementary-luna-v4flash.txt` 是为 `gpt-5-6-luna [xhigh]` 与 `deepseek-v4-flash [max]` 互补性实验单独准备的 10 题清单（前 5 题 luna 强方向、后 5 题 flash 强方向），由手工筛选维护，不由筛选脚本生成，重跑脚本也不会更新它。筛选思路、逐题依据和替补名单见 [luna/v4-flash 互补子集文档](../docs/deepswe-luna-v4flash-complementary-subset.md)。

`selection/complementary-opus-sol-xhigh.txt` 与 `selection/complementary-opus-sol-max.txt` 是为 `claude-opus-5 [high]` 分别与 `gpt-5-6-sol [xhigh]`、`[max]` 配对准备的同类 10 题清单（前 5 题 opus 强方向、后 5 题 sol 强方向，两份重叠 8 题），同为手工维护。筛选依据、替补名单及两组配对的优先级建议（推荐先做 xhigh 配对）见 [opus/sol 互补子集文档](../docs/deepswe-opus-sol-complementary-subsets.md)。

## 对后续 agent-system 评测的解释

后续把“agent 框架 + 模型”或“coder + reviewer 协作配置”作为一个整体 agent system 比较是合适的，也不改变当前的稳定性和区分度筛选主线。做整体效果排名时，不必拆解模型效应与框架效应：每个完整配置直接作为一个 treatment，在相同 task、预算、timeout 和重复次数下做配对比较即可。如果还要进一步声称“协作机制本身带来提升”，则需要增加同模型、同预算、无 reviewer 的 matched ablation，不能只比较两个整体配置。

边界是：官网公开 rollout 全部来自 `mini-swe-agent`，所以本目录的核心池只能证明这些题能够区分“固定框架下的公开模型/effort 配置”。它是其他单 agent 或 collab agent 的候选池，不是框架或协作区分度的既成证据。建议先在 `05_sample_dev` 上调试，在不改规则的前提下用 `05_sample_confirm` 做确认；每个 agent system 每题至少 4 次，并单独记录基础设施错误。
