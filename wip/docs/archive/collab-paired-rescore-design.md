# Collab 初始 Patch 配对实验:离线重打分设计

状态:superseded——已并入
[collab-paired-checkpoint-verification-design.md](../collab-paired-checkpoint-verification-design.md),
以该文档为唯一权威设计。本文仅作历史记录保留。

确认日期:2026-08-07。归档日期:2026-08-07。

## 背景

结果报告
[collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833](../results/collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833.md)
的建议第 7 条指出:要判断 reviewer 是否提升 verifier 分数,不应继续比较独立随机 job,
而应对同一初始 patch 构造 no-review 与 review-loop 的配对对比,并记录每轮 revision 后的 verifier delta。

关键事实:collab runtime 已经把每轮 review 前的 patch 快照落盘在 trial 目录中——

- `rounds/01-review/patch.diff` 是 review 介入前的初始 patch;
- `rounds/03-review/patch.diff`、`rounds/05-review/patch.diff` 是各轮 revision 后的快照;
- `final/patch.diff`(= `artifacts/model.patch`)是 review-loop 终稿,已由 Pier verifier 评分。

而 verifier 是 `model.patch` 单文件的纯函数(独立容器、只消费该 diff、产出 `reward.json`)。
因此**配对实验不需要 fork 机制、不需要 replay engine、不需要修改主管线**:
对已有 trial 的 round-0 patch 离线跑 verifier 即得 no-review 臂,已记录的最终 reward 即 review 臂,
两臂天然共享同一初始 patch。

## 实验定义

实验单位是一个成功产生初始 patch 的 collab trial。Estimand:

```text
no-review score   = V(round-0 patch)
review-loop score = V(final patch)          # Pier 已评
paired delta      = V(final) - V(round-0)
round delta[r]    = V(round-r 快照) - V(上一快照)
```

即「review-loop(含其触发的 revision)相对于同一初始 patch 直接提交,对正式 verifier reward 的边际改变」。
这不是 collab 与 standalone 的端到端对比,也不声称与"把相同预算继续给 modifier"计算公平。

## 指标与分析口径

- **主指标**:trial 级二元 reward 的配对差。
- **次要诊断**:F2P / P2P 通过节点数的每轮变化;特别记录「review 后变差」(1→0 或节点数下降)的方向。
- **盲测**:所有补充 verifier 均在 trial 结束后离线运行,reward / 日志永不进入 agent prompt,
  不驱动任何后续 revision。
- **计分策略**:intention-to-treat 为主口径——无论编排结局(approved / max_reviews_reached /
  degraded),终稿就是 review 臂的结果;编排异常对单列附表,不剔除(剔除与任务难度相关,会引入偏倚)。
- **统计呈现**:McNemar(或精确二项 sign test)作用于配对二元结果;核心呈现是不一致对 2×2 表
  ——「review 修好(0→1)」与「review 修坏(1→0)」的对数及任务清单;每轮 delta 用
  round 0→1→2→3 的 reward / 节点数轨迹表呈现,不做过度检验。
- 注意:首轮直接 approve、零 revision 的 trial,其配对 delta 恒为 0;不一致对只能来自
  发生过 revision 的 trial,评估检验力时以后者为有效样本。

## 阶段计划

- **Phase 0(回溯,零模型成本)**:只对 `collab-codex-opencode-…-224833` 跑重打分。
  24 个 trial 全部具备 `rounds/01-review/patch.diff`,得 24 对;其中 9 个首轮 approve
  (delta 恒 0),15 个有 1–3 轮 revision。
- **Phase 1(前瞻)**:照常跑新 collab job——主管线零改动,round patch 本来就会落盘——
  然后对新 job 目录跑同一个重打分命令。先 smoke test,再边观察边按情况扩大样本量;
  样本量不预设。

## 非目标

- 不做 replay engine / initial-patch 注入;不支持从同一 patch 分叉多个 reviewer 变体。
- 不为上述扩展性预留复杂度。
- 不把重打分集成进 `eval` 主流程;`eval` 行为完全不变。
- 不加入与 review-loop 等预算的 modifier-only continuation 第三支。
- 不让 agent 根据 verifier 反馈继续修复。
- 不预设正式实验的任务规模与统计功效。
- 不回溯 224833 以外的旧 job(旧 runtime 有已知故障,无信息量)。

## 实现方案

### `rescore` 子命令

