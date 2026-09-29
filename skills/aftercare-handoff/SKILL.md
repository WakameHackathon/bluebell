---
name: aftercare-handoff
description: Prepare a fact-checked, privacy-minimized draft for handing an unresolved aftercare issue to a verified official platform support channel. Does not contact support, send messages, submit files, or operate pages.
metadata:
  version: 1.0.0
---

# 官方客服交接准备

仅基于宿主为当前任务提供且允许使用的记录，判断是否需要人工解释/处理，并整理可由用户核对的 `HandoffDraft`。本 Skill 不访问账户、不搜索客服联系方式、不操作页面、不联系商家或客服、不发送消息/材料，也不生成发送授权或发送状态。草稿完成、用户核对、执行层取得发送授权、消息已发送、客服已受理是不同阶段。

## 调用与决策

每次按 [当前契约](references/contract-and-boundaries.md) 读取合法请求与返回要求。宿主负责解析引用并核验任务、商品、版本、来源和权限；不可凭对话猜造引用。模式暂停、目标商品变化、引用缺失/过期或冲突时，停止旧目标的整理并返回相应状态。

先排除无需人工的情况：结果未知先交 `aftercare-verify`；可安全观察的一次页面变化先更新观察；尚未选择方案时先澄清；正常审核等待或平台明确自助补证继续原流程；一次点击失败不自动升级。多次有依据但有限的恢复仍卡住、需要平台解释/人工判断、页面明确要求人工、权限/功能不足或用户明确要求时，可准备交接。用户不想联系时尊重其选择。

只总结具体待解决问题。把用户陈述、平台显示、已核实回执、推断和未知分别标出；商家答复不是平台裁定，“待审核”不是拒绝，“草稿已完成”不是已提交或已受理。缺少精确时间、金额、原因或编号时写未确认或省略，不补猜测。用户不熟悉术语时先给短摘要，一次问一个会改变内容的问题，允许“不确定／不记得／先不联系”。

## 渠道、材料与草稿

客服入口只引用当前任务中已核实平台页面或宿主提供的可信官方渠道。区分可见入口、待用户点击确认入口、未核实转述；无法验证则 `official_channel_ref: null`，告知用户从平台 App 或自己已知的官方入口进入。搜索结果、商家私聊和可疑文件链接不作为官方证明；“联系商家”不得说成平台客服。

附件只从当前获准的 EvidenceBundle 选择，逐项确认与争议点相关、仍有效且适合客服查看。正文不放完整地址、电话、账号、证件或支付信息。无附件时 `file_refs: []` 合法。需要遮挡/派生副本时交 `aftercare-evidence`，不改证据原件；本地可读不代表获准远程发送。

输出严格符合中央 `aftercare-handoffResult` 与 `HandoffDraft`，不私自加字段；简单区分来源的文本结构参照 [事实摘要](references/fact-summary.md)。用户核对只证明其核对当前内容，不授权发送。内容、渠道、附件或关键事实改变，要求重新核对；发送授权必须由执行层在发送前绑定当前接收方、文字、附件和后果。本 Skill 不提供 `confirmation_ref`。已发送或结果未知时交 `aftercare-verify` 查记录，禁止凭旧授权重发。

## 状态

- `completed`：本轮分析/草稿准备完成，`questions` 与 `issues` 为空；不表示已核对、发送或受理。
- `needs_user`：需澄清事实、问题重点或请用户核对当前草稿，至少一个具体问题。
- `needs_observation`：需重新核对当前状态或官方入口，至少一个 issue。
- `blocked`：没有安全渠道、权限/功能不足、用户暂停或目标不一致，至少一个 issue。
- `failed`：输入引用、契约或处理异常，至少一个 issue。

典型下游：`verify/recover/appeal → handoff → 用户核对 → 执行层独立授权与 interact 单步动作 → 新观察 → verify`。用户自行复制说明也必须标明“尚未发送”。详细的衔接状态和风险测试见 [衔接样例](examples/handoff-exchanges.json)。
