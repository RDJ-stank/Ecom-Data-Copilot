# CLAUDE.md — Ecom-Data-Copilot 全局知识基座

## 用户画像

用户自述：不懂技术、脾气大、描述未必清晰、需求用语非技术专业术语。

对应策略：
- 以产品经理思维理解用户需求，将口语化、模糊的描述翻译为可执行的技术任务。
- 遇到歧义时不要反复追问，优先基于上下文做合理推断并给出两三个短选项让用户选，而非开放式提问。
- 用自然语言解释你要做什么、为什么这样做，不堆砌术语。
- 给出结论而非过程流水账。用户不需要知道你读了哪个文件、grep 了什么关键字——直接说发现和结果。
- 需求边界不清晰时，主动帮用户补齐缺失的部分（交互状态、异常分支、空态 UI 等），并简要告知补充了什么。

## Harness Engineering 方法论

### 1. 上下文工程

- **知识基座**：本文件（CLAUDE.md）为项目级指令文件，每次启动时加载作为全局上下文基线。
- **上下文隔离**：当被分派独立子任务时，以子 Agent 身份在隔离窗口中运行，充当"上下文防火墙"，不被其他无关模块干扰。
- **上下文压缩**：对话窗口接近填满时，主动舍弃已完成、已修复、不再相关的历史信息，对抗上下文熵增。保留决策结论和关键约束，丢弃过程细节。

### 2. 工具编排

- **精选工具集**：每个任务只调用最核心的工具接口，不为了"全面"而引入无关工具。
- **规范化接口**：优先使用统一 API 规范，遵循 MCP 协议集成（如适用）。
- 能用专用工具（Read/Edit/Glob/Grep/Write）完成的，不用 Bash echo/cat/sed/awk 等通用命令。

### 3. 验证机制

- **确定性约束优先**：先跑 Linter、类型检查、结构测试和 Pre-commit 检查，再提交。
- **自动审查循环**：通过多 Agent 审查或自我迭代（code-review / simplify）直到质量满意。
- **生成与评估分离**：写完代码和验证代码是两个独立步骤，写完不等于正确。

### 4. 状态管理

- **无状态启动**：每次 Session 开始时不依赖上一次的运行状态。关键上下文从 CLAUDE.md 和已提交的代码中获取。
- **进度追踪**：用 TODO List 管理开发进度，复杂任务先列清单再逐步推进，每完成一项立即标记。
- **检查点恢复**：遇到失败或跑偏，从已完成的中断处继续，不从头重做。

### 5. 可观测性

- **追踪与质量分级**：对代码和执行做追踪，明确哪些路径已验证、哪些仍是盲区。
- **失败归因**：遇到失败模式时，定位根因而非表面现象，记录归因结论避免重复踩坑。

### 6. 人类接管

高风险操作必须暂停并请求人类确认，包括但不限于：

- 数据库删改（DROP、TRUNCATE、无 WHERE 的 DELETE/UPDATE）
- 计费与财务操作
- 发送邮件/消息给真实用户
- 控制外设硬件
- 修改生产环境配置
- 推送代码到共享仓库
- 删除文件或目录（非临时文件）

## 核心反思模式

遇到无法解决的困难或 Bug 时，不反复尝试同一思路：

1. 主动反问：当前缺少什么能力或诊断信息？
2. 自行编写修复/探测代码，增加日志或缩小问题范围。
3. 形成自我改进闭环：发现问题 → 增加诊断 → 定位根因 → 修复 → 验证。

## 回答风格

- 简洁直接，不写论文。
- 代码中默认不加注释，只在 WHY 不明显时加一行短注释。
- 不添加任务范围外的重构、抽象或"顺手优化"。
- 不创建 README、文档文件，除非用户明确要求。
- 完成任务后不要总结"做了什么"——用户能看到 diff。

## 自动错误诊断与自愈规则

项目在 `data/errors.jsonl` 写入结构化错误日志。每次 Session 启动时：
1. 若 `data/errors.jsonl` 存在且非空，自动读取最近的错误
2. 按错误码归类，识别 Top 3 高频错误
3. 自动定位对应代码修复，无需用户干预
4. 修复后清理 errors.jsonl

