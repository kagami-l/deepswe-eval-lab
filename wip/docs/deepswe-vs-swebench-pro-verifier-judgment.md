# DeepSWE 与 SWE-bench Pro verifier 判断能力核查

核查日期：2026-07-29

## 结论

DeepSWE 并不是因为“注入了事先准备的 `test.patch`”就天然比 SWE-bench Pro 更能判断正确实现。两者的最终判分本质上都是行为测试：把候选 patch 放进固定版本的仓库，运行指定测试，要求 F2P（原本失败、修复后应通过）与 P2P（原本通过、修复后仍应通过）测试通过。两者都不会在评分时把候选 patch 与 reference/gold patch 做文本、AST 或代码结构比对。

DeepSWE 所说的优势，准确地讲是 **test oracle 的设计目标、来源和 QA 更适合充当开放实现空间中的任务判定器**：

- DeepSWE 的隐藏测试从任务描述出发专门编写，官方要求通过 public API 和 observable output 断言行为，避免依赖私有 helper、内部状态或 reference solution 的结构。
- SWE-bench Pro 的测试主要继承历史合并 PR 的测试。这些测试适合验证当时那个 PR，却不一定是为“未来任意候选实现”设计的完整任务规格，因此可能过窄、过宽或带有实现耦合。
- DeepSWE 还通过 prompt-verifier bijection、acceptance breadth、多种 agent rollout、人审、重复运行排查 flaky test 和回归测试来降低误判。

所以应把官方表述理解为：DeepSWE **有意让测试的接受集合更接近任务的行为规格**，而不是“有限测试可以证明任意程序完全正确”。

## `test.patch` 到底代表什么

`test.patch` 只是把隐藏的可执行 oracle 安装到待测仓库。它可以写成两种完全不同的风格：

```text
实现耦合测试：断言必须存在 _new_helper，或某内部方法恰好调用 2 次
行为测试：通过 public API 给定输入，检查输出、异常和外部可观察状态
```

前一种测试会拒绝“内联同样逻辑”或“采用不同模块划分”的正确实现；后一种测试则可以让不同内部实现得到同样的通过结果。因此，是否注入 patch 不决定 verifier 是否 implementation-agnostic，**patch 内断言了什么**才决定。

可以把 verifier 的接受集合写成：

```text
A = { candidate patch | 所有指定行为测试与回归测试通过 }
```

理想情况是 `A` 接近“满足 prompt 行为规格的所有实现”。有限测试不可能证明两者完全相等；测试遗漏会让 `A` 过宽并产生 false positive，测试额外要求或实现耦合会让 `A` 过窄并产生 false negative。

## 两边相同与不同之处

| 维度 | SWE-bench Pro | DeepSWE | 对“判断正确实现”的意义 |
|---|---|---|---|
| 最终判分 | 要求 F2P 与 P2P 测试进入 passed set | 要求 F2P 与 P2P 节点全部通过 | 原理相同，都是测试 oracle，而不是 reference patch 相似度 |
| reference solution | gold patch 用于构建/验证任务，不作为候选 patch 的相似度评分项 | reference solution 用于任务审查，官方明确称不在 grading 时使用 | 两者原则上都可以接受 alternative implementation |
| 测试来源 | 历史 PR/commit 所带的测试及选定回归测试 | 从 task prompt 出发专门编写新 verifier | 这是 DeepSWE 的核心差异主张 |
| 断言对象 | 历史测试可能依赖该 PR 新增的私有符号、fixture 或结构 | 官方规范要求 public API 与 observable output | 降低“实现正确但形状不同”导致的 false negative |
| 覆盖目标 | 原 PR 测试未必覆盖 prompt 对任意未来提交的完整要求 | 要求 prompt-verifier bijection：no more, no less | 同时降低覆盖不足的 false positive 与过度约束的 false negative |
| 验证 QA | 依赖数据构建与已有测试 | 多配置 rollout、LLM 辅助分析、独立人审、near-correct failure 复核、三次运行排查 flaky | 提供比单个 reference solution 通过更强的经验校验 |
| v1.1 执行隔离 | 不是本次主张的关键 | agent 环境与 verifier 环境隔离，missing/skipped 等严格失败 | 改善可重复性和防篡改；不直接证明语义覆盖更完整 |

SWE-bench Pro 的公开 evaluator 最后取得 `PASSED` 测试名集合，然后计算：

```python
result = (f2p | p2p) <= passed_tests
```

