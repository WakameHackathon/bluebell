# 最小契约修订提案（未生效）

中央 Schema 和 catalog 均保持原样。本提案待接口所有者评审、版本协商及消费者迁移后才可生效。由于 v1 对象均 `additionalProperties:false`，新增字段不是向后兼容的小补丁；建议发布新的合同主版本，不能只把 v1.0.0 重标版本。

## 缺口和建议

| 缺口 | 当前约束 | 最小提议 | 消费者影响 |
|---|---|---|---|
| 被复核决定及来源/版本 | OutcomeReport 有状态/证据，无 case/reason identity | 新增 `review_target_ref`，引用不可变售后实例、记录版本和决定来源（platform/merchant） | verify、platform adapter、appeal、host 都需提供/解析 |
| 商家/平台/终局区分 | `business_result` 粗粒度；缺原决定实体 | `ReviewTarget` 含 source、decision_ref、record_revision、reason_refs、finality/evidence refs | verify 输出语义迁移； appeal 不从 merchant 回答推平台裁决 |
| 争议与证据/段落映射 | grounds 是 Fact[]，草稿是一段文本 | 增 `grounds_map[]`：ground_id、claim_refs、counter_refs、draft_segment_id；draft segments 带 id/text | 所有下游展示、校验及交互执行改用段落集合 |
| 复核入口适用性/期限/可用性 | PlatformView 只有通用 controls/state/rules | `AppealRoute` 带 route_ref、scope、eligibility_state、deadline (value/source/unknown)、availability、conditions、evidence_refs | platform adapter 和 appeal 必须结构化当前路径；UI 不推断 |
| 正在处理/补充/新建 | Ledger 无申诉实体或 operation subtype | `appeal_case_ref` + `submission_intent` (`new|supplement_existing`) + `existing_case_state`，平台记录回连 ledger | host 按 case/intent 去重；verify 读申诉记录 |
| 草稿核对和失效 | EvidenceBundle 有单一材料 review 字段，无 appeal content binding | 独立不可变 `AppealReviewReceipt`：task/target/draft revision、内容摘要、file refs+digest、route ref、用户事件/time | host 在内容或材料变化时撤销旧核对； interact 校验摘要 |
| 无材料 vs 缺材料 | `evidence` 必填且只能引用完整 EvidenceBundle 结构；没有 explicit empty state | 将 evidence ref 改为 nullable，或定义合法空包 `state:no_materials|available`、检查数组及 file refs | appeal 消费者支持空输入且不假报完备；主 Agent 允许只凭处理记录分析 |
| prepare vs 可进入提交准备 | recommendation 只有 `prepare`，无机器条件 | 保留 recommendation 建议，另加只由宿主计算的 `submission_readiness` 状态与 unmet conditions；Skill 不得自报 ready | host 承担条件计算；interact 仅读取可信 gate |
| 未知结果阻重复 | ledger generic events, no business effect state/case | 在 Ledger operation 增 `business_effect_key`、intent/case ref、dispatch outcome (`not_sent|sent|unknown|verified`)、idempotency key | verify、interact、resume、appeal 共同执行持久去重锁 |
| 草稿核对已变更 | 现 v1 无绑定 | ReviewReceipt 绑定内容/文件摘要和 revision；新版本须新确认 | interact/host reject stale receipt |

## 空 EvidenceBundle 判定

现 Schema 对 `EvidenceBundle` 的数组允许空，但这只意味着结构可以容纳空数组，不定义该 bundle 表示“没有材料”“材料尚未查验”还是“全部不需要”。且 request 的 EvidenceBundle 引用本身必填，宿主必须已有真实登记 artifact。不能因为数组 technically 可空就伪造一个“空 EvidenceBundle”。首选最小安全变更是 `evidence` nullable 并明确 null=本轮没有可用材料产物；若宿主更需统一引用，定义带 `state` 的正式空包。均属提案。

## 正反样例（语义，不是 v1 消息）

**接受：** `review_target_ref` 指向当前任务平台拒绝记录版本 4；商家另有不同回复且独立列示。两个 grounds 分别引用平台理由和用户陈述来源；route 显示当前可用、条件已观察，未声称未知期限。用户核对回执绑定 draft rev 3 与两份文件字节摘要。ledger 显示已有 appeal case 正在处理时，decision 为 stop/补充现案候选，host 锁禁止新建。

**拒绝：** 以商家说“不退”为平台最终裁决；从裂纹照片推断商家责任；引用另一个 task 的文件；将找不到按钮写成永久无权；deadline 空白时自行填固定天数；把用户核对当发送授权；用新 call_id 或改措辞绕过未知发送锁；将模型输出的 `ready=true` 作为执行门禁。
