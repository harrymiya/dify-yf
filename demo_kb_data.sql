-- ============================================================
-- demo_kb_data.sql
-- 创建 KB 四层授权/审计/图谱新表（幂等，表名带 kb_ 前缀）+ 写入 demo 数据
-- 关联现有环境:
--   tenant  = 2025d4d9-0382-4649-99e4-155377357429 (lirui's Workspace)
--   account = a431f6a0-67f7-480a-bdde-8ad60df5ac70 (harrydolly1226@gmail.com)
--   dataset = dfa37227-dc91-4de4-bead-e1f787272814 (test)
--   document= 588e5ef2-dabc-4772-a22c-3fa666fd7dd5 (可视化算子分类建议.md)
-- ============================================================

BEGIN;

-- -----------------------------------------------------------
-- 1) 建表（幂等：IF NOT EXISTS；表名带 kb_ 前缀避免与上游冲突）
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS departments (
    id          uuid PRIMARY KEY,
    tenant_id   uuid NOT NULL,
    parent_id   uuid,
    name        varchar(255) NOT NULL,
    sort        integer NOT NULL DEFAULT 0,
    created_at  timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_departments_tenant_id ON departments (tenant_id);
CREATE INDEX IF NOT EXISTS idx_departments_parent_id ON departments (parent_id);

CREATE TABLE IF NOT EXISTS department_members (
    id            uuid PRIMARY KEY,
    department_id uuid NOT NULL,
    account_id    uuid NOT NULL,
    tenant_id     uuid NOT NULL,
    created_at    timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_department_members_department_id ON department_members (department_id);
CREATE INDEX IF NOT EXISTS idx_department_members_account_id ON department_members (account_id);
CREATE INDEX IF NOT EXISTS idx_department_members_tenant_id ON department_members (tenant_id);

CREATE TABLE IF NOT EXISTS kb_roles (
    id          uuid PRIMARY KEY,
    tenant_id   uuid NOT NULL,
    name        varchar(255) NOT NULL,
    description varchar(255),
    built_in    boolean NOT NULL DEFAULT false,
    created_at  timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_kb_roles_tenant_id ON kb_roles (tenant_id);

CREATE TABLE IF NOT EXISTS kb_user_roles (
    id         uuid PRIMARY KEY,
    user_id    uuid NOT NULL,
    role_id    uuid NOT NULL,
    tenant_id  uuid NOT NULL,
    created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_kb_user_roles_user_id ON kb_user_roles (user_id);
CREATE INDEX IF NOT EXISTS idx_kb_user_roles_role_id ON kb_user_roles (role_id);
CREATE INDEX IF NOT EXISTS idx_kb_user_roles_tenant_id ON kb_user_roles (tenant_id);

CREATE TABLE IF NOT EXISTS kb_permission_grants (
    id            uuid PRIMARY KEY,
    tenant_id     uuid NOT NULL,
    subject_type  varchar(32) NOT NULL,
    subject_id    uuid NOT NULL,
    resource_type varchar(32) NOT NULL,
    resource_id   uuid NOT NULL,
    action        varchar(64) NOT NULL,
    created_by    uuid,
    created_at    timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_kb_grants_tenant_resource ON kb_permission_grants (tenant_id, resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_kb_grants_subject ON kb_permission_grants (subject_type, subject_id);

CREATE TABLE IF NOT EXISTS kb_audit_logs (
    id            uuid PRIMARY KEY,
    tenant_id     uuid NOT NULL,
    user_id       uuid,
    user_type     varchar(32),
    log_type      varchar(32) NOT NULL,
    action        varchar(64) NOT NULL,
    status        varchar(16) NOT NULL,
    resource_type varchar(32),
    resource_id   uuid,
    detail        json,
    ip            varchar(45),
    request_id    varchar(16),
    trace_id      varchar(64),
    created_at    timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_kb_audit_logs_tenant_created ON kb_audit_logs (tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_kb_audit_logs_tenant_type ON kb_audit_logs (tenant_id, log_type);

CREATE TABLE IF NOT EXISTS graph_entities (
    id          uuid PRIMARY KEY,
    tenant_id   uuid NOT NULL,
    dataset_id  uuid,
    document_id uuid,
    name        varchar(255) NOT NULL,
    entity_type varchar(64),
    description text,
    created_at  timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_graph_entities_tenant_dataset ON graph_entities (tenant_id, dataset_id);
CREATE INDEX IF NOT EXISTS idx_graph_entities_name ON graph_entities (tenant_id, name);

CREATE TABLE IF NOT EXISTS graph_relations (
    id               uuid PRIMARY KEY,
    tenant_id        uuid NOT NULL,
    source_entity_id uuid NOT NULL,
    target_entity_id uuid NOT NULL,
    relation_type    varchar(64) NOT NULL,
    detail           json,
    created_at       timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_graph_relations_tenant ON graph_relations (tenant_id);
CREATE INDEX IF NOT EXISTS idx_graph_relations_source ON graph_relations (tenant_id, source_entity_id);

-- -----------------------------------------------------------
-- 2) 部门树 demo
-- -----------------------------------------------------------
INSERT INTO departments (id, tenant_id, parent_id, name, sort) VALUES
    ('a0000000-0000-4000-8000-000000000001', '2025d4d9-0382-4649-99e4-155377357429', NULL, '全公司', 0),
    ('a0000000-0000-4000-8000-000000000002', '2025d4d9-0382-4649-99e4-155377357429', 'a0000000-0000-4000-8000-000000000001', '研发部', 1),
    ('a0000000-0000-4000-8000-000000000003', '2025d4d9-0382-4649-99e4-155377357429', 'a0000000-0000-4000-8000-000000000001', '数据部', 2),
    ('a0000000-0000-4000-8000-000000000004', '2025d4d9-0382-4649-99e4-155377357429', 'a0000000-0000-4000-8000-000000000002', '可视化算法组', 1)
ON CONFLICT (id) DO NOTHING;

-- 成员：把现有账号加入 研发部
INSERT INTO department_members (id, department_id, account_id, tenant_id) VALUES
    ('a1000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000002',
     'a431f6a0-67f7-480a-bdde-8ad60df5ac70', '2025d4d9-0382-4649-99e4-155377357429')
ON CONFLICT (id) DO NOTHING;

-- -----------------------------------------------------------
-- 3) 自定义角色 demo
-- -----------------------------------------------------------
INSERT INTO kb_roles (id, tenant_id, name, description, built_in) VALUES
    ('b0000000-0000-4000-8000-000000000001', '2025d4d9-0382-4649-99e4-155377357429', '知识管理员', '可管理与配置知识库权限', false),
    ('b0000000-0000-4000-8000-000000000002', '2025d4d9-0382-4649-99e4-155377357429', '普通用户', '仅可检索与下载', false)
ON CONFLICT (id) DO NOTHING;

INSERT INTO kb_user_roles (id, user_id, role_id, tenant_id) VALUES
    ('b1000000-0000-4000-8000-000000000001', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70',
     'b0000000-0000-4000-8000-000000000001', '2025d4d9-0382-4649-99e4-155377357429')
ON CONFLICT (id) DO NOTHING;

-- -----------------------------------------------------------
-- 4) 四层授权 demo（subject x resource x action, 默认 deny）
-- -----------------------------------------------------------
-- 账号级：test 数据集 只读/检索/编辑
INSERT INTO kb_permission_grants (id, tenant_id, subject_type, subject_id, resource_type, resource_id, action, created_by) VALUES
    ('c0000000-0000-4000-8000-000000000001', '2025d4d9-0382-4649-99e4-155377357429', 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_preview', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000002', '2025d4d9-0382-4649-99e4-155377357429', 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_readonly', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000003', '2025d4d9-0382-4649-99e4-155377357429', 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_retrieval_recall', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000004', '2025d4d9-0382-4649-99e4-155377357429', 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_edit', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70')
ON CONFLICT (id) DO NOTHING;
-- 部门级：研发部 检索+下载；数据部 仅预览
INSERT INTO kb_permission_grants (id, tenant_id, subject_type, subject_id, resource_type, resource_id, action, created_by) VALUES
    ('c0000000-0000-4000-8000-000000000005', '2025d4d9-0382-4649-99e4-155377357429', 'department', 'a0000000-0000-4000-8000-000000000002', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_retrieval_recall', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000006', '2025d4d9-0382-4649-99e4-155377357429', 'department', 'a0000000-0000-4000-8000-000000000002', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_document_download', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000007', '2025d4d9-0382-4649-99e4-155377357429', 'department', 'a0000000-0000-4000-8000-000000000003', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_preview', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70')
ON CONFLICT (id) DO NOTHING;
-- 角色级：知识管理员 编辑器+访问配置
INSERT INTO kb_permission_grants (id, tenant_id, subject_type, subject_id, resource_type, resource_id, action, created_by) VALUES
    ('c0000000-0000-4000-8000-000000000008', '2025d4d9-0382-4649-99e4-155377357429', 'role', 'b0000000-0000-4000-8000-000000000001', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_edit', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000009', '2025d4d9-0382-4649-99e4-155377357429', 'role', 'b0000000-0000-4000-8000-000000000001', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_access_config', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70')
ON CONFLICT (id) DO NOTHING;
-- 文档级：账号 可读/下载原文档
INSERT INTO kb_permission_grants (id, tenant_id, subject_type, subject_id, resource_type, resource_id, action, created_by) VALUES
    ('c0000000-0000-4000-8000-000000000010', '2025d4d9-0382-4649-99e4-155377357429', 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'document', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', 'document_read', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000011', '2025d4d9-0382-4649-99e4-155377357429', 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'document', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', 'document_download', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70')
ON CONFLICT (id) DO NOTHING;

-- -----------------------------------------------------------
-- 5) 知识图谱 demo（源自"可视化算子分类建议.md"内容）
-- -----------------------------------------------------------
INSERT INTO graph_entities (id, tenant_id, dataset_id, document_id, name, entity_type, description) VALUES
    ('d0000000-0000-4000-8000-000000000001', '2025d4d9-0382-4649-99e4-155377357429', 'dfa37227-dc91-4de4-bead-e1f787272814', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', '可视化算子', 'concept', '可视化类算子，共 62 个，全部纳入分类'),
    ('d0000000-0000-4000-8000-000000000002', '2025d4d9-0382-4649-99e4-155377357429', 'dfa37227-dc91-4de4-bead-e1f787272814', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', '通用算子', 'concept', '通用业务算子，共 45 个'),
    ('d0000000-0000-4000-8000-000000000003', '2025d4d9-0382-4649-99e4-155377357429', 'dfa37227-dc91-4de4-bead-e1f787272814', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', '业务算子', 'concept', '业务分类集合'),
    ('d0000000-0000-4000-8000-000000000004', '2025d4d9-0382-4649-99e4-155377357429', 'dfa37227-dc91-4de4-bead-e1f787272814', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', '分类范围', 'section', '本次分类的范围与全集来源说明'),
    ('d0000000-0000-4000-8000-000000000005', '2025d4d9-0382-4649-99e4-155377357429', 'dfa37227-dc91-4de4-bead-e1f787272814', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', '系统算子', 'concept', '以 systemLab 开头的实验室算子，不纳入本次分类')
ON CONFLICT (id) DO NOTHING;

INSERT INTO graph_relations (id, tenant_id, source_entity_id, target_entity_id, relation_type, detail) VALUES
    ('d1000000-0000-4000-8000-000000000001', '2025d4d9-0382-4649-99e4-155377357429', 'd0000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000003', '属于', '{"note": "通用算子属于业务算子分类"}'),
    ('d1000000-0000-4000-8000-000000000002', '2025d4d9-0382-4649-99e4-155377357429', 'd0000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000001', '区别于', '{"note": "业务算子与可视化算子并列"}'),
    ('d1000000-0000-4000-8000-000000000003', '2025d4d9-0382-4649-99e4-155377357429', 'd0000000-0000-4000-8000-000000000004', 'd0000000-0000-4000-8000-000000000001', '界定', '{"note": "分类范围界定可视化算子全集"}'),
    ('d1000000-0000-4000-8000-000000000004', '2025d4d9-0382-4649-99e4-155377357429', 'd0000000-0000-4000-8000-000000000005', 'd0000000-0000-4000-8000-000000000004', '排除于', '{"note": "系统算子不纳入分类范围"}')
ON CONFLICT (id) DO NOTHING;

-- -----------------------------------------------------------
-- 6) 审计日志 demo（覆盖 5 类）
-- -----------------------------------------------------------
INSERT INTO kb_audit_logs (id, tenant_id, user_id, user_type, log_type, action, status, resource_type, resource_id, detail, ip) VALUES
    ('e0000000-0000-4000-8000-000000000001', '2025d4d9-0382-4649-99e4-155377357429', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'account', 'qna', 'app.retrieval', 'success', 'app', 'dfa37227-dc91-4de4-bead-e1f787272814', '{"dataset_ids":["dfa37227-dc91-4de4-bead-e1f787272814"],"query":"可视化算子分类","source":"app"}', '127.0.0.1'),
    ('e0000000-0000-4000-8000-000000000002', '2025d4d9-0382-4649-99e4-155377357429', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'account', 'retrieval', 'hit_testing.retrieve', 'success', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', '{"query":"可视化算子","hits":3}', '127.0.0.1'),
    ('e0000000-0000-4000-8000-000000000003', '2025d4d9-0382-4649-99e4-155377357429', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'account', 'download', 'document.download_file', 'success', 'document', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', '{"dataset_id":"dfa37227-dc91-4de4-bead-e1f787272814","file_name":"可视化算子分类建议.md"}', '127.0.0.1'),
    ('e0000000-0000-4000-8000-000000000004', '2025d4d9-0382-4649-99e4-155377357429', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'account', 'permission_change', 'kb_permission.grant', 'success', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', '{"subject_type":"department","subject_id":"a0000000-0000-4000-8000-000000000002","actions":["dataset_retrieval_recall"],"created":1}', '127.0.0.1'),
    ('e0000000-0000-4000-8000-000000000005', '2025d4d9-0382-4649-99e4-155377357429', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'account', 'system', 'kb_graph.build', 'success', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', '{"entities_created":5,"relations_created":4,"segments_processed":93}', '127.0.0.1')
ON CONFLICT (id) DO NOTHING;

COMMIT;
