# 定制方案 3️⃣：知识查询权限设置（部门—角色—知识域/文档—操作）

> 分支：`feature/kb-permission`
> 目标：在 Dify 社区版（OSS）基础上实现「部门 — 角色 — 知识域/文档 — 操作」四层授权。
> 本文基于 `api/`、`web/` 现有代码实地核查后编写。

---

## 一、现状核查结论（重要：先纠正一个认知）

调研中发现本 fork（Dify 社区版 OSS）存在**两套**"权限"代码，必须区分清楚：

### 1. 企业版 RBAC（`api/services/enterprise/`）—— ⚠️ 社区版不可用

- `api/services/enterprise/rbac_service.py`（1843 行）、`api/controllers/console/workspace/rbac.py`、`api/core/rbac/entities.py`、装饰器 `rbac_permission_required`（`api/controllers/common/wraps.py`）。
- **关键**：这整套是「企业版客户端」——通过 `EnterpriseRequest`（`api/services/enterprise/base.py`）向**独立的 dify-enterprise 后端** `ENTERPRISE_API_URL` 发起 HTTP 调用（`/inner/api/rbac/*`）。
- **默认关闭**：`api/configs/enterprise/__init__.py` 中 `RBAC_ENABLED: bool = False`；为 `False` 时 `rbac_permission_required` / `enforce_rbac_access` 直接 no-op 放行。
- **结论**：社区版 fork **不含**企业后端，这套 RBAC 无法开箱使用。真正在社区版生效的是下面第 2 套。

### 2. 社区版数据集权限（本 fork 实际生效的）—— ✅ 定制的基础

这是社区版真正在线的权限机制，全部在 `api/models/dataset.py` + `api/services/dataset_service.py`：

| 内容 | 位置 | 说明 |
|------|------|------|
| 权限枚举 | `api/models/enums.py:383` `PermissionEnum`（= `DatasetPermissionEnum`） | `only_me` / `all_team_members` / `partial_members` |
| 数据集权限字段 | `api/models/dataset.py:184` `Dataset.permission` | 数据集级可见性 |
| 归属人 | `api/models/dataset.py:193` `Dataset.maintainer` | 数据集负责人 |
| 成员授权表 | `api/models/dataset.py:1439` `DatasetPermission`（表 `dataset_permissions`） | `dataset_id / account_id / tenant_id / has_permission`，**粒度到「成员×数据集」** |
| 校验函数 | `api/services/dataset_service.py:1373` `check_dataset_permission()`、`:1392` `check_dataset_operator_permission()` | 实际访问控制 |
| 成员管理 | `api/services/dataset_service.py:4379` `DatasetPermissionService` | `get/update_partial_member_list`、`clear_partial_member_list` |
| 前端设置页 | `web/app/components/datasets/settings/permission-selector/*` | 数据集可见性设置 UI |

**现状粒度 = 「成员（Account）× 数据集（Dataset）× 菜单权限」**，操作层面由各 controller 的 `rbac_permission_required`（社区版为 no-op）+ `check_dataset_permission` 决定；
且**没有部门维度**、**没有文档/分段粒度**、**没有"角色"自定义**（社区版只有内置 `TenantAccountRole`：owner/admin/editor/normal/dataset_operator）。

---

## 二、四层授权模型设计

需求方要求的四层：**部门 — 角色 — 知识域/文档 — 操作**。

落地为「主体 / 资源 / 动作」三层实体 + 绑定关系：

```
主体(Subject)                      资源(Resource)                动作(Action)
┌─────────────┐                  ┌──────────────────┐        ┌─────────────────┐
│ 部门 Department │ ←──┐           │ 知识域(数据集) Dataset │        │ 操作 Permission  │
│ 成员 Account/User │←┐  │        │ 文档 Document │          │ preview / edit   │
│ 角色 Role     │  │  │        │ 分段 Segment │          │ retrieval_recall │
└─────────────┘  │  │        └──────────────────┘        │ download / 等    │
   (部门可含成员/角色)  │  │                                  └─────────────────┘
      授权策略(ACL):  Subject × Resource × Action
```

### 新增 / 扩展实体（数据表）

