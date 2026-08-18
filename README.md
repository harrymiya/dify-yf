![cover-v5-optimized](./images/GitHub_README_if.png)

> **定制版说明**：本仓库 `dify-yf` 是从 [langgenius/dify](https://github.com/langgenius/dify) fork 的定制版本，在开源版基础上针对**企业知识库场景**新增三项定制能力（知识查询权限、知识库使用统计、知识库审计日志）。详细规划与进度见文末 **[「本 fork 定制说明」](#本-fork-定制说明)**。

<details>
<summary><b>📌 本 fork 定制说明（点开查看）</b></summary>

<br>

> 以下内容为本仓库 `dify-yf` 的定制规划文档，与上游 `langgenius/dify` 的官方 README 相互独立。

## 本 fork 定制说明

本仓库在原版 Dify 开源版基础上，围绕**企业知识库（KB）管理**进行定制开发。功能开发遵循**分支隔离**策略，各定制功能分别在独立分支上进行，避免相互干扰，待稳定后合入 `main`。

### 定制功能总览

| # | 功能 | 现状 | 定制分支 | 状态 |
|----|------|------|----------|------|
| 3️⃣ | 知识查询权限设置 | 开源版已有「角色×数据集×操作」三层 RBAC，缺**部门维度**与**文档级粒度** | `feature/kb-permission` | 规划中 |
| 4️⃣ | 知识库使用情况统计 | 无专项报表/接口，仅有 `hit_count` 等底层数据 | `feature/kb-statistics` | 规划中 |
| 5️⃣ | 日志（Log）功能 | 缺少知识库侧「问答/检索/下载/权限变更」审计日志 | `feature/kb-audit-log` | 规划中 |

### 3️⃣ 知识查询权限设置（`feature/kb-permission`）

- **目标**：实现「部门 — 角色 — 知识域/文档 — 操作」四层授权。
- **现状差距**：开源版具备「角色 × 数据集 × 操作」三层（`api/services/enterprise/rbac_service.py`、`api/core/rbac/entities.py`），`RBACResourceType` 目前仅 `app`、`dataset`，数据集 ACL 权限点完整（`dataset_preview / readonly / edit / retrieval_recall / use / document_download / delete_file / delete / access_config / api_key_manage` 等）。
- **待补充**：
  - 「部门」维度（组织架构/部门树作为权限主体，目前 `department/team` 仅是文档元数据字段）。
  - 「知识域/文档」级资源粒度（目前只能整库授权）。

### 4️⃣ 知识库使用情况统计（`feature/kb-statistics`）

- **目标**：提供接口调用使用量、知识库调用情况等聚合统计报表。
- **现状差距**：无专项报表/接口；仅有 `DocumentSegment.hit_count`（`api/services/dataset_service.py`）、`hit_testing` 检索试运行及应用侧 `metadata.usage` 等底层数据可支撑。
- **待补充**：基于 `hit_count`、检索日志等实现「知识库调用量/使用情况」聚合统计与接口。

### 5️⃣ 日志（Log）功能（`feature/kb-audit-log`）

- **目标**：提供问答、检索、下载、权限变更、系统运行的**知识库审计日志**查询。
- **现状差距**：仅有应用（App）级日志（对话/消息/工作流）；`operation_service.py` 仅做 UTM 计费上报，非审计日志。
- **待补充**：新增知识库操作审计日志（检索/下载/权限变更等）及查询接口。

### 分支结构

```text
main                        # 主干，跟随上游源库同步
├── feature/kb-permission   # 3️⃣ 知识查询权限设置
├── feature/kb-statistics   # 4️⃣ 知识库使用情况统计
└── feature/kb-audit-log    # 5️⃣ 日志（审计）
```

### 同步上游

```bash
git fetch upstream
git merge upstream/main
```

---

*以下为上游 `langgenius/dify` 官方 README。*
</details>

<p align="center">
  <a href="https://cloud.dify.ai">Dify Cloud</a> ·
  <a href="https://docs.dify.ai/getting-started/install-self-hosted">Self-hosting</a> ·
  <a href="https://docs.dify.ai">Documentation</a> ·
  <a href="https://dify.ai/pricing">Dify edition overview</a>
</p>

<p align="center">
    <a href="https://dify.ai" target="_blank">
        <img alt="Static Badge" src="https://img.shields.io/badge/Product-F04438"></a>
    <a href="https://dify.ai/pricing" target="_blank">
        <img alt="Static Badge" src="https://img.shields.io/badge/free-pricing?logo=free&color=%20%23155EEF&label=pricing&labelColor=%20%23528bff"></a>
    <a href="https://discord.gg/FngNHpbcY7" target="_blank">
        <img src="https://img.shields.io/discord/1082486657678311454?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb"
            alt="chat on Discord"></a>
    <a href="https://reddit.com/r/difyai" target="_blank">
        <img src="https://img.shields.io/reddit/subreddit-subscribers/difyai?style=plastic&logo=reddit&label=r%2Fdifyai&labelColor=white"
            alt="join Reddit"></a>
    <a href="https://twitter.com/intent/follow?screen_name=dify_ai" target="_blank">
        <img src="https://img.shields.io/twitter/follow/dify_ai?logo=X&color=%20%23f5f5f5"
            alt="follow on X(Twitter)"></a>
    <a href="https://www.linkedin.com/company/langgenius/" target="_blank">
        <img src="https://custom-icon-badges.demolab.com/badge/LinkedIn-0A66C2?logo=linkedin-white&logoColor=fff"
            alt="follow on LinkedIn"></a>
    <a href="https://hub.docker.com/u/langgenius" target="_blank">
        <img alt="Docker Pulls" src="https://img.shields.io/docker/pulls/langgenius/dify-web?labelColor=%20%23FDB062&color=%20%23f79009"></a>
    <a href="https://github.com/langgenius/dify/graphs/commit-activity" target="_blank">
        <img alt="Commits last month" src="https://img.shields.io/github/commit-activity/m/langgenius/dify?labelColor=%20%2332b583&color=%20%2312b76a"></a>
    <a href="https://github.com/langgenius/dify/" target="_blank">
        <img alt="Issues closed" src="https://img.shields.io/github/issues-search?query=repo%3Alanggenius%2Fdify%20is%3Aclosed&label=issues%20closed&labelColor=%20%237d89b0&color=%20%235d6b98"></a>
    <a href="https://github.com/langgenius/dify/discussions/" target="_blank">
        <img alt="Discussion posts" src="https://img.shields.io/github/discussions/langgenius/dify?labelColor=%20%239b8afb&color=%20%237a5af8"></a>
    <a href="https://insights.linuxfoundation.org/project/langgenius-dify" target="_blank">
        <img alt="LFX Health Score" src="https://insights.linuxfoundation.org/api/badge/health-score?project=langgenius-dify"></a>
    <a href="https://insights.linuxfoundation.org/project/langgenius-dify" target="_blank">
        <img alt="LFX Contributors" src="https://insights.linuxfoundation.org/api/badge/contributors?project=langgenius-dify"></a>
    <a href="https://insights.linuxfoundation.org/project/langgenius-dify" target="_blank">
        <img alt="LFX Active Contributors" src="https://insights.linuxfoundation.org/api/badge/active-contributors?project=langgenius-dify"></a>
</p>

<p align="center">
  <a href="./README.md"><img alt="README in English" src="https://img.shields.io/badge/English-d9d9d9"></a>
  <a href="./docs/zh-TW/README.md"><img alt="繁體中文文件" src="https://img.shields.io/badge/繁體中文-d9d9d9"></a>
  <a href="./docs/zh-CN/README.md"><img alt="简体中文文件" src="https://img.shields.io/badge/简体中文-d9d9d9"></a>
  <a href="./docs/ja-JP/README.md"><img alt="日本語のREADME" src="https://img.shields.io/badge/日本語-d9d9d9"></a>
  <a href="./docs/es-ES/README.md"><img alt="README en Español" src="https://img.shields.io/badge/Español-d9d9d9"></a>
  <a href="./docs/fr-FR/README.md"><img alt="README en Français" src="https://img.shields.io/badge/Français-d9d9d9"></a>
  <a href="./docs/tlh/README.md"><img alt="README tlhIngan Hol" src="https://img.shields.io/badge/Klingon-d9d9d9"></a>
  <a href="./docs/ko-KR/README.md"><img alt="README in Korean" src="https://img.shields.io/badge/한국어-d9d9d9"></a>
  <a href="./docs/ar-SA/README.md"><img alt="README بالعربية" src="https://img.shields.io/badge/العربية-d9d9d9"></a>
  <a href="./docs/tr-TR/README.md"><img alt="Türkçe README" src="https://img.shields.io/badge/Türkçe-d9d9d9"></a>
  <a href="./docs/vi-VN/README.md"><img alt="README Tiếng Việt" src="https://img.shields.io/badge/Ti%E1%BA%BFng%20Vi%E1%BB%87t-d9d9d9"></a>
  <a href="./docs/de-DE/README.md"><img alt="README in Deutsch" src="https://img.shields.io/badge/German-d9d9d9"></a>
  <a href="./docs/it-IT/README.md"><img alt="README in Italiano" src="https://img.shields.io/badge/Italiano-d9d9d9"></a>
  <a href="./docs/pt-BR/README.md"><img alt="README em Português do Brasil" src="https://img.shields.io/badge/Portugu%C3%AAs%20do%20Brasil-d9d9d9"></a>
  <a href="./docs/sl-SI/README.md"><img alt="README Slovenščina" src="https://img.shields.io/badge/Sloven%C5%A1%C4%8Dina-d9d9d9"></a>
  <a href="./docs/bn-BD/README.md"><img alt="README in বাংলা" src="https://img.shields.io/badge/বাংলা-d9d9d9"></a>
  <a href="./docs/hi-IN/README.md"><img alt="README in हिन्दी" src="https://img.shields.io/badge/Hindi-d9d9d9"></a>
</p>

Dify is an open-source LLM app development platform. Its intuitive interface combines AI workflow, RAG pipeline, agent capabilities, model management, observability features (including [Opik](https://www.comet.com/docs/opik/integrations/dify), [Langfuse](https://docs.langfuse.com), and [Arize Phoenix](https://docs.arize.com/phoenix)) and more, letting you quickly go from prototype to production. Here's a list of the core features:

## Quick start

> Before installing Dify, make sure your machine meets the following minimum system requirements:
>
> - CPU >= 2 Core
> - RAM >= 4 GiB

<br/>

The easiest way to start the Dify server is through [Docker Compose](docker/docker-compose.yaml). Before running Dify with the following commands, make sure that [Docker](https://docs.docker.com/get-docker/) and Docker Compose v2.24.0 or later are installed on your machine:

```bash
cd dify
cd docker
cp .env.example .env
docker compose up -d
```

After running, you can access the Dify dashboard in your browser at [http://localhost/install](http://localhost/install) and start the initialization process.

#### Seeking help

Please refer to our [FAQ](https://docs.dify.ai/getting-started/install-self-hosted/faqs) if you encounter problems setting up Dify. Reach out to [the community and us](#community--contact) if you are still having issues.

> If you'd like to contribute to Dify or do additional development, refer to our [guide to deploying from source code](https://docs.dify.ai/getting-started/install-self-hosted/local-source-code)

## Key features

**1. Workflow**:
Build and test powerful AI workflows on a visual canvas, leveraging all the following features and beyond.

**2. Comprehensive model support**:
Seamless integration with hundreds of proprietary / open-source LLMs from dozens of inference providers and self-hosted solutions, covering GPT, Mistral, Llama3, and any OpenAI API-compatible models. A full list of supported model providers can be found [here](https://docs.dify.ai/getting-started/readme/model-providers).

![providers-v5](https://github.com/langgenius/dify/assets/13230914/5a17bdbe-097a-4100-8363-40255b70f6e3)

**3. Prompt IDE**:
Intuitive interface for crafting prompts, comparing model performance, and adding additional features such as text-to-speech to a chat-based app.

**4. RAG Pipeline**:
Extensive RAG capabilities that cover everything from document ingestion to retrieval, with out-of-box support for text extraction from PDFs, PPTs, and other common document formats.

**5. Agent capabilities**:
You can define agents based on LLM Function Calling or ReAct, and add pre-built or custom tools for the agent. Dify provides 50+ built-in tools for AI agents, such as Google Search, DALL·E, Stable Diffusion and WolframAlpha.

**6. LLMOps**:
Monitor and analyze application logs and performance over time. You could continuously improve prompts, datasets, and models based on production data and annotations.

**7. Backend-as-a-Service**:
All of Dify's offerings come with corresponding APIs, so you could effortlessly integrate Dify into your own business logic.

## Using Dify

- **Cloud <br/>**
  We host a [Dify Cloud](https://dify.ai) service for anyone to try with zero setup. It provides all the capabilities of the self-deployed version, and includes 200 free GPT-4 calls in the sandbox plan. If you run into issues with Dify Cloud, [contact our Cloud support team](mailto:cloud@dify.ai?subject=%5BGitHub%5DDify%20Cloud%20Support).

- **Self-hosting Dify Community Edition<br/>**
  Quickly get Dify running in your environment with this [starter guide](#quick-start).
  Use our [documentation](https://docs.dify.ai) for further references and more in-depth instructions.

- **Dify for enterprise / organizations<br/>**
  We provide additional enterprise-centric features. [Send us an email](mailto:business@dify.ai?subject=%5BGitHub%5DBusiness%20License%20Inquiry) to discuss your enterprise needs. <br/>

## Staying ahead

Star Dify on GitHub and be instantly notified of new releases.

![star-us](https://github.com/langgenius/dify/assets/13230914/b823edc1-6388-4e25-ad45-2f6b187adbb4)

## Advanced Setup

### Custom configurations

If you need to customize the configuration, edit `docker/.env`. The essential startup defaults live in [`docker/.env.example`](docker/.env.example), and optional advanced variables are split under `docker/envs/` by theme. After making any changes, re-run `docker compose up -d` from the `docker` directory. You can find the full list of available environment variables [here](https://docs.dify.ai/getting-started/install-self-hosted/environments).

### Metrics Monitoring with Grafana

Import the dashboard to Grafana, using Dify's PostgreSQL database as data source, to monitor metrics in granularity of apps, tenants, messages, and more.

- [Grafana Dashboard by @bowenliang123](https://github.com/bowenliang123/dify-grafana-dashboard)

### Deployment with Kubernetes

If you'd like to configure a highly available setup, there are community-contributed [Helm Charts](https://helm.sh/) and YAML files which allow Dify to be deployed on Kubernetes.

- [Helm Chart by @LeoQuote](https://github.com/douban/charts/tree/master/charts/dify)
- [Helm Chart by @BorisPolonsky](https://github.com/BorisPolonsky/dify-helm)
- [Helm Chart by @magicsong](https://github.com/magicsong/ai-charts)
- [YAML file by @Winson-030](https://github.com/Winson-030/dify-kubernetes)
- [YAML file by @wyy-holding](https://github.com/wyy-holding/dify-k8s)
- [🚀 NEW! YAML files (Supports Dify v1.6.0) by @Zhoneym](https://github.com/Zhoneym/DifyAI-Kubernetes)

#### Using Terraform for Deployment

Deploy Dify to Cloud Platform with a single click using [terraform](https://www.terraform.io/)

##### Azure Global

- [Azure Terraform by @nikawang](https://github.com/nikawang/dify-azure-terraform)

##### Google Cloud

- [Google Cloud Terraform by @sotazum](https://github.com/DeNA/dify-google-cloud-terraform)

#### Using AWS CDK for Deployment

Deploy Dify to AWS with [CDK](https://aws.amazon.com/cdk/)

##### AWS

- [AWS CDK by @KevinZhao (EKS based)](https://github.com/aws-samples/solution-for-deploying-dify-on-aws)
- [AWS CDK by @tmokmss (ECS based)](https://github.com/aws-samples/dify-self-hosted-on-aws)

#### Using Alibaba Cloud Computing Nest

Quickly deploy Dify to Alibaba cloud with [Alibaba Cloud Computing Nest](https://computenest.console.aliyun.com/service/instance/create/default?type=user&ServiceName=Dify%E7%A4%BE%E5%8C%BA%E7%89%88)

#### Using Alibaba Cloud Data Management

One-Click deploy Dify to Alibaba Cloud with [Alibaba Cloud Data Management](https://www.alibabacloud.com/help/en/dms/dify-in-invitational-preview/)

#### Deploy to AKS with Azure Devops Pipeline

One-Click deploy Dify to AKS with [Azure Devops Pipeline Helm Chart by @LeoZhang](https://github.com/Ruiruiz30/Dify-helm-chart-AKS)

## Contributing

For those who'd like to contribute code, see our [Contribution Guide](https://github.com/langgenius/dify/blob/main/CONTRIBUTING.md).
At the same time, please consider supporting Dify by sharing it on social media and at events and conferences.

> We are looking for contributors to help translate Dify into languages other than Mandarin or English. If you are interested in helping, please see the [i18n README](https://github.com/langgenius/dify/blob/main/web/i18n-config/README.md) for more information, and leave us a comment in the `global-users` channel of our [Discord Community Server](https://discord.gg/8Tpq4AcN9c).

## Community & contact

- [GitHub Discussion](https://github.com/langgenius/dify/discussions). Best for: sharing feedback and asking questions.
- [GitHub Issues](https://github.com/langgenius/dify/issues). Best for: bugs you encounter using Dify.AI, and feature proposals. See our [Contribution Guide](https://github.com/langgenius/dify/blob/main/CONTRIBUTING.md).
- [Discord](https://discord.gg/FngNHpbcY7). Best for: sharing your applications and hanging out with the community.
- [X(Twitter)](https://twitter.com/dify_ai). Best for: sharing your applications and hanging out with the community.

**Contributors**

<a href="https://github.com/langgenius/dify/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=langgenius/dify" />
</a>

## Star History

<a href="https://star-history.dera.page/#langgenius/dify&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://star-history.dera.page/svg?repos=langgenius/dify&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://star-history.dera.page/svg?repos=langgenius/dify&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://star-history.dera.page/svg?repos=langgenius/dify&type=date&legend=top-left" />
 </picture>
</a>

## Security disclosure

To protect your privacy, please avoid posting security issues on GitHub. Instead, report issues to security@dify.ai, and our team will respond with detailed answer.

## License

This repository is licensed under the [Dify Open Source License](LICENSE), based on Apache 2.0 with additional conditions.
