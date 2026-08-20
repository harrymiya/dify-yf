# Next.js → Vite/Vinext 改造计划

## 一、改造目标

- 使用 Vite 作为开发与构建工具。
- 使用 Vinext 保留现有 App Router、SSR、Server Components、动态路由和并行路由能力。
- 重新适配开发期 API、Cookie、CSRF、SSE 和 WebSocket 代理。
- 保留 Next.js 作为迁移期回退方案，稳定后再移除。

## 二、现有基础

项目已有：

- `web/vite.config.ts`
- `web/dev-proxy.config.ts`
- Vinext 开发与构建脚本
- `web/next/` Next 兼容层
- 独立 Dev Proxy 服务

当前前端仍大量依赖 Next.js API 和 App Router 文件约定，因此不建议直接改为纯 Vite SPA。

## 三、目标开发架构

```text
浏览器
  │ 同源请求 localhost:3000
  ▼
Vinext/Vite :3000
  │ Vite server.proxy
  ▼
Dev Proxy :5002
  │ Cookie / CSRF / 路由分流
  ▼
Dify API :5001
```

## 四、开发代理配置

### 代理路径

Vite 需要代理：

```text
/console/api
/api
/socket.io
/admin-api
/inner/api
/mfa
/scim
/v1/*
```

其中 `/socket.io` 必须支持 WebSocket upgrade。浏览器只访问 `localhost:3000`，Cookie 和 CSRF 由 Dev Proxy 统一处理。

### 环境变量

```dotenv
NEXT_PUBLIC_API_PREFIX=/console/api
NEXT_PUBLIC_PUBLIC_API_PREFIX=/api
NEXT_PUBLIC_SOCKET_URL=ws://localhost:3000

DEV_PROXY_PORT=5002
DEV_PROXY_TARGET=http://127.0.0.1:5001
DEV_PROXY_PUBLIC_TARGET=http://127.0.0.1:5001
SERVER_CONSOLE_API_URL=http://127.0.0.1:5002
```

## 五、分阶段改造

### 阶段 1：建立迁移基线

- 记录 Next 与 Vinext 的启动、构建结果。
- 验证登录、Token 刷新、应用、知识库、工作流和分享页面。
- 保留 Next 启动命令作为回退。
- 整理 Vinext 当前兼容问题。

### 阶段 2：切换开发入口

修改根目录 `package.json`、`web/package.json` 和开发启动脚本：

```json
{
  "dev": "vinext dev",
  "dev:next": "next dev",
  "build": "vinext build",
  "start": "vinext start"
}
```

要求：

- `pnpm dev` 默认启动 Vinext。
- 保留 `pnpm dev:next`。
- 禁止 `pnpm dev` 与启动脚本递归调用。
- 根目录命令统一管理 Web 和 Dev Proxy。

### 阶段 3：迁移 Next 配置

| Next 配置 | Vite/Vinext 方案 |
| --- | --- |
| `redirects` | Vinext 路由重定向 |
| `rewrites` | Vite `server.proxy` |
| `basePath` | Vite/Vinext `base` |
| MDX | Vite MDX 插件 |
| `transpilePackages` | `optimizeDeps` / `ssr.noExternal` |
| `serverExternalPackages` | Vite SSR external 配置 |
| Turbopack 插件 | Vite 插件 |
| source map | Vite build 配置 |

### 阶段 4：保留兼容层

继续使用 `web/next/` 下的兼容模块，并禁止业务代码新增直接的 `next/*` 引用。需要扩展能力时，优先修改兼容层。

### 阶段 5：验证服务端和路由能力

重点验证：

- Server Components
- `cookies()`、`headers()`、`redirect()`、`notFound()`
- Metadata
- 动态路由和 Catch-all 路由
- 并行路由 `@detailSidebar`
- Route Handler
- SSR 请求中的绝对 API 地址
- SSE 流式响应
- WebSocket
- MDX 和静态资源

重点页面：

- `/apps`
- `/signin`
- `/datasets`
- `/workflow`
- `/plugins`
- `/chat`
- `/agent`
- `/auth/refresh`

### 阶段 6：迁移生产构建

修改 Docker 构建和入口：

- 只执行 `vinext build`。
- 只复制 Vinext 产物。
- 删除 `.next/standalone` 复制逻辑。
- 入口直接启动 Vinext server。
- 删除 `EXPERIMENTAL_ENABLE_VINEXT`。
- 保留运行时环境变量注入。

### 阶段 7：清理 Next 依赖