这说明它的最终判分同样是测试通过关系，而不是 gold patch 形状匹配。参见 [SWE-bench Pro evaluator](https://github.com/scaleapi/SWE-bench_Pro-os/blob/main/swe_bench_pro_eval.py)。

DeepSWE v1.1 的 grader 也基于配置中的 F2P/P2P 测试节点判定；所有目标节点通过才给 task reward 1。reference solution 会用于任务制作时的 oracle 验证，但不参与候选提交的运行时相似度比较。参见 [DeepSWE 仓库](https://github.com/datacurve-ai/deep-swe) 与官方的 [Task construction / Quality Assurance](https://deepswe.datacurve.ai/blog/deepswe#task-construction)。

## 官方如何支持“更好”的主张

### 1. 构造原则

官方说明 verifier 从 task description 出发专门编写，并通过 public API 和 observable output 断言；内部 helper 重写、新增模块或扩展已有 class 都应被同等接受，只要外部行为满足要求。还要求：

- prompt-verifier bijection：测试恰好覆盖 prompt 要求，不多不少；
- acceptance breadth：接受合理的不同模块边界、helper 名称与控制流；
- 每个 verifier 在制作时重复运行三次以排查 flaky；
- 每次正式评测也运行选定的既有测试和新增回归测试；
- 多个 frontier agent configuration 试做任务，并检查通过样本是否真阳性、失败样本是否因能力问题，利用 near-correct failure 修订 verifier。

来源：[DeepSWE official blog — Methodology](https://deepswe.datacurve.ai/blog/deepswe#methodology)。

### 2. 官方给出的 SWE-bench Pro 误判案例形状

官方审计列出的差异恰好说明了“测试内容”而非“注入机制”的影响：

- 历史 gold test 只覆盖 PR 当时需要的路径，stub/no-op 实现可能碰巧通过，形成 false positive；
- gold test import 了 PR 新增但 prompt 未要求的 private helper，行为正确但内联实现会编译失败，形成 false negative；
- 只恢复测试文件却缺少同一 commit 中的 fixture，正确候选也会失败；
- verifier 纳入与请求无关的测试并对输出快照过度敏感，可能拒绝合理改动。

这些是 DeepSWE 官方对其抽样数据的归因，参见 [SWE-bench Pro failure patterns](https://deepswe.datacurve.ai/blog/deepswe#swe-bench-pro-patterns)。它们不是“所有 SWE-bench Pro 任务都有问题”的证明。

### 3. 官方经验审计

DeepSWE 从两个 benchmark 各随机取 30 个 task，对多个 frontier config 各跑多次，再让一个 LLM analyzer 查看 task、trajectory、patch、reference solution 和 verifier output，独立判断候选是否真正满足行为。官方报告：

| 指标 | SWE-bench Pro | DeepSWE |
|---|---:|---:|
| false positive | 8.5% | 0.3% |
| false negative | 24.0% | 1.1% |
| analyzer 与 verifier 总体不一致 | 32% | 1.4% |

样本量为 735 个 DeepSWE rollout、789 个 SWE-bench Pro rollout（排除 API error、timeout 等瞬态 harness failure）。来源：[DeepSWE official verifier audit](https://deepswe.datacurve.ai/blog/deepswe#cleaner-verifier-judgments)。

## 证据的边界

上述审计是对“DeepSWE 的 verifier 更接近任务成功”的经验支持，但不是严格证明：

- 独立 verdict 仍由 LLM analyzer 给出，不是形式化规格或全量人工裁决；官方自己也提醒部分 verdict 会错。
- 只抽样 30 个 task/benchmark；可观察到主要模式，但不应把小比例差异当作精确总体估计。
- analyzer 看到 reference solution，可能有 reference-shape anchoring 风险；它虽然能识别 alternative implementation，但仍不是无偏 ground truth。
- 有限测试永远存在未覆盖输入，`will accept any solution` 应读作设计目标和已审查的接受广度，而非对所有可能正确实现的数学保证。
- DeepSWE 的原创新任务、浅克隆和 verifier 隔离会减少答案泄漏、测试篡改及环境污染，但这些属于 contamination/security/reproducibility 优势，不能与行为测试的语义充分性混为一谈。

## 对后续小规模 agent 实验的建议

把 DeepSWE 的 `reward=1/0` 当作首要自动指标是合理的，但在比较差异较小的 agent 时，建议对以下 trial 做人工复核：

1. 两个 agent 在同一 task 上结果不一致；
2. F2P 只差少数节点或只因 fixture、timeout、missing/skipped 失败；
3. patch 行为看似正确但 verifier 报接口/结构相关错误；
4. verifier 通过但 patch 明显存在未覆盖分支、stub 或 no-op；
5. collab agent 改动更广，P2P 回归失败但核心 F2P 全过。

可记录 `verifier verdict` 与 `reviewed verdict` 两列，并把差异分成 `TEST_MISMATCH`、`TEST_BROKEN`、`REGRESSION`、`MISSED_REQUIREMENT`、`HARNESS_ERROR`。这样既利用 DeepSWE 更严格的自动 verifier，也不会把任何有限测试套件误当成绝对真值。

## 一句话总结

**DeepSWE 与 SWE-bench Pro 都靠隐藏测试判分；DeepSWE 声称更可靠的根据，不是它用了 `test.patch`，而是它把 test patch 当作从 prompt 专门设计并经过 acceptance-breadth QA 的行为规格，而 SWE-bench Pro 的测试通常是从历史 PR 继承来的验证素材。官方抽样审计支持这一主张，但仍应视作有局限的经验性证据。**
