# Git 协同实践记录（第 3 周）

> 仓库：https://github.com/yuyu41-sg/ydsh-week3 ｜ 成员：张宇（20230308059）

## 一、分支模型

- 主分支 `main`：承载可直接交付的代码与报告
- 功能分支 `feature/nl2sql-tests`：NL2SQL 实测开发与测试记录，独立开发后经 PR 合入 main
- 版本标签 `v0.1.0`：第 3 周基础交付（DWS/ADS 建模、预测建模、AI 代码框架）

## 二、关键提交

| 提交 | 分支 | 说明 |
|---|---|---|
| 5f08a65 | main | 第3周基础交付（DWS/ADS 建模与 KPI、时间序列预测与报告、AI 代码框架） |
| 27451e6 | feature | NL2SQL 测试用例记录与人工验证口径 |
| 5c18d4f | feature | NL2SQL 实测通过并新增报错自修复机制 |
| 3ec30e7 | main | 大模型接入切换为智谱 GLM 并完成 AI 洞察实测 |
| 1b51483 | main | README 补充 NL2SQL 自修复机制与实测结果（与 feature 分支修改同一行，埋下冲突） |
| 9546593 | feature | README 关键成果补充 NL2SQL 实测通过率（与 main 修改同一行，埋下冲突） |
| 3b3c5b8 | feature | merge: 解决 README 冲突（保留双方描述，融合合并） |

## 三、Issue 追踪（Issue #1）

- 标题：NL2SQL 生成的 SQL 在 Hive 报 GROUP BY 别名错误（10004）
- 内容：glm-4-flash 生成的 SQL 使用 SELECT 别名做 GROUP BY，Hive 4.0 不支持，报 SemanticException 10004；计划通过提示词方言约束 + repair_sql() 报错回传自修复解决
- 关联：PR #2 描述含 `Closes #1`，合并时自动关闭
- 截图：`截图/01_Issue创建与PR关联.png`

## 四、Pull Request 与 Code Review（PR #2）

- PR：feature/nl2sql-tests → main，标题"NL2SQL 实测通过并新增报错自修复机制"
- Code Review：在 Files changed 中对 `repair_sql()` 自修复逻辑发表评审意见（重试上限 2 次防死循环，符合预期），自审留痕
- 截图：`截图/02_PR冲突提示_CantAutomaticallyMerge.png`、`截图/03_冲突解决后PR_diff.png`

## 五、合并冲突解决实录

1. 起因：main（1b51483）与 feature（9546593）先后修改了 README.md"关键成果"中同一行 NL2SQL 描述，且内容不同；
2. GitHub PR 页面显示 "Can't automatically merge"（截图 02）；
3. 本地执行 `git checkout feature/nl2sql-tests && git merge main`，复现冲突：
   ```
   Auto-merging README.md
   CONFLICT (content): Merge conflict in README.md
   ```
4. 解决原则：不简单二选一，而是融合双方意图——保留 main 的"自修复机制描述"与 feature 的"测试通过率 + 文档指引"，合并为一句完整描述；
5. `git add README.md && git commit` 完成合并提交 3b3c5b8 并推送，PR 恢复可合并状态；
6. 经 PR #2 合入 main，Issue #1 随 `Closes #1` 自动关闭。

合并图谱：
```
*   3b3c5b8 merge: 解决 README 冲突
|\
| * 1b51483 docs: README 补充 NL2SQL 自修复机制（main）
| * 3ec30e7 feat: 切换智谱GLM并完成AI洞察实测（main）
* | 9546593 docs: README 补充实测通过率（feature）
* | 5c18d4f feat: NL2SQL 实测+自修复（feature）
* | 27451e6 feat: 测试用例记录（feature）
|/
* 5f08a65 feat: 第3周基础交付（main）
```

## 六、密钥安全

- API Key 仅存本地 `.env`（`.gitignore` 排除，未入版本库），`.env.example` 仅含模板占位符
