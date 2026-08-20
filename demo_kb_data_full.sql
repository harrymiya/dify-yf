-- ============================================================
-- demo_kb_data_full.sql
-- 覆盖 KB 权限改造的全部模块 demo 数据（幂等/可重复执行）
--
-- 覆盖模块:
--   M1 部门管理      departments / department_members
--   M2 角色管理      kb_roles / kb_user_roles
--   M3 四层授权      kb_permission_grants (account x department x role -> dataset/document)
--   M4 审计日志      kb_audit_logs (qna / retrieval / download / permission_change / system)
--   M5 知识图谱      graph_entities / graph_relations
--   M6 使用统计      dataset_queries (KB 调用量 + 时间趋势)
--
-- 关联现有环境:
--   tenant  = 2025d4d9-0382-4649-99e4-155377357429 (lirui's Workspace)
--   account = a431f6a0-67f7-480a-bdde-8ad60df5ac70 (harrydolly1226@gmail.com)
--   dataset = dfa37227-dc91-4de4-bead-e1f787272814 (test)
--   document= 588e5ef2-dabc-4772-a22c-3fa666fd7dd5 (可视化算子分类建议.md)
-- ============================================================

BEGIN;

-- ============================================================
-- M1 部门管理
-- ============================================================
-- 部门树: 全公司 -> 研发部(->可视化算法组/前端组) / 数据部(->数据治理组/数据分析组) / 产品部 / 运营部 / 财务部
INSERT INTO departments (id, tenant_id, parent_id, name, description, sort) VALUES
    ('a0000000-0000-4000-8000-000000000001', '2025d4d9-0382-4649-99e4-155377357429', NULL, '全公司', '公司根组织，包含所有一级部门', 0),
    ('a0000000-0000-4000-8000-000000000002', '2025d4d9-0382-4649-99e4-155377357429', 'a0000000-0000-4000-8000-000000000001', '研发部', '负责可视化算法与前端产品的研发', 1),
    ('a0000000-0000-4000-8000-000000000003', '2025d4d9-0382-4649-99e4-155377357429', 'a0000000-0000-4000-8000-000000000001', '数据部', '负责数据处理、治理与分析', 2),
    ('a0000000-0000-4000-8000-000000000004', '2025d4d9-0382-4649-99e4-155377357429', 'a0000000-0000-4000-8000-000000000002', '可视化算法组', '负责可视化算子的研发与维护', 1),
    ('a0000000-0000-4000-8000-000000000005', '2025d4d9-0382-4649-99e4-155377357429', 'a0000000-0000-4000-8000-000000000002', '前端组', '负责前端界面与交互开发', 2),
    ('a0000000-0000-4000-8000-000000000006', '2025d4d9-0382-4649-99e4-155377357429', 'a0000000-0000-4000-8000-000000000003', '数据治理组', '负责数据标准与质量管理', 1),
    ('a0000000-0000-4000-8000-000000000007', '2025d4d9-0382-4649-99e4-155377357429', 'a0000000-0000-4000-8000-000000000003', '数据分析组', '负责数据分析与报表产出', 2),
    ('a0000000-0000-4000-8000-000000000008', '2025d4d9-0382-4649-99e4-155377357429', 'a0000000-0000-4000-8000-000000000001', '产品部', '负责产品规划与需求管理', 3)
ON CONFLICT (id) DO UPDATE SET description = EXCLUDED.description;

-- 成员：把现有账号加入 研发部（演示部门成员归属）
INSERT INTO department_members (id, department_id, account_id, tenant_id) VALUES
    ('a1000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000002',
     'a431f6a0-67f7-480a-bdde-8ad60df5ac70', '2025d4d9-0382-4649-99e4-155377357429')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- M2 角色管理
-- ============================================================
-- 自定义角色 + 内置角色
INSERT INTO kb_roles (id, tenant_id, name, description, built_in) VALUES
    ('b0000000-0000-4000-8000-000000000001', '2025d4d9-0382-4649-99e4-155377357429', '知识管理员', '可管理与配置知识库权限', false),
    ('b0000000-0000-4000-8000-000000000002', '2025d4d9-0382-4649-99e4-155377357429', '普通用户', '仅可检索与下载', false),
    ('b0000000-0000-4000-8000-000000000003', '2025d4d9-0382-4649-99e4-155377357429', '知识浏览者', '只读浏览，不可检索下载', false),
    ('b0000000-0000-4000-8000-000000000004', '2025d4d9-0382-4649-99e4-155377357429', '数据集编辑器', '内置角色：可编辑数据集', true)
ON CONFLICT (id) DO NOTHING;

-- 角色-用户绑定：账号同时具备 知识管理员 + 数据集编辑器
INSERT INTO kb_user_roles (id, user_id, role_id, tenant_id) VALUES
    ('b1000000-0000-4000-8000-000000000001', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70',
     'b0000000-0000-4000-8000-000000000001', '2025d4d9-0382-4649-99e4-155377357429'),
    ('b1000000-0000-4000-8000-000000000002', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70',
     'b0000000-0000-4000-8000-000000000002', '2025d4d9-0382-4649-99e4-155377357429')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- M3 四层授权 (subject x resource x action, 默认 deny)
-- 主体类型: account / department / role
-- 资源类型: dataset / document
-- ============================================================
-- 3.1 账号级 -> test 数据集：读/检索/编辑/使用/删除文件/API Key管理
INSERT INTO kb_permission_grants (id, tenant_id, subject_type, subject_id, resource_type, resource_id, action, created_by) VALUES
    ('c0000000-0000-4000-8000-000000000001', '2025d4d9-0382-4649-99e4-155377357429', 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_preview', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000002', '2025d4d9-0382-4649-99e4-155377357429', 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_readonly', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000003', '2025d4d9-0382-4649-99e4-155377357429', 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_retrieval_recall', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000004', '2025d4d9-0382-4649-99e4-155377357429', 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_edit', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000012', '2025d4d9-0382-4649-99e4-155377357429', 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_use', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000013', '2025d4d9-0382-4649-99e4-155377357429', 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_delete_file', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000014', '2025d4d9-0382-4649-99e4-155377357429', 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_api_key_manage', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70')
ON CONFLICT (id) DO NOTHING;

-- 3.2 部门级 -> 研发部(含祖先链) 检索+下载；数据部 仅预览；可视化算法组 只读
INSERT INTO kb_permission_grants (id, tenant_id, subject_type, subject_id, resource_type, resource_id, action, created_by) VALUES
    ('c0000000-0000-4000-8000-000000000005', '2025d4d9-0382-4649-99e4-155377357429', 'department', 'a0000000-0000-4000-8000-000000000002', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_retrieval_recall', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000006', '2025d4d9-0382-4649-99e4-155377357429', 'department', 'a0000000-0000-4000-8000-000000000002', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_document_download', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000007', '2025d4d9-0382-4649-99e4-155377357429', 'department', 'a0000000-0000-4000-8000-000000000003', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_preview', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000015', '2025d4d9-0382-4649-99e4-155377357429', 'department', 'a0000000-0000-4000-8000-000000000004', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_readonly', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70')
ON CONFLICT (id) DO NOTHING;

-- 3.3 角色级 -> 知识管理员 编辑+访问配置+删除；普通用户 只读+检索
INSERT INTO kb_permission_grants (id, tenant_id, subject_type, subject_id, resource_type, resource_id, action, created_by) VALUES
    ('c0000000-0000-4000-8000-000000000008', '2025d4d9-0382-4649-99e4-155377357429', 'role', 'b0000000-0000-4000-8000-000000000001', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_edit', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000009', '2025d4d9-0382-4649-99e4-155377357429', 'role', 'b0000000-0000-4000-8000-000000000001', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_access_config', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000016', '2025d4d9-0382-4649-99e4-155377357429', 'role', 'b0000000-0000-4000-8000-000000000001', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_delete', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000017', '2025d4d9-0382-4649-99e4-155377357429', 'role', 'b0000000-0000-4000-8000-000000000002', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_readonly', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000018', '2025d4d9-0382-4649-99e4-155377357429', 'role', 'b0000000-0000-4000-8000-000000000002', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_retrieval_recall', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000019', '2025d4d9-0382-4649-99e4-155377357429', 'role', 'b0000000-0000-4000-8000-000000000003', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', 'dataset_preview', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70')
ON CONFLICT (id) DO NOTHING;

-- 3.4 文档级 -> 账号 读/检索/下载/编辑/删除
INSERT INTO kb_permission_grants (id, tenant_id, subject_type, subject_id, resource_type, resource_id, action, created_by) VALUES
    ('c0000000-0000-4000-8000-000000000010', '2025d4d9-0382-4649-99e4-155377357429', 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'document', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', 'document_read', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000011', '2025d4d9-0382-4649-99e4-155377357429', 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'document', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', 'document_download', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000020', '2025d4d9-0382-4649-99e4-155377357429', 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'document', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', 'document_retrieval', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000021', '2025d4d9-0382-4649-99e4-155377357429', 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'document', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', 'document_edit', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70'),
    ('c0000000-0000-4000-8000-000000000022', '2025d4d9-0382-4649-99e4-155377357429', 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'document', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', 'document_delete', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- M4 审计日志 (5 类事件: qna / retrieval / download / permission_change / system)
-- 含 success + failure
-- ============================================================
INSERT INTO kb_audit_logs (id, tenant_id, user_id, user_type, log_type, action, status, resource_type, resource_id, detail, ip, request_id, trace_id, created_at) VALUES
    -- qna / Q&A 助手检索
    ('e0000000-0000-4000-8000-000000000001', '2025d4d9-0382-4649-99e4-155377357429', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'account', 'qna', 'app.retrieval', 'success', 'app', 'dfa37227-dc91-4de4-bead-e1f787272814', '{"dataset_ids":["dfa37227-dc91-4de4-bead-e1f787272814"],"query":"可视化算子分类","source":"app"}', '127.0.0.1', 'req0000000001', 'trace0000000000000001', now() - interval '2 days'),
    ('e0000000-0000-4000-8000-000000000006', '2025d4d9-0382-4649-99e4-155377357429', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'account', 'qna', 'app.retrieval', 'success', 'app', 'dfa37227-dc91-4de4-bead-e1f787272814', '{"dataset_ids":["dfa37227-dc91-4de4-bead-e1f787272814"],"query":"通用算子有哪些","source":"app"}', '127.0.0.1', NULL, NULL, now() - interval '1 day'),
    -- retrieval / 检索命中测试
    ('e0000000-0000-4000-8000-000000000002', '2025d4d9-0382-4649-99e4-155377357429', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'account', 'retrieval', 'hit_testing.retrieve', 'success', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', '{"query":"可视化算子","hits":3}', '127.0.0.1', 'req0000000002', 'trace0000000000000002', now() - interval '2 days'),
    ('e0000000-0000-4000-8000-000000000007', '2025d4d9-0382-4649-99e4-155377357429', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'account', 'retrieval', 'hit_testing.retrieve', 'failure', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', '{"query":"不存在的内容","error":"no_permission"}', '127.0.0.1', 'req0000000003', 'trace0000000000000003', now() - interval '5 hours'),
    -- download / 原文档下载
    ('e0000000-0000-4000-8000-000000000003', '2025d4d9-0382-4649-99e4-155377357429', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'account', 'download', 'document.download_file', 'success', 'document', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', '{"dataset_id":"dfa37227-dc91-4de4-bead-e1f787272814","file_name":"可视化算子分类建议.md"}', '127.0.0.1', 'req0000000004', 'trace0000000000000004', now() - interval '3 days'),
    -- permission_change / 授权变更
    ('e0000000-0000-4000-8000-000000000004', '2025d4d9-0382-4649-99e4-155377357429', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'account', 'permission_change', 'kb_permission.grant', 'success', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', '{"subject_type":"department","subject_id":"a0000000-0000-4000-8000-000000000002","actions":["dataset_retrieval_recall"],"created":1}', '127.0.0.1', 'req0000000005', 'trace0000000000000005', now() - interval '4 days'),
    ('e0000000-0000-4000-8000-000000000008', '2025d4d9-0382-4649-99e4-155377357429', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'account', 'permission_change', 'kb_permission.revoke', 'success', 'document', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', '{"subject_type":"role","subject_id":"b0000000-0000-4000-8000-000000000002","actions":["document_download"],"revoked":1}', '127.0.0.1', 'req0000000006', 'trace0000000000000006', now() - interval '1 hour'),
    -- system / 系统事件: 图谱构建、审计清理、融合检索
    ('e0000000-0000-4000-8000-000000000005', '2025d4d9-0382-4649-99e4-155377357429', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'account', 'system', 'kb_graph.build', 'success', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', '{"entities_created":8,"relations_created":7,"segments_processed":93}', '127.0.0.1', 'req0000000007', 'trace0000000000000007', now() - interval '6 days'),
    ('e0000000-0000-4000-8000-000000000009', '2025d4d9-0382-4649-99e4-155377357429', NULL, 'system', 'system', 'kb_fusion.retrieve', 'success', 'dataset', 'dfa37227-dc91-4de4-bead-e1f787272814', '{"query":"运营指标","sources":1,"strategy":"rrf"}', '127.0.0.1', 'req0000000008', 'trace0000000000000008', now() - interval '30 minutes')
ON CONFLICT (id) DO NOTHING;

-- 部门/角色创建审计（与 M1/M2 的 demo 数据对应）
INSERT INTO kb_audit_logs (id, tenant_id, user_id, user_type, log_type, action, status, resource_type, resource_id, detail, ip, created_at) VALUES
    ('e0000000-0000-4000-8000-00000000000a', '2025d4d9-0382-4649-99e4-155377357429', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'account', 'permission_change', 'department.create', 'success', 'department', 'a0000000-0000-4000-8000-000000000005', '{"name":"前端组","parent":"研发部"}', '127.0.0.1', now() - interval '2 days'),
    ('e0000000-0000-4000-8000-00000000000b', '2025d4d9-0382-4649-99e4-155377357429', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', 'account', 'permission_change', 'role.create', 'success', 'role', 'b0000000-0000-4000-8000-000000000003', '{"name":"知识浏览者"}', '127.0.0.1', now() - interval '2 days')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- M5 知识图谱 (源自"可视化算子分类建议.md")
-- ============================================================
INSERT INTO graph_entities (id, tenant_id, dataset_id, document_id, name, entity_type, description) VALUES
    ('d0000000-0000-4000-8000-000000000001', '2025d4d9-0382-4649-99e4-155377357429', 'dfa37227-dc91-4de4-bead-e1f787272814', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', '可视化算子', 'concept', '可视化类算子，共 62 个，全部纳入分类'),
    ('d0000000-0000-4000-8000-000000000002', '2025d4d9-0382-4649-99e4-155377357429', 'dfa37227-dc91-4de4-bead-e1f787272814', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', '通用算子', 'concept', '通用业务算子，共 45 个'),
    ('d0000000-0000-4000-8000-000000000003', '2025d4d9-0382-4649-99e4-155377357429', 'dfa37227-dc91-4de4-bead-e1f787272814', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', '业务算子', 'concept', '业务分类集合'),
    ('d0000000-0000-4000-8000-000000000004', '2025d4d9-0382-4649-99e4-155377357429', 'dfa37227-dc91-4de4-bead-e1f787272814', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', '分类范围', 'section', '本次分类的范围与全集来源说明'),
    ('d0000000-0000-4000-8000-000000000005', '2025d4d9-0382-4649-99e4-155377357429', 'dfa37227-dc91-4de4-bead-e1f787272814', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', '系统算子', 'concept', '以 systemLab 开头的实验室算子，不纳入本次分类'),
    ('d0000000-0000-4000-8000-000000000006', '2025d4d9-0382-4649-99e4-155377357429', 'dfa37227-dc91-4de4-bead-e1f787272814', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', '图表类算子', 'group', '折线/柱状/饼图/散点等图表算子子类'),
    ('d0000000-0000-4000-8000-000000000007', '2025d4d9-0382-4649-99e4-155377357429', 'dfa37227-dc91-4de4-bead-e1f787272814', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', '地图类算子', 'group', '地理可视化相关算子子类'),
    ('d0000000-0000-4000-8000-000000000008', '2025d4d9-0382-4649-99e4-155377357429', 'dfa37227-dc91-4de4-bead-e1f787272814', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', '数据集市', 'org', '可视化算子分类的组织来源'),
    ('d0000000-0000-4000-8000-000000000009', '2025d4d9-0382-4649-99e4-155377357429', 'dfa37227-dc91-4de4-bead-e1f787272814', '588e5ef2-dabc-4772-a22c-3fa666fd7dd5', '实体解析负责人', 'person', '负责解析数据集市算子全集')
ON CONFLICT (id) DO NOTHING;

INSERT INTO graph_relations (id, tenant_id, source_entity_id, target_entity_id, relation_type, detail) VALUES
    ('d1000000-0000-4000-8000-000000000001', '2025d4d9-0382-4649-99e4-155377357429', 'd0000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000003', '属于', '{"note": "通用算子属于业务算子分类"}'),
    ('d1000000-0000-4000-8000-000000000002', '2025d4d9-0382-4649-99e4-155377357429', 'd0000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000001', '区别于', '{"note": "业务算子与可视化算子并列"}'),
    ('d1000000-0000-4000-8000-000000000003', '2025d4d9-0382-4649-99e4-155377357429', 'd0000000-0000-4000-8000-000000000004', 'd0000000-0000-4000-8000-000000000001', '界定', '{"note": "分类范围界定可视化算子全集"}'),
    ('d1000000-0000-4000-8000-000000000004', '2025d4d9-0382-4649-99e4-155377357429', 'd0000000-0000-4000-8000-000000000005', 'd0000000-0000-4000-8000-000000000004', '排除于', '{"note": "系统算子不纳入分类范围"}'),
    ('d1000000-0000-4000-8000-000000000005', '2025d4d9-0382-4649-99e4-155377357429', 'd0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000006', '包含', '{"note": "可视化算子包含图表类算子"}'),
    ('d1000000-0000-4000-8000-000000000006', '2025d4d9-0382-4649-99e4-155377357429', 'd0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000007', '包含', '{"note": "可视化算子包含地图类算子"}'),
    ('d1000000-0000-4000-8000-000000000007', '2025d4d9-0382-4649-99e4-155377357429', 'd0000000-0000-4000-8000-000000000006', 'd0000000-0000-4000-8000-000000000003', '属于', '{"note": "图表类算子属于业务算子"}')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- M6 使用统计 (dataset_queries: KB 调用量 + 时间趋势 + 来源分布)
-- source: app / hit_testing; created_by_role: account / end_user
-- 时间跨度近 30 天，便于趋势图展示
-- ============================================================
INSERT INTO dataset_queries (dataset_id, content, source, source_app_id, created_by_role, created_by, created_at) VALUES
    ('dfa37227-dc91-4de4-bead-e1f787272814', '可视化算子分类', 'app', NULL, 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '29 days'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '通用算子列表', 'app', NULL, 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '29 days'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '何种算子纳入分类', 'hit_testing', NULL, 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '28 days'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '系统算子是否纳入', 'hit_testing', NULL, 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '26 days'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '图表类算子举例', 'app', NULL, 'end_user', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '24 days'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '可视化算子全集', 'app', NULL, 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '22 days'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '地图类算子分类', 'hit_testing', NULL, 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '20 days'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '折线图算子', 'app', NULL, 'end_user', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '18 days'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '柱状图算子', 'app', NULL, 'end_user', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '17 days'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '饼图算子', 'app', NULL, 'end_user', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '16 days'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '散点图算子', 'hit_testing', NULL, 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '14 days'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '纺织业可视化算子', 'app', NULL, 'end_user', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '12 days'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '通用业务算子全集', 'app', NULL, 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '10 days'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '数据集市算子来源', 'hit_testing', NULL, 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '8 days'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '实验室算子', 'app', NULL, 'end_user', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '6 days'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '可视化算子分类建议', 'app', NULL, 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '4 days'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '地图可视化算子', 'app', NULL, 'end_user', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '3 days'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '业务算子与可视化算子区别', 'hit_testing', NULL, 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '2 days'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '分类范围界定', 'app', NULL, 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '1 day'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '可视化算子数量', 'app', NULL, 'end_user', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '1 day'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '全部算子分类统计', 'hit_testing', NULL, 'account', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '3 hours'),
    ('dfa37227-dc91-4de4-bead-e1f787272814', '可视化算子介绍了什么', 'app', NULL, 'end_user', 'a431f6a0-67f7-480a-bdde-8ad60df5ac70', now() - interval '1 hour')
ON CONFLICT DO NOTHING;

COMMIT;