| 表 | 说明 |
|----|------|
| `departments`（**新增**） | 部门/机构树：`id, tenant_id, parent_id, name, sort`, 自关联树 |
| `department_members`（**新增**） | 部门成员绑定：`id, department_id, account_id, tenant_id` |
| `roles`（**新增，自定义角色**） | `id, tenant_id, name, description, built_in`（社区版目前只有内置角色，需新增自定义角色表） |
| `role_permissions`（**新增**） | 角色→权限点目录，`role_id, permission_key, tenant_id` |
| ``user_roles``（**新增/复用**） | 成员→角色绑定（自定义角色与内置角色统一） |
| `resource_access` / 扩展 `dataset_permissions`（**扩展**） | 将粒度从「成员×数据集」扩展到「主体(部门/角色/成员)×资源(数据集/文档)」 |

> 设计倾向：**复用并扩展现有 `dataset_permissions`**，新增 `subject_type`（account/department/role）、`resource_type`（dataset/document）、`resource_id`、`permission_key`，同时保留现状兼容。文档级可用 `ResourceAccess` 新表承载（`resource_type=document`, `resource_id=document_id`），避免改动过大的既有表。

### 操作（Action）权限点

复用社区版已有权限点（`api/core/rbac/entities.py` `RBACPermission` 中 DATASET_*）作为场景标，**新增文档级**操作：
- 数据集级：`dataset_preview / dataset_readonly / dataset_edit / dataset_retrieval_recall / dataset_use / dataset_document_download / dataset_delete_file / dataset_delete / dataset_access_config / dataset_api_key_manage`（已有）
- 文档级（**新增**）：`document_read / document_retrieval / document_download / document_edit / document_delete`

---

## 三、后端改造点（`api/`）

### 3.1 新增数据模型
- `api/models/department.py`（新）：`Department`、`DepartmentMember`
- `api/models/custom_role.py`（新）：`Role`、`RolePermission`、`UserRole`
- `api/models/resource_access.py`（新）：统一「主体×资源×操作」授权表（部门/角色/成员 × 数据集/文档）
- 在 `api/models/__init__.py` 导出新模型

### 3.2 迁移
- 在 `api/migrations/versions/` 新增迁移文件：建 `departments` / `department_members` / `roles` / `role_permissions` / `user_roles` / `resource_access` 表，并在 `dataset_permissions` 增加 `subject_type/resource_type` 可空列（向后兼容）。
- 数据初始化脚本：为指定租户导入内置角色（映射现有 `TenantAccountRole`）。

### 3.3 服务层
- `api/services/department_service.py`（新）：部门/成员 CRUD、树查询、`member_department_ids(user)`。
- 扩展 `api/services/dataset_service.py`：
  - 重写 `check_dataset_permission()` 为**四层校验**：`is_owner → (部门/角色/成员) × (数据集/文档) × 操作` 逐一解析 `resource_access`；保留 `all_team_members / only_me` 兼容逻辑。
  - 新增 `check_document_permission(dataset, document, user, permission_key)`（文档级校验）。
  - 新增统一鉴权查询：`resolve_effective_permissions(user, resource_type, resource_id)`（合并部门、角色、成员各来源授权）。
- `api/services/access_policy_service.py`（新）：授权策略 CRUD（给 dataset/document 授权给 部门/角色/成员 + 操作集合）。

### 3.4 接口层（`api/controllers/console/`）
- 部门管理：
  - `GET/POST/PATCH/DELETE /console/api/workspaces/current/departments` — 部门树 CRUD
  - `POST/DELETE /console/api/departments/{id}/members` — 部门成员管理
- 自定义角色：
  - `GET/POST/PATCH/DELETE /console/api/workspaces/current/custom-roles`
  - `PATCH /console/api/custom-roles/{id}/permissions` — 配置权限点目录
- 授权策略：
  - `GET/POST /console/api/datasets/{dataset_id}/access-policies` — 数据集授权（subject=部门/角色/成员, actions）
  - `GET/POST /console/api/datasets/{dataset_id}/documents/{document_id}/access-policies` — 文档级授权
