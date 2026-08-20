# Dify 本地开发环境指南（前端 + 后端 + 中间件）

本仓库在本地开发模式下运行的完整指南，包括启动命令、依赖中间件管理，
以及本机针对"配置一般"硬件的性能优化与已知问题。

---

## 1. 快速启动命令

在仓库根目录执行：

| 命令 | 作用 | 端口 |
|------|------|------|
| `npm run dev` | 启动前端（Next.js dev server） | `3000` |
| `npm run py` | 启动后端 API + 中间件 + 迁移 | API `5001`，插件 daemon `5002` |

> 说明：`npm run dev` / `npm run py` 分别对应 `dev/start-web.sh` 和
> `dev/start-backend.sh`。启动脚本做了大量优化与容错，**请优先使用这两个
> 入口**，不要直接跑裸的 `next dev` / `python -m app`。

### 推荐的启动顺序

1. 先跑 `npm run py`（确保中间件容器和后端就绪，约 1~2 分钟）
2. 再跑 `npm run dev`（前端，因首次冷编译可能等待数十秒）
3. 浏览器访问 http://localhost:3000

---

## 2. 中间件容器（Docker）管理

Dify 本地开发依赖以下 Docker 中间件容器：

- `db_postgres`（PostgreSQL 15）
- `redis`（Redis 6）
- `weaviate`（向量数据库）
- `plugin_daemon`（插件守护进程，端口 5002）

### 启动方式

这些容器**不会随操作系统自动启动**，统一由 `npm run py` 拉起
（`start-backend.sh` 执行 `docker compose up -d --no-recreate`）。

如需手动管理：

```bash
cd docker
# 启动中间件
docker compose -f docker-compose.middleware.yaml --env-file middleware.env -p docker up -d --no-recreate db_postgres redis weaviate plugin_daemon
# 查看状态
docker ps --filter "label=com.docker.compose.project=docker"
# 停止（不删除）
docker compose -f docker-compose.middleware.yaml --env-file middleware.env -p docker stop db_postgres redis weaviate plugin_daemon
# 彻底删除容器（下次启动会自动重建）
docker compose -f docker-compose.middleware.yaml --env-file middleware.env -p docker down
```

### 自启策略（重要）

`docker-compose.middleware.yaml` 中所有服务的 `restart` 策略已从 `always`
改为 `"no"`（提交 `cfba569834`）。因此：

- 系统重启后，Docker 守卫进程会启动，但 **Dify 中间件容器不会自动拉起**
- 中间件只在执行 `npm run py`（或手动 `docker compose up`）时启动
- 若容器异常退出，不会自动重启，需要重新 `npm run py`

> 注：Docker 服务本身（`docker.service`）仍为开机自启，这是预期行为。
> 若你希望连 Docker 服务也不自启，需额外执行：
> `sudo systemctl disable docker.service docker.socket`（之后每次开发前手动
> `sudo systemctl start docker`）。默认不推荐这样做。

---

## 3. 前端性能优化（本机硬件配置一般）

`dev/start-web.sh` 针对"硬件配置一般"的机器做了以下优化（已提交）：

| 提交 | 优化内容 |
|------|---------|
| `7286e7773f` | 禁用 Turbopack 磁盘持久化缓存（`TURBOPACK_CACHE=0`）；移除 ReactScanLoader；移除 Vite 遗留的 code-inspector 插件 |
| `b8d400b5a9` | 启动时自动清理 `.next/dev` 编译残留，防止膨胀到数十 GB 导致冷启动卡死 |
| `76bad3c687` | 移除右下角 Agentation 调试浮层 |

### 为什么这样做 / 已知行为

- **`TURBOPACK_CACHE=0`**：Next.js 16 的 Turbopack 磁盘缓存在本机易膨胀到
  10GB+，且冷启动触发超长 DB compaction（50s~66s），导致页面"打不开"。
  禁用后改为纯内存缓存 + 每次启动清理，行为可预测。
- **"每个菜单第一次点击要等 6~15s，之后秒开"**：这是 `next dev` 模式下
  on-demand 冷编译的固有现象（`TURBOPACK_CACHE=0` 下每个路由首次访问都要
  现场编译）。后续访问同一路由走内存缓存，约 0.2~1s。