确认 Vinext 构建、Docker 启动、关键路由、SSR、SSE、WebSocket 和测试均稳定后，再删除 Next 构建脚本、Docker 产物、依赖和无用兼容代码。

## 六、验证命令

```bash
pnpm --filter dify-web type-check
pnpm --filter dify-web test
pnpm --filter dify-web build
pnpm --filter dify-web build:vinext
```

功能验证：

- 登录与退出
- Token 刷新
- Cookie 与 CSRF
- 应用列表
- 知识库
- 工作流
- 插件管理
- 分享页面
- SSE
- WebSocket
- 动态路由刷新
- Docker 启动

## 七、风险控制

- 不一次性删除 Next.js。
- 不直接重写现有业务路由。
- 先迁移代理，再迁移构建。
- 保留 `dev:next` 回退入口。
- 每个阶段单独验证。
- 代理异常必须显式报错，不允许静默降级。
- 不修改无关业务逻辑。

## 八、AI 执行提示词

```text
你是一名资深 React、Vite、Vinext 和 Next.js 架构工程师。

请在 Dify monorepo 中完成前端从 Next.js 默认运行时迁移到 Vinext/Vite 的改造。

项目路径：
- 仓库：/mnt/data/code/dify
- 前端：/mnt/data/code/dify/web

目标：
1. 使用 Vinext 保留现有 App Router、SSR、Server Components、动态路由和并行路由语义。
2. Vite 成为默认开发和生产构建工具。
3. Next.js 仅作为迁移期回退，稳定后再移除。
4. 重新适配开发期 API、Cookie、CSRF、SSE 和 WebSocket 代理。
5. 浏览器只访问 localhost:3000 下的同源相对路径。

代理拓扑：
- Vinext/Vite：localhost:3000
- Dev Proxy：127.0.0.1:5002
- Dify API：127.0.0.1:5001
- Vite 将 /console/api、/api、/socket.io 及企业接口代理到 Dev Proxy。
- Dev Proxy 再转发到 Dify API。
- /socket.io 必须支持 WebSocket upgrade。
- 必须保留现有 Cookie rewrite 和 CSRF header 行为。

实施要求：
1. 先阅读仓库根目录 AGENTS.md 和 web/AGENTS.md。
2. 检查当前未提交改动，不得覆盖用户已有修改。
3. 基于现有 web/vite.config.ts 和 Vinext 集成继续改造，不要新建另一套 Vite 应用。
4. 修改根 package.json 和 web/package.json：
   - dev 默认启动 Vinext + Dev Proxy
   - 保留 dev:next 作为临时回退
   - build 切换到 vinext build
   - start 使用 Vinext 生产服务
5. 将 next.config.ts 中的 redirects、rewrites、basePath、MDX、external 和构建行为迁移到 Vinext/Vite。
6. 修复 start-web.sh，禁止脚本递归调用自身。
7. 统一开发环境变量：
   NEXT_PUBLIC_API_PREFIX=/console/api
   NEXT_PUBLIC_PUBLIC_API_PREFIX=/api
   NEXT_PUBLIC_SOCKET_URL=ws://localhost:3000
   DEV_PROXY_PORT=5002
   DEV_PROXY_TARGET=http://127.0.0.1:5001
   DEV_PROXY_PUBLIC_TARGET=http://127.0.0.1:5001
   SERVER_CONSOLE_API_URL=http://127.0.0.1:5002
8. 保留 web/next 兼容层，禁止业务代码新增直接的 next/* import。
9. 检查 Server Components、cookies、headers、redirect、notFound、metadata、route handler、动态路由和并行路由兼容性。
10. 修改 Dockerfile 和 entrypoint，只构建并运行 Vinext；确认稳定前不要删除 Next 回退代码。
11. 补充或更新与代理、路由和启动行为直接相关的测试及文档。
12. 不做无关重构，不使用 any，不吞掉异常。

验收标准：
- pnpm dev 可同时启动 Vinext 和开发代理。
- /apps 可以访问且刷新后正常。
- 登录、Token refresh、Cookie、CSRF 正常。
- SSE 和 WebSocket 正常。
- 动态路由和并行路由可直接访问。
- pnpm --filter dify-web type-check 通过。
- 相关测试通过。
- vinext build 通过。
- Docker 镜像仅包含并启动 Vinext 产物。
- 不再依赖 Next rewrites 提供开发代理。

请按以下顺序执行：
1. 现状检查
2. 分阶段修改
3. 每阶段验证
4. 最终差异总结
5. 剩余风险说明
```