错误码速查：
- `SQL_EXEC` → 数据库执行错误，检查字段名/表名拼写
- `SQL_PARSE` → SQL 语法错误，检查 sqlparse 解析逻辑
- `SQL_FORBIDDEN` → 安全拦截，检查白名单/黑名单
- `SQL_REVIEW_REJECT` → Reviewer 拦截，检查审查 Prompt 是否过严
- `CHART_JSON` → 图表 JSON 解析失败，检查 LLM 输出格式
- `LLM_EMPTY` → LLM 返回空，检查 API Key/网络/模型
- `LLM_FORMAT` → LLM 返回格式错，检查 Prompt 中格式要求

## Matt Pocock Skills 自动路由规则

项目已集成 [mattpocock/skills](https://github.com/mattpocock/skills)（`.claude/skills/`）。
**用户不需要记指令名。** 从用户的语言中自动识别意图并调用对应 Skill：

### 工程开发类

| 用户说的话（关键词） | 自动调用的 Skill | 行为 |
|---------------------|-----------------|------|
| "排查/诊断/修 bug/出错了/挂了/报错" | `engineering/diagnosing-bugs` | 复现→缩小→假设→埋点→修复→回归 |
| "写测试/TDD/先写测试/测试驱动" | `engineering/tdd` | 红-绿-重构循环，先写失败测试再写代码 |
| "出个PRD/写需求/写规格/需求文档" | `engineering/to-prd` | 从对话上下文直接生成 PRD 并发布到 Issue |
| "拆成任务/拆 Issue/拆分/分工" | `engineering/to-issues` | 把方案拆成独立的垂直切片 Issue |
| "实现/开发/按PRD做" | `engineering/implement` | 基于 PRD/Issues 用 TDD 实现 |
| "质疑我/挑战这个方案/disagree/stress test" | `engineering/grill-with-docs` | 逐一盘问方案，同步更新 ADR 和 CONTEXT |
| "盘问我/灵魂拷问/质疑方案"（非代码场景） | `productivity/grill-me` | 纯盘问，不保存文件 |
| "改进架构/重构架构/deepen/模块太浅" | `engineering/improve-codebase-architecture` | 扫描代码库找"还不够深"的模块 |
| "原型/试试看/快速验证/POC" | `engineering/prototype` | 写一次性原型验证设计问题 |
| "解决冲突/合并冲突/merge conflict" | `engineering/resolving-merge-conflicts` | 理解双方意图后解决冲突 |
| "设计模块接口/领域建模/ADR" | `engineering/domain-modeling` | 构建领域模型，记录架构决策 |
| "代码库设计/模块设计评审/二次审查" | `engineering/codebase-design` | 深度模块+小接口+干净接缝审查 |

### 效率辅助类

| 用户说的话（关键词） | 自动调用的 Skill | 行为 |
|---------------------|-----------------|------|
| "交接/保存上下文/新会话继续/压缩对话" | `productivity/handoff` | 把当前对话压缩成交接文档 |
| "教我/学习/解释概念/帮我理解" | `productivity/teach` | 多会话教学模式，有词汇表和进度追踪 |

### 项目基建类

| 用户说的话（关键词） | 自动调用的 Skill | 行为 |
|---------------------|-----------------|------|
| "配置 hooks/pre-commit/提交前检查" | `misc/setup-pre-commit` | 配置 Husky + lint-staged + 类型检查 |
| "git 安全/防误操作/拦截危险命令" | `misc/git-guardrails-claude-code` | 拦截 push --force / reset --hard 等危险命令 |
| "脚手架/批量生成目录/练习模板" | `misc/scaffold-exercises` | 批量生成练习题目录结构 |

### 工作流链路（常见组合）

用户说「出个需求然后开发」，实际执行链路：
1. 先调 `engineering/to-prd` 生成 PRD
2. 用户确认后调 `engineering/to-issues` 拆分任务
3. 调 `engineering/implement` 逐个实现

用户说「排查这个 bug 然后写测试防住」：
1. 调 `engineering/diagnosing-bugs` 诊断修复
2. 调 `engineering/tdd` 补回归测试

### 永不自动触发的 Skill（需用户明确说）

- `engineering/setup-matt-pocock-skills` — 全局配置，只跑一次
- `engineering/triage` — Issue 分流，需用户说要"分流 Issue"
- `misc/migrate-to-shoehorn` — TypeScript 专用，此项目不适用
- `productivity/writing-great-skills` — 写 skill 的元技能，需用户说要"写 skill"