- **`.next/dev` 可能达 4GB+**：已由启动脚本在每次 `npm run dev` 时自动清理。

> 该优化目标是开发体验，**不影响生产构建**（生产仍走 `next build` 完整产物）。

---

## 4. 插件市场（Marketplace）功能已关闭

为避免开发时控制台出现插件市场的 CORS 报错，本机后端已关闭市场功能。

修改位置：`api/.env`

```env
MARKETPLACE_ENABLED=false
```

效果：
- 后端 `system-features` 返回 `enable_marketplace: false`
- 前端不再渲染"从市场安装"等区块，不发起任何插件市场请求
- 控制台不再出现 `http://localhost:5002/api/...` 的 CORS 红色报错

> **注意**：`api/.env` 是 git 忽略文件（未提交到仓库）。若克隆到新环境
> 或有人改动该文件，需重新确认此配置。如需恢复市场功能，改回 `true` 并
> 重启后端即可。

---

## 5. 环境变量（`.env.local`）

`web/.env.local`（git 忽略）包含前端本地开发的核心配置：

```env
NEXT_PUBLIC_API_PREFIX=/console/api
NEXT_PUBLIC_PUBLIC_API_PREFIX=/api
NEXT_PUBLIC_SOCKET_URL=ws://localhost:3000
SERVER_CONSOLE_API_URL=http://127.0.0.1:5001
```

> 注意：`SERVER_CONSOLE_API_URL` 用于 SSR 请求，**必须指向实际的
> 后端地址**（5001）。早期曾误指向 dev-proxy 的 5010，导致 SSR 请求打到
> 不存在的端口而等待超时。

API 转发由 `web/next.config.ts` 的 `rewrites` 在 dev 下完成（`/console/api`、
`/api`、`/socket.io` → 本地后端 5001），保证浏览器始终同源、不触发 CORS。

---

## 6. 后端启动注意事项

`dev/start-backend.sh` 会自动：

1. 确保中间件容器已启动（见上文）
2. 等待 plugin daemon（5002）就绪
3. 执行 `uv run flask db upgrade`（数据库迁移）
4. 启动 API：`uv run python -m app`（端口 5001）

特别注意（脚本已处理）：
- **`ALL_PROXY` 必须清空**：系统全局代理（socks://127.0.0.1:7890）会破坏
  后端 httpx 请求，脚本已自动 `unset`。
- `uv` 位于 `/mnt/data/.hermes/bin`，脚本已加入 PATH。

后端当前进程：`api/.venv/bin/python3 -m app`（实际以 root 运行在 5001）。

---

## 7. 常见问题排查

### 页面打开很慢 / 菜单切换要 6~15 秒
正常的首次冷编译。同一路由二次访问即秒开。若重启后所有路由都慢，属预期
（无磁盘缓存）。如遇异常慢（几分钟无响应），检查是否 `.next` 缓存膨胀
（本机已通过启动自动清理规避）。

### 控制台报 CORS / `localhost:5002` 请求失败
插件市场功能已关闭（见第 4 节），正常情况下不应再出现。若出现，确认
`api/.env` 中 `MARKETPLACE_ENABLED=false` 且后端已重启。

### 中间件容器自己启动了
检查容器 restart 策略是否为 `no`：
```bash
docker inspect --format '{{.Name}} {{.HostConfig.RestartPolicy.Name}}' \
  docker-db_postgres-1 docker-redis-1 docker-weaviate-1 docker-plugin_daemon-1
```
若为 `always`，执行 `docker update --restart=no <容器名>` 并同步 compose 文件。

### 前端 3000 端口被占
`start-web.sh` 自动检测，若 3000 被占会回退到 3001。

---

## 8. 相关脚本入口

| 文件 | 说明 |
|------|------|
| `dev/start-web.sh` | 前端启动（含清理 `.next/dev`、禁磁盘缓存、端口回退） |
| `dev/start-backend.sh` | 后端 + 中间件 + 迁移 + API |
| `docker/docker-compose.middleware.yaml` | 中间件容器定义（restart: no） |
| `web/next.config.ts` | Next.js 配置 + dev rewrites 代理 |
| `web/.env.local` | 前端本地环境变量（git 忽略） |
| `api/.env` | 后端环境变量（git 忽略，含 MARKETPLACE_ENABLED） |
