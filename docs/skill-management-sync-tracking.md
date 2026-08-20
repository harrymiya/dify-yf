# Skill Management 同步跟踪

> 目标：当上游缺省开源分支（langgenius/dify `main`）正式完成 roadmap 的 **Skill Management**
> 功能后，做一次针对性同步到本 fork（dify-yf）。

## Roadmap 条目

- 站点：https://roadmap.dify.ai/roadmap
- slug：`skill-management`
- 标题：Skill Management
- 状态：**In Progress（进行中，截至 2026-07-21）** —— 尚未 Completed
- 内容：Extract business SOPs from agent prompts into centrally managed, versioned
  resources that any Agent can reuse. Edit once, apply everywhere.

## 当前 fork 状态（2026-08）

- Fork `dev`（HEAD `2fdfa930f8`）**已具备完整 Skill 能力**：
  - 后端：`api/controllers/console/app/agent.py` 中的 skill 路由
    （`/agent/:id/skills/upload`、`/apps/:app_id/agent/skills/upload`、`/agent/:id/skills/:slug`、
    `/agent/:id/skills/:slug/infer-tools`、files 等）
  - 服务：`api/services/agent/skill_package_service.py`、`config_skill_normalize_service.py`
  - 前端：`web/features/agent-v2/agent-detail/configure/components/orchestrate/skills/`
    （index / item / detail-dialog / upload-dialog / use-skill-detail）+
    `web/features/agent-v2/agent-composer/store-modules/skills.ts`
- 上述 skill 文件与上游（移除 Agent Drive 之前）逐字节一致，无本地未提交改动。

## 上游最新动向（需等待）

- 上游 commit `8874f3c80b refactor(agent): remove Agent Drive (#40887)`（2026-08-19）
  删除了旧实现：`agent_drive_service.py`、`skill_standardize_service.py`、
  `skill_tool_inference_service.py`、`agent_drive_inspector.py`、`skill_standardize`/`infer-tools` 等。
  说明 **Skill Management 最终形态仍在上游重构中**，尚未定型。
- **触发同步的条件**：上游 `main` 出现正式把 Skill Management 定位为 Completed / 合入统一的
  skill 管理实现的提交流程，且含新增/改动的 skill 相关代码。

## 同步方法（届时执行）

当上述条件满足后，在 fork 中执行针对性同步：

```bash
# 1. 拉取最新上游 main
git fetch upstream main

# 2. 查看上游新增/改动的 skill 相关提交（不含旧 Agent Drive 重构）
git log --oneline HEAD..upstream/main | grep -i skill

# 3. 仅挑选 Skill Management 相关提交 cherry-pick 到功能分支后合入
#    或按文件做定点合并：
git diff HEAD upstream/main -- 'api/services/agent/*skill*' \
  'web/features/agent-v2/**/skills/**' 'api/controllers/**/*skill*'

# 4. 因 fork 有本地定制，需人工 review 冲突后提交
```

## 注意事项

- 不需要把 `8874f3c80b`（删除 Agent Drive）整段拉入，除非你决定跟进上游重构方向。
- fork 有本地定制功能，合并到 skill 相关文件时需要人工 review，避免覆盖定制逻辑。
