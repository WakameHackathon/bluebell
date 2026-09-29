# 验证报告解释

`tests/synthetic-cases.json` 覆盖用户要求的 26 个合成场景。它是决策表，不是实时平台测试，也不证明大模型每次都会正确分类。`scripts/check_appeal.py` 负责检查请求/结果字段、中央枚举、Fact 形状、引用格式及在调用者提供登记集合时的引用存在性；它不实现 JSON Schema 全量验证器或 host。

需分开报告：

- **Schema 结构**：用本地派生 Schema 验证请求和结果样例；校验通过只代表结构符合 v1。
- **争议—证据关联**：本包 lint 可检查 Fact 引用是否在给定登记集合中，不能判断证据是否真实、相关或含义支持主张。
- **草稿事实一致性**：需人工/有来源见证的语义审查；关键词检查只是提示，不是事实真伪检测。
- **核对 vs 授权**：Skill 明确区分；无宿主授权服务，未做集成验证。
- **重复申诉**：有规则与 fixture；无平台申诉 ID 和持久 host 锁，未做集成验证。
- **上下游集成**：需宿主接通 verify/evidence/remedy/interact/handoff、解析引用、版本化 review receipt 及结果核对。本次无可运行 runtime。
