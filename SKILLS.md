# Skill 清单与调用链

Skill 包以文件夹形式放在 [`skills/`](skills/) 下（共 11 个，117 个文件），
注册信息在 [`skill-catalog.json`](skill-catalog.json)，契约在 [`contracts.schema.json`](contracts.schema.json)。

## 11 个已交付的 Skill

| Skill | 版本 | 输出产物 (`output_kind`) | 需要的输入（全部是已登记产物的引用） |
| --- | --- | --- | --- |
| `aftercare-intake` | 1.2.0 | `TaskIntent` | `user_turn` |
| `aftercare-order` | 1.0.0 | `OrderSelection` | `intent`, `platform_view`, `user_decision`? |
| `aftercare-remedy` | 1.0.0 | `RemedyPlan` | `intent`, `order`, `platform_view`, `user_decision`? |
| `aftercare-evidence` | 1.0.0 | `EvidenceBundle` | `remedy`, `platform_view`, `approved_file_refs`, `user_turn`? |
| `aftercare-interact` | 1.0.0 | `InteractionPlan` | `goal_step`, `platform_view`, `source_artifacts` |
| `aftercare-verify` | 1.0.0 | `OutcomeReport` | `platform_view`, `receipt`?, `ledger` |
| `aftercare-recover` | 1.0.0 | `RecoveryPlan` | `failure`, `platform_view`, `ledger`, `outcome`? |
| `aftercare-resume` | 1.0.0 | `ResumePlan` | `saved_task`, `platform_view`, `current_outcome`, `ledger` |
| `aftercare-logistics` | 1.0.0 | `LogisticsPlan` | `order`, `remedy`, `outcome`, `platform_view`, `user_decision`? |
| `aftercare-appeal` | 1.0.0 | `AppealDraft` | `outcome`, `platform_view`, `evidence`, `ledger` |
| `aftercare-handoff` | 1.0.0 | `HandoffDraft` | `outcome`, `ledger`, `platform_view`, `evidence`? |

`?` 表示该输入在契约里可空。除 `aftercare-interact.goal_step`（`Step`，契约中无 `$defs`，
以字面对象传递）外，所有输入都是 `{artifact_id, kind, revision}` 形式的引用。

## 未交付的 3 个 Skill

`platform-main`、`platform-secondary`、`platform-sandbox` 在 catalog 里声明，输出 `PlatformView`，
但上游从未交付对应包（GitHub 上不存在对应仓库），因此 `implemented: false`，运行时 `skills_loaded`
只报 11。`PlatformView` 是 11 个 Skill 中 10 个的必需输入，**这条缺口是链路最硬的一处断点**。

为了让本地链路可跑，宿主在 `skill_runtime.sandbox_platform_view()` 里以「沙箱适配器」临时顶替：
把用户粘贴的页面文字包成一个 `PlatformView`，`environment: "sandbox"`，
`state_facts[0].certainty: "user_reported"`。这不是已实现的 Skill，也不代表平台已核验，
只是把「用户自己贴的文字」如实标注后送进链路。

## 典型顺序

```
intake ──> order ──> remedy ──> evidence ──> interact ──> verify ──┬─> logistics
                                                                   ├─> appeal ──> handoff
                                                                   └─> recover ──> interact
```

`aftercare-resume` 独立于这条主线，用于用户回来继续旧任务。

## 链路实际能走到哪一步

**能用的部分（已实现并测试）**：请求按契约组装、引用必须已登记、结果信封与 `data` 都按契约校验、
通过校验的产物落库并可供下游引用。

**走不通的部分（上游设计使然，不是本项目偷懒）**：

1. **没有 `PlatformView` 的生产者。** 3 个平台适配器未交付。当前只能靠用户粘贴页面文字，
   由宿主标注为 `user_reported` 后顶替。
2. **每一步都是声明式终点。** 没有任何 Skill 会点按钮、提交、上传或发送。
   只有 `aftercare-interact` 能产出动作提案，而且它自己也不执行。
3. **执行与授权层不存在。** `OperationLedger`、`ExecutionReceipt`、`FailureEvent`、
   `UserDecision`、`UserTurn`、`TaskSnapshot` 这些宿主侧输入没有生产者；
   本项目只提供 `/api/artifacts` 让你登记，`TaskSnapshot` 与 `UserTurn` 由宿主在每次调用时构造。
4. **v1 契约下 intake 拿不到 `completed`。** v1 的 `UserDecision` 只能表达
   `select_item/choose_option/confirm_fact/review_material`，无法表达「整体诉求已确认」，
   而 `TaskIntent` 要求 `intent_confirmation_ref`。上游 `aftercare-intake` 1.2.0 的本地 v2 契约
   （`urn:aftercare:intake-candidate:2.0.0`）补了 `source_turn_refs`/`goal_evidence_refs`/
   `intent_confirmation_ref`，但 v1 消费者会拒绝它。本项目**保留这道闸门**：
   `aftercare-intake` 在缺少宿主登记的确认记录时如实返回 `needs_user` 或 `blocked`，不伪造确认产物。

结论：这是一条**契约完整、运行时可校验**的链路，但**不是一条能替用户把事办完的运行链路**。
演示时应按此说明，不要声称已完成真实售后操作。