- 鉴权查询辅助：`GET /console/api/datasets/{id}/my-permissions`（当前请求者获得的权限清单，供前端渲染）

### 3.5 检索/运行时强制
- 知识检索入口（命中数据集时）接入文档级/数据集级鉴权：
  - `api/services/hit_testing_service.py`（检索测试）
  - 应用侧 retrieval 回调 / `api/core/rag/` 检索路径，在执行 recall 前校验 `dataset_retrieval_recall` / `document_retrieval`。
- 下载入口：`datasets_document.py` 的下载接口已带 `DATASET_DOCUMENT_DOWNLOAD`，补文档级下载校验 `document_download`。

---

## 四、前端改造点（`web/`）

### 4.1 新增页面/组件
- 部门管理页：`web/app/components/workspace/departments/`（部门树 + 成员编辑，带搜索/递归）
- 自定义角色页：`web/app/components/workspace/custom-roles/`（角色列表 + 权限点复选树）
- 数据集授权编辑器：`web/app/components/datasets/access-policy-editor/`（参照现有 `web/app/components/access-rules-editor/`，支持选择主体=部门/角色/成员 + 勾选操作）
- 文档级授权：数据集详情 → 文档行内「授权」操作，弹出同上编辑器

### 4.2 修改现有设置页
- `web/app/components/datasets/settings/permission-selector/*`：在既有 `only_me/all_team_members/partial_members` 基础上，新增「自定义授权（部门/角色/成员 + 操作）」入口。

### 4.3 类型与 API
- `web/app/(commonLayout)/datasets/dataset-*/` 相关 API 调用若涉及列表需按新鉴权过滤；UI 层读取 `my-permissions` 决定可见操作按钮。
- 新增 `web/app/components/.../departments`、`custom-roles` 的 API client（ts）。

---

## 五、数据表汇总（新增）

```text
departments          (id, tenant_id, parent_id, name, sort, created_at)
department_members   (id, department_id, account_id, tenant_id)
roles                (id, tenant_id, name, description, built_in)
role_permissions     (id, role_id, permission_key, tenant_id)
user_roles           (id, user_id, role_id, tenant_id)
resource_access      (id, tenant_id, subject_type, subject_id, resource_type,
                      resource_id, permission_key, created_at)   -- 核心授权表
dataset_permissions  (+ subject_type, resource_type 列, 兼容扩展)
```

---

## 六、实施步骤（建议顺序）

1. **数据层**：新增模型 + 迁移（departments / roles / resource_access 等），写单元测试。
2. **服务层核心**：实现 `resolve_effective_permissions` 与 `check_dataset/document_permission` 四层校验；先用单元测试覆盖 owner/部门/角色/成员 各来源与优先级。
3. **接口**：部门 / 自定义角色 / 授权策略 CRUD controller。
4. **接入强制点**：将校验接入 `check_dataset_permission`、检索 recall、文档下载。
5. **前端**：部门管理、角色、授权编辑器、文档级授权 UI。
6. **迁移与初始化**：内置角色种子、README 更新、`docs/` 设计文档留档。

---

## 七、风险与待确认项

- **粒度待业务确认**：授权粒度需业务方确认——是否落到**文档级**还是仅**数据集级**？（本文按「数据集+文档」两级设计，可降级为仅数据集级以缩小范围。）
- **自定义角色与内置角色并存**：社区版角色模型是 `TenantAccountRole` 枚举 + `tenant_account_joins.role`，引入自定义 `roles` 需要统一「内置角色」与「自定义角色」的判定逻辑，避免双轨混乱。
- **检索性能**：逐文档鉴权会增加 recall 路径查询，建议加缓存/批量解析（一次查 `resource_access` 全量授权，内存中判定）。
- **RBAC_ENABLED 与社区模式**：保持 `RBAC_ENABLED=false`（不依赖企业后端），改造完全落在社区版 `dataset_permissions`/`resource_access` 上，避免与企业客户端冲突。
- **同步上游**：本分支改动涉及 `check_dataset_permission` 等共享函数，日后 `merge upstream/main` 可能冲突，需注意。

---

*文件清单、接口清单、数据表清单以上均已列出；具体实现按第 6 节顺序推进。*