在 `wip/agent_eval/cli.py` 注册,经 `scripts/run_agent_eval.py` 入口调用:

```bash
uv run python scripts/run_agent_eval.py rescore \
  --job-dir jobs/collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833 \
  [--trial <glob>] [--concurrency 2] [--force]
```

- `--trial <glob>`:只处理匹配的 trial 目录,用于 smoke test。
- `--concurrency`:verifier 容器并发数,默认 2(与 `--n-concurrent` 惯例一致)。
- `--force`:重跑已有结果;默认幂等——已存在 `verifier-replay/round-NN/reward.json`
  的 patch 跳过,中断后可续跑,Phase 1 增量样本直接重入。

### 打分核心

编程复用 pier 内部件(以 uv tool 安装的 `datacurve-pier==0.3.0`,版本锁定):

- 用 `EnvironmentFactory` 创建 separate verifier 容器(build context = 任务 `tests/`
  目录,FROM 锁定的任务镜像);
- 投入待评 patch 为 `artifacts/model.patch`;
- 用 `Verifier.verify()` 执行 `test.sh` → `grader.py`,收 `reward.json`;
- 沿用原 task 的 verifier 配置与 timeout。

不手写 docker 复刻(有与真 verifier 分叉的风险),不造 apply-patch 替身 agent
(每 patch 需完整 agent 容器,笨重)。私有 API 风险由版本锁定与下述一致性检验兜底。

### 输入枚举与去重

- 每个 trial 收集 `rounds/*-review/patch.diff` 与 `final/patch.diff`;
- 按 diff 文本 SHA-256 去重,相同内容只打一次分,汇总中记录映射
  (首轮 approve 的 trial final == round-0,可省近半 verifier 运行);
- 打分成本约 1.5 分钟/patch。

### 一致性检验(保真度兜底)

对每个 trial 的 final patch 重打分,与 `result.json` 已记录 reward 逐 trial 对比:

- 全部一致 ⇒ 证明脚手架与真 verifier 等价,同时量化 verifier 可复现性;
- 出现不一致 ⇒ 只如实列入差异报告,不自动重试(必要时手动复跑判断 flake);
  若不一致率非零,再讨论是否为主分析加多次打分机制,先不预建。

### 产物布局

```text
jobs/<job-name>/
├── rescore-summary.json
├── rescore-summary.csv        # task, trial, round, patch sha, reward,
│                              # f2p/p2p 通过数, 与记录值是否一致, 去重映射
└── <task>__<trial-id>/
    └── verifier-replay/
        ├── round-01/reward.json
        ├── round-03/reward.json
        └── final/reward.json
```

全部留在 gitignored 的 `jobs/` 内,不提交。分析文档照惯例手写进
`wip/docs/results/`,相对链接引用上述工件。

## 实施顺序

1. 实现 `rescore` 子命令(枚举、去重、pier verifier 调用、幂等、汇总)。
2. 用 `--trial` 对单个 trial smoke test(建议选有 3 轮 revision 的
   `tomlkit-toml-table-converters__Yoaiwcp`)。
3. 全量跑 224833,先核对 final patch 一致性检验结果。
4. 产出配对分析:`rescore-summary.csv` + 手写 `wip/docs/results/*.md`
   (不一致对表、每轮轨迹表、异常附表)。
5. 视 Phase 0 方向决定 Phase 1 新 collab job 的规模,逐步扩样本。

## 已确认的关键决策

- 问题锁定为「review-loop 对同一初始 patch 的边际价值」,配对来自同一 trial 的
  round-0 快照与终稿,不重新生成初始 patch。
- 主指标 = 正式 reward 的配对差;F2P/P2P 节点 delta 仅诊断。
- Verifier 完全事后、盲测、不反馈 agent。
- 主分析 intention-to-treat;编排异常单列不剔除。
- Phase 0 只回溯 224833;Phase 1 = 正常 collab job + 同一 rescore 命令;主管线零改动。
- 不做 replay engine,不为多 reviewer 变体预留复杂度。
- 打分核心复用 pier 内部件(锁定 0.3.0),以 final patch 一致性检验证明等价。
- 相同 patch 内容按 SHA 去重;final 与记录 reward 不一致时只报告、不自动重试。
- 机器可读产物留在 job 目录内不提交;分析 md 手写进 `wip/docs/results/`。
- 样本量后置:smoke → 观察 → 逐步扩大。
