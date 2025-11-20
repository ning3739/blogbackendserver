# Backend Server

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/) [![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/) [![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge&logo=opensourceinitiative&logoColor=white)](LICENSE)

一个基于 FastAPI 的现代化博客后端管理系统，采用异步架构设计，支持多语言、支付、媒体管理等丰富功能。

[特性](#-特性) • [技术栈](#-技术栈) • [快速开始](#-快速开始) • [项目结构](#-项目结构) • [API 文档](#-api-文档) • [部署](#-部署)

</div>

---

## 📋 目录

- [特性](#-特性)
- [技术栈](#-技术栈)
- [系统架构](#-系统架构)
- [快速开始](#-快速开始)
- [项目结构](#-项目结构)
- [配置说明](#-配置说明)
- [API 文档](#-api-文档)
- [数据库迁移](#-数据库迁移)
- [异步任务](#-异步任务)
- [部署指南](#-部署指南)
- [开发指南](#-开发指南)
- [测试](#-测试)
- [常见问题](#-常见问题)
- [贡献指南](#-贡献指南)
- [许可证](#-许可证)

## ✨ 特性

### 核心功能

- 🔐 **完整的认证系统**

  - 邮箱验证码登录/注册
  - OAuth 社交账号登录（Google、GitHub 等）
  - JWT 双令牌机制（访问令牌 + 刷新令牌）
  - Argon2 密码加密
  - CSRF 保护

- 📝 **博客管理系统**

  - 多语言支持（中文/英文）
  - 富文本内容编辑
  - 草稿/发布状态管理
  - 标签分类系统
  - SEO 优化支持
  - 文章封面管理

- 📁 **媒体管理**

  - AWS S3 文件存储
  - 图片水印自动添加
  - 缩略图自动生成
  - 文件分类管理
  - 用户媒体库

- 💳 **支付系统**

  - Stripe 支付集成
  - 自动生成 PDF 发票
  - 邮件发送发票
  - 支付记录管理

- 🤖 **AI 功能**

  - 内容自动翻译（阿里云通义千问）
  - 文本转语音（Azure TTS）
  - 智能内容摘要

- 📊 **数据分析**

  - 访问统计
  - 用户行为分析
  - 客户端信息收集

- 🔧 **其他功能**
  - 留言板系统
  - 友链管理
  - 项目展示
  - 订阅者管理
  - 邮件通知系统
  - 限流保护

## 🛠 技术栈

### 后端框架

- **[FastAPI](https://fastapi.tiangolo.com/)** - 高性能异步 Web 框架
- **[SQLModel](https://sqlmodel.tiangolo.com/)** - SQL 数据库的 Python ORM
- **[Pydantic](https://pydantic-docs.helpmanual.io/)** - 数据验证和设置管理
- **[Alembic](https://alembic.sqlalchemy.org/)** - 数据库迁移工具

### 数据库与缓存

- **MySQL** - 主数据库
- **Redis** - 缓存和消息队列
- **aiomysql** - 异步 MySQL 驱动

### 异步任务

- **[Celery](https://docs.celeryproject.org/)** - 分布式任务队列
- **Redis** - Celery 消息代理

### 第三方服务

- **AWS S3** - 对象存储服务
- **Stripe** - 支付处理
- **阿里云通义千问** - AI 内容翻译
- **Azure Cognitive Services** - 语音合成
- **邮件服务** - 发送通知和发票

### 开发工具

- **Docker & Docker Compose** - 容器化部署
- **Nginx** - 反向代理和负载均衡
- **Pytest** - 测试框架
- **Ruff** - Python 代码检查
- **Loguru** - 日志管理

## 🏗 系统架构

```
┌─────────────┐
│   Nginx     │  ← 反向代理 & SSL 终止
└──────┬──────┘
       │
┌──────▼──────┐
│   FastAPI   │  ← Web 应用服务器
│  (Uvicorn)  │
└──────┬──────┘
       │
       ├──────────────┬──────────────┬──────────────┐
       │              │              │              │
┌──────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐ ┌────▼─────┐
│    MySQL    │ │  Redis   │ │   AWS S3    │ │  Stripe  │
│  (数据库)   │ │ (缓存)   │ │  (存储)     │ │  (支付)  │
└─────────────┘ └────┬─────┘ └─────────────┘ └──────────┘
                     │
              ┌──────▼──────┐
              │   Celery    │  ← 异步任务处理
              │   Worker    │
              └─────────────┘
```

## 🚀 快速开始

### 前置要求

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) - 快速的 Python 包管理器
- MySQL 8.0+
- Redis 7.0+
- Docker & Docker Compose (可选)

### 本地开发安装

1. **克隆仓库**

```bash
git clone https://github.com/NING3739/blogbackendserver.git
cd blogbackendserver
```

2. **安装 uv（如果尚未安装）**

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

3. **安装依赖**

```bash
# 使用 uv 同步依赖（自动创建虚拟环境）
uv sync
```

4. **配置环境变量**

在 `secret/` 目录下创建环境配置文件：

```bash
mkdir -p secret
touch secret/.env.development  # 开发环境
touch secret/.env.production   # 生产环境
```

参考 [配置说明](#️-配置说明) 部分填写必要的环境变量。

5. **初始化数据库**

```bash
# 创建数据库（MySQL 中执行）
mysql -u root -p
CREATE DATABASE blog CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;

# 运行数据库迁移（详见"数据库迁移"章节）
uv run alembic upgrade head

# 初始化数据（可选）
uv run python script/initial_data.py
```

6. **生成 SSL 证书（开发环境）**

```bash
# 安装 mkcert（如果尚未安装）
# macOS
brew install mkcert
# 或访问 https://github.com/FiloSottile/mkcert 查看其他平台安装方式

# 安装本地 CA
mkcert -install

# 生成证书
mkdir -p certs
cd certs
mkcert 127.0.0.1 localhost
# 将生成 127.0.0.1+1-key.pem 和 127.0.0.1+1.pem
# 重命名为项目所需的文件名
mv 127.0.0.1+1-key.pem localhost-key.pem
mv 127.0.0.1+1.pem localhost.pem
cd ..
```

7. **启动开发服务器**

```bash
# 设置环境变量
export ENV=development

# 启动 FastAPI 应用
uv run python -m app.main

# 在另一个终端启动 Celery Worker
uv run celery -A app.core.celery.celery_manager.celery_app worker --loglevel=info

# 启动 Celery Beat（定时任务）
uv run celery -A app.core.celery.celery_manager.celery_app beat --loglevel=info
```

8. **访问应用**

- API 文档: https://127.0.0.1:8000/docs
- ReDoc 文档: https://127.0.0.1:8000/redoc
- 应用主页: https://127.0.0.1:8000

## 📁 项目结构

```
backend-server/
├── alembic/                    # 数据库迁移文件
│   ├── versions/              # 迁移版本
│   ├── env.py                 # Alembic 配置
│   └── script.py.mako         # 迁移脚本模板
├── app/                        # 应用主目录
│   ├── core/                  # 核心模块
│   │   ├── config/           # 配置管理
│   │   │   ├── modules/      # 配置模块（数据库、JWT、AWS等）
│   │   │   ├── base.py       # 基础配置类
│   │   │   └── settings.py   # 全局设置
│   │   ├── database/         # 数据库连接管理
│   │   ├── i18n/            # 国际化
│   │   ├── celery.py        # Celery 配置
│   │   ├── logger.py        # 日志管理
│   │   └── security.py      # 安全相关（密码、JWT）
│   ├── crud/                  # 数据库 CRUD 操作
│   │   ├── auth_crud.py
│   │   ├── blog_crud.py
│   │   ├── user_crud.py
│   │   └── ...
│   ├── decorators/            # 装饰器
│   │   └── rate_limiter.py   # 限流装饰器
│   ├── models/                # 数据模型
│   │   ├── auth_model.py
│   │   ├── blog_model.py
│   │   ├── user_model.py
│   │   └── ...
│   ├── router/                # API 路由
│   │   └── v1/               # API v1 版本
│   │       ├── auth_router.py
│   │       ├── blog_router.py
│   │       └── ...
│   ├── schemas/               # Pydantic 数据模式
│   │   ├── auth_schemas.py
│   │   ├── blog_schemas.py
│   │   └── ...
│   ├── services/              # 业务逻辑层
│   │   ├── auth_service.py
│   │   ├── blog_service.py
│   │   └── ...
│   ├── tasks/                 # Celery 异步任务
│   │   ├── backup_database_task.py
│   │   ├── generate_content_audio_task.py
│   │   ├── large_content_translation_task.py
│   │   └── ...
│   ├── utils/                 # 工具函数
│   └── main.py               # 应用入口
├── certs/                     # SSL 证书（开发环境）
├── docs/                      # 项目文档
├── logs/                      # 日志文件
├── script/                    # 脚本文件
│   ├── initial_data.py       # 初始化数据
│   ├── setup-docker.sh       # Docker 设置脚本
│   └── setup-server.sh       # 服务器设置脚本
├── secret/                    # 密钥和环境变量
│   ├── .env.development      # 开发环境配置
│   └── .env.production       # 生产环境配置
├── static/                    # 静态文件
│   ├── font/                 # 字体文件
│   ├── image/                # 图片资源
│   └── template/             # 模板文件
├── tests/                     # 测试文件
├── alembic.ini               # Alembic 配置文件
├── docker-compose.yml        # Docker Compose 配置
├── Dockerfile                # Docker 镜像构建文件
├── nginx.conf                # Nginx 配置
├── pyproject.toml            # 项目依赖配置
└── README.md                 # 项目说明文档
```

## ⚙️ 配置说明

### 环境变量

在 `secret/.env.development` 或 `secret/.env.production` 中配置以下环境变量：

#### 完整配置示例

```env
# ========================================
# 应用配置
# ========================================
APP_NAME=YourAppName

# ========================================
# 数据库配置
# ========================================
# 格式：mysql+aiomysql://username:password@host:port/database
DATABASE_URL=mysql+aiomysql://your_user:your_password@localhost:3306/your_database

# ========================================
# JWT 配置
# ========================================
JWT_SECRET_KEY=your_random_secret_key_here_at_least_32_characters

# ========================================
# 邮件配置
# ========================================
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password

# ========================================
# CORS 配置
# ========================================
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://api.yourdomain.com

# ========================================
# CSRF 配置
# ========================================
CSRF_SECRET_KEY=your_csrf_secret_key

# ========================================
# Celery 和 Redis 配置
# ========================================
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
REDIS_CONNECTION_URL=redis://localhost:6379/0

# ========================================
# OAuth 配置
# ========================================
# GitHub OAuth
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_REDIRECT_URI=https://api.yourdomain.com/api/v1/auth/github-callback

# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=https://api.yourdomain.com/api/v1/auth/google-callback

# ========================================
# 日志配置
# ========================================
LOG_TO_FILE=True
LOG_FILE_PATH=logs/app.log

# ========================================
# AWS S3 配置
# ========================================
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_BUCKET_NAME=your_bucket_name
AWS_REGION=ap-southeast-1

# ========================================
# AI 服务配置
# ========================================
# 阿里云通义千问
QWEN_API_KEY=your_qwen_api_key
QWEN_API_MAX_RETRIES=3

# Azure 语音服务
AZURE_SPEECH_KEY=your_azure_speech_key
AZURE_SPEECH_REGION=eastus

# ========================================
# Stripe 支付配置
# ========================================
STRIPE_SECRET_KEY=sk_live_your_stripe_secret_key
STRIPE_PUBLIC_KEY=pk_live_your_stripe_public_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
SUCCESS_URL=https://yourdomain.com/payment/success
CANCEL_URL=https://yourdomain.com/payment/cancel

# ========================================
# 域名和公司信息
# ========================================
DOMAIN_URL=https://api.yourdomain.com
COMPANY_NAME=YourCompanyName
COMPANY_PHONE=+1234567890
COMPANY_EMAIL=contact@yourdomain.com
```

#### 配置说明

**重要提示**：

- 🔒 **切勿将真实的生产环境配置提交到版本控制**
- 🔐 生产环境配置应存储在 GitHub Secrets 中（参考部署指南）
- 🔑 定期轮换敏感密钥

## 📖 API 文档

### 访问文档

启动服务后，访问以下地址查看 API 文档：

- **Swagger UI**: https://127.0.0.1:8000/docs
- **ReDoc**: https://127.0.0.1:8000/redoc

### API 模块

| 模块   | 路由前缀              | 描述                 |
| ------ | --------------------- | -------------------- |
| 认证   | `/api/v1/auth`        | 登录、注册、令牌刷新 |
| 用户   | `/api/v1/users`       | 用户管理             |
| 博客   | `/api/v1/blogs`       | 博客文章 CRUD        |
| 分类   | `/api/v1/sections`    | 博客分类管理         |
| 标签   | `/api/v1/tags`        | 标签管理             |
| 媒体   | `/api/v1/media`       | 文件上传和管理       |
| SEO    | `/api/v1/seo`         | SEO 配置             |
| 留言板 | `/api/v1/boards`      | 留言管理             |
| 友链   | `/api/v1/friends`     | 友链管理             |
| 支付   | `/api/v1/payments`    | 支付处理             |
| 项目   | `/api/v1/projects`    | 项目展示             |
| 分析   | `/api/v1/analytics`   | 数据分析             |
| 订阅   | `/api/v1/subscribers` | 订阅者管理           |

### 认证方式

API 使用 JWT 令牌通过 **HTTP-Only Cookie** 进行认证，令牌自动管理，无需手动设置 Authorization 头。

```bash
# 1. 登录获取令牌（令牌自动保存在 Cookie 中）
curl -X 'POST' \
  'https://127.0.0.1:8000/api/v1/auth/account-login' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "password": "Ln8218270@",
  "email": "ln729500172@gmail.com"
}'

# 2. 访问受保护的 API（自动携带 Cookie）
curl -X 'GET' \
  'https://127.0.0.1:8000/api/v1/user/me/get-my-profile' \
  -H 'accept: application/json'

# 3. 刷新令牌
curl -X 'PATCH' \
  'https://127.0.0.1:8000/api/v1/auth/generate-access-token' \
  -H 'accept: application/json'

# 4. 登出（清除 Cookie）
curl -X 'DELETE' \
  'https://127.0.0.1:8000/api/v1/auth/account-logout' \
  -H 'accept: application/json'
```

**说明**：

- 浏览器会自动管理 Cookie，无需手动操作

## 🗃 数据库迁移

### 创建新迁移

```bash
# 自动生成迁移文件
uv run alembic revision --autogenerate -m "描述你的更改"

# 手动创建迁移文件
uv run alembic revision -m "描述你的更改"
```

### 执行迁移

```bash
# 升级到最新版本
uv run alembic upgrade head

# 升级到特定版本
uv run alembic upgrade <revision_id>

# 降级一个版本
uv run alembic downgrade -1

# 查看当前版本
uv run alembic current

# 查看迁移历史
uv run alembic history
```

### 迁移最佳实践

1. 每次更改数据模型后立即创建迁移
2. 在迁移文件中添加清晰的注释
3. 测试迁移的升级和降级
4. 备份数据库后再执行生产环境迁移

## ⚡️ 异步任务

### 可用任务

| 任务                             | 描述           | 调度           |
| -------------------------------- | -------------- | -------------- |
| `backup_database_task`           | 数据库备份     | 每天凌晨 2:00  |
| `generate_content_audio_task`    | 生成内容音频   | 按需触发       |
| `large_content_translation_task` | AI 内容翻译    | 按需触发       |
| `greeting_email_task`            | 发送欢迎邮件   | 用户注册时触发 |
| `send_invoice_email_task`        | 发送发票邮件   | 支付完成后触发 |
| `watermark_task`                 | 添加图片水印   | 图片上传时触发 |
| `thumbnail_task`                 | 生成缩略图     | 图片上传时触发 |
| `delete_user_media_task`         | 删除用户媒体   | 用户删除时触发 |
| `client_info_task`               | 记录客户端信息 | API 请求时触发 |
| `summary_content_task`           | 生成内容摘要   | 按需触发       |

### 启动 Celery Worker

```bash
# 启动 Worker
uv run celery -A app.core.celery.celery_manager.celery_app worker --loglevel=info

# 启动 Beat 调度器
uv run celery -A app.core.celery.celery_manager.celery_app beat --loglevel=info

# 同时启动 Worker 和 Beat
uv run celery -A app.core.celery.celery_manager.celery_app worker --beat --loglevel=info
```

### 监控任务

```bash
# 使用 Flower 监控（需要添加到依赖）
uv add flower
uv run celery -A app.core.celery.celery_manager.celery_app flower
```

访问 http://localhost:5555 查看任务监控面板。

## 🚢 部署指南

### GitHub Actions 全自动部署

本项目采用 **完全自动化** 的 CI/CD 流程，无需手动操作服务器。当你推送代码到 `main` 分支时，GitHub Actions 会自动：

1. ✅ 构建 Docker 镜像
2. ✅ 推送到 Docker Hub（私有仓库）
3. ✅ 通过 SSH 连接服务器
4. ✅ 拉取最新镜像并部署容器
5. ✅ 执行数据库迁移
6. ✅ 运行健康检查

### 部署架构

```
┌─────────────────────────────────────────────────────────────┐
│                       GitHub Actions                         │
│  (推送代码到 main 分支触发)                                   │
└────────────┬────────────────────────────┬───────────────────┘
             │                            │
             ▼                            ▼
    ┌────────────────┐          ┌────────────────┐
    │  构建 & 推送    │          │  SSH 部署      │
    │  Docker 镜像   │──────────▶│  到服务器      │
    │  (私有仓库)    │          │                │
    └────────────────┘          └────────┬───────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
            ┌───────────────┐    ┌──────────────┐    ┌──────────────┐
            │ 数据库服务器   │    │ 应用服务器    │    │ Docker Hub   │
            │ MySQL + Redis │    │ App + Nginx  │    │ (私有镜像)   │
            └───────────────┘    └──────────────┘    └──────────────┘
```

### 前置准备

#### 1. 服务器要求

- **数据库服务器**：
  - Ubuntu 20.04+ / Debian 11+
  - 最低 1GB RAM, 推荐 2GB+
  - MySQL 8.0+ 和 Redis 7.0+
- **应用服务器**：
  - Ubuntu 20.04+ / Debian 11+
  - 最低 2GB RAM, 推荐 4GB+
  - Docker 和 Docker Compose
  - 开放端口：80 (HTTP), 443 (HTTPS)

#### 2. Docker Hub 账号

创建私有仓库用于存储镜像：

- 访问 [Docker Hub](https://hub.docker.com/)
- 创建账号并创建私有仓库
- 生成 Access Token（Settings → Security → New Access Token）

### 配置 GitHub Secrets

在 GitHub 仓库设置 Secrets（Settings → Secrets and variables → Actions）：

#### Docker 配置

| Secret 名称       | 说明                    | 示例             |
| ----------------- | ----------------------- | ---------------- |
| `DOCKER_USERNAME` | Docker Hub 用户名       | `your_username`  |
| `DOCKER_PASSWORD` | Docker Hub Access Token | `dckr_pat_xxxxx` |

#### 服务器 SSH 配置

| Secret 名称     | 说明                  | 获取方式                                         |
| --------------- | --------------------- | ------------------------------------------------ |
| `DB_SERVER_IP`  | 数据库服务器 IP       | `123.456.789.100`                                |
| `DB_SSH_KEY`    | 数据库服务器 SSH 私钥 | 完整的私钥内容（包括 `-----BEGIN ... KEY-----`） |
| `APP_SERVER_IP` | 应用服务器 IP         | `123.456.789.101`                                |
| `APP_SSH_KEY`   | 应用服务器 SSH 私钥   | 完整的私钥内容（包括 `-----BEGIN ... KEY-----`） |

**获取 SSH 私钥**：

```bash
# 在本地生成 SSH 密钥对
ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/github_actions

# 将公钥添加到服务器
ssh-copy-id -i ~/.ssh/github_actions.pub ubuntu@<SERVER_IP>

# 复制私钥内容到 GitHub Secret
cat ~/.ssh/github_actions
```

#### 数据库配置

| Secret 名称       | 说明             | 示例                   |
| ----------------- | ---------------- | ---------------------- |
| `MYSQL_ROOT_PASS` | MySQL root 密码  | 强密码（至少 16 字符） |
| `MYSQL_APP_USER`  | 应用数据库用户名 | `app_user`             |
| `MYSQL_APP_PASS`  | 应用数据库密码   | 强密码（至少 16 字符） |
| `REDIS_PASS`      | Redis 密码       | 强密码（至少 16 字符） |

#### 应用环境配置

| Secret 名称           | 说明                                                  |
| --------------------- | ----------------------------------------------------- |
| `ENV_PRODUCTION_FILE` | 完整的生产环境配置（**纯 KEY=VALUE 格式，不含注释**） |

**`ENV_PRODUCTION_FILE` 配置示例**：

```env
APP_NAME=YourAppName
DATABASE_URL=mysql+aiomysql://app_user:app_password@db_server_ip:3306/your_database
JWT_SECRET_KEY=your_jwt_secret_key_min_32_chars
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
CORS_ALLOWED_ORIGINS=https://yourdomain.com
CSRF_SECRET_KEY=your_csrf_secret_key
CELERY_BROKER_URL=redis://:redis_password@db_server_ip:6379/0
CELERY_RESULT_BACKEND=redis://:redis_password@db_server_ip:6379/0
REDIS_CONNECTION_URL=redis://:redis_password@db_server_ip:6379/0
GITHUB_CLIENT_ID=your_github_oauth_client_id
GITHUB_CLIENT_SECRET=your_github_oauth_secret
GITHUB_REDIRECT_URI=https://api.yourdomain.com/api/v1/auth/github-callback
GOOGLE_CLIENT_ID=your_google_oauth_client_id
GOOGLE_CLIENT_SECRET=your_google_oauth_secret
GOOGLE_REDIRECT_URI=https://api.yourdomain.com/api/v1/auth/google-callback
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_BUCKET_NAME=your_s3_bucket
AWS_REGION=ap-southeast-1
STRIPE_SECRET_KEY=sk_live_your_stripe_key
STRIPE_PUBLIC_KEY=pk_live_your_stripe_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
QWEN_API_KEY=your_qwen_api_key
AZURE_SPEECH_KEY=your_azure_key
AZURE_SPEECH_REGION=eastus
DOMAIN_URL=https://api.yourdomain.com
COMPANY_NAME=YourCompany
COMPANY_EMAIL=contact@yourdomain.com
```

⚠️ **重要提示**：

- **不要包含注释行**（`#` 开头的行）
- **不要包含空格分隔线**
- 只保留 `KEY=VALUE` 格式
- 确保所有必需的变量都已配置

### 配置 SSL 证书（首次部署前必须完成）

应用服务器需要配置 SSL 证书才能通过 Nginx 提供 HTTPS 服务。**请在首次部署前完成此步骤。**

#### 方法 1：使用 Let's Encrypt（推荐）

```bash
# SSH 登录应用服务器
ssh ubuntu@<APP_SERVER_IP>

# 安装 Certbot
sudo apt update
sudo apt install certbot -y

# 获取证书（替换为你的域名）
sudo certbot certonly --standalone \
  -d api.yourdomain.com \
  --non-interactive \
  --agree-tos \
  --email your-email@example.com

# 证书将保存在：
# /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/api.yourdomain.com/privkey.pem

# 创建证书目录并复制
sudo mkdir -p /opt/server/certs
sudo cp /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem /opt/server/certs/cert.pem
sudo cp /etc/letsencrypt/live/api.yourdomain.com/privkey.pem /opt/server/certs/key.pem
sudo chmod 644 /opt/server/certs/cert.pem
sudo chmod 600 /opt/server/certs/key.pem

# 设置自动续期
sudo certbot renew --dry-run
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

#### 方法 2：使用自有证书

```bash
# 上传你的证书文件到服务器
scp cert.pem ubuntu@<APP_SERVER_IP>:/tmp/
scp key.pem ubuntu@<APP_SERVER_IP>:/tmp/

# SSH 登录服务器
ssh ubuntu@<APP_SERVER_IP>

# 移动证书到部署目录
sudo mkdir -p /opt/server/certs
sudo mv /tmp/cert.pem /opt/server/certs/
sudo mv /tmp/key.pem /opt/server/certs/
sudo chmod 644 /opt/server/certs/cert.pem
sudo chmod 600 /opt/server/certs/key.pem
sudo chown ubuntu:ubuntu /opt/server/certs/*
```

#### 验证 SSL 配置

```bash
# 检查证书文件
ls -lh /opt/server/certs/

# 检查证书有效期
sudo openssl x509 -in /opt/server/certs/cert.pem -noout -dates

# 部署完成后测试 HTTPS 连接
curl -I https://api.yourdomain.com
```

### 自动部署流程

#### 触发部署

```bash
# 提交并推送代码到 main 分支
git add .
git commit -m "feat: add new feature"
git push origin main
```

推送后，GitHub Actions 会自动执行以下步骤：

#### 阶段 1：数据库服务器部署（Deploy DB Server）

```
1️⃣ 上传 setup-mysql-redis.sh 到数据库服务器
2️⃣ 通过 SSH 执行脚本：
   - 安装/更新 MySQL 8.0
   - 安装/更新 Redis 7.0
   - 创建 blog 数据库（CHARACTER SET utf8mb4）
   - 创建应用数据库用户并授权
   - 配置远程访问权限
   - 设置防火墙规则
3️⃣ 验证数据库和 Redis 连接
```

#### 阶段 2：应用服务器部署（Deploy App Server）

```
1️⃣ 代码检出和验证
   - 验证必需文件存在
   - 检查数据库迁移文件

2️⃣ 构建 Docker 镜像
   - 使用 Docker Buildx 构建
   - 标签：latest, commit-sha, timestamp
   - 推送到 Docker Hub 私有仓库

3️⃣ 准备部署文件
   - 生成 .env.production
   - 上传配置文件到服务器：
     * docker-compose.yml
     * nginx.conf
     * alembic 迁移文件
     * 初始化数据脚本

4️⃣ 服务器环境准备
   - 安装 Docker（如需要）
   - 配置 SSL 证书（Let's Encrypt）
   - 备份当前配置（保留最近 5 份）
   - 创建部署目录结构

5️⃣ 拉取并启动容器
   - 登录 Docker Hub
   - 拉取最新镜像
   - 停止并清理旧容器
   - 启动新容器（app + nginx）
   - 等待容器健康检查通过

6️⃣ 数据库迁移
   - 检查迁移状态
   - 自动执行 alembic upgrade head
   - 验证迁移成功

7️⃣ 初始化数据
   - 运行 initial_data.py
   - 创建默认数据（如需要）

8️⃣ 健康检查
   - 验证 API 可访问性
   - 检查容器状态
   - 显示资源使用情况

9️⃣ 部署完成通知
```

### 监控部署状态

#### 在 GitHub 查看部署进度

1. 进入仓库的 **Actions** 标签页
2. 查看正在运行的 Workflows：
   - `Deploy DB Server` - 数据库部署
   - `Deploy App Server` - 应用部署
3. 点击查看详细日志和每个步骤的执行情况

#### 部署状态标识

| 图标 | 状态        | 说明     |
| ---- | ----------- | -------- |
| 🟡   | In Progress | 正在部署 |
| ✅   | Success     | 部署成功 |
| ❌   | Failed      | 部署失败 |

### 运维管理

#### 查看服务状态

```bash
# SSH 登录应用服务器
ssh ubuntu@<APP_SERVER_IP>

# 查看容器状态
cd /opt/server
sudo docker-compose ps

# 查看实时日志
sudo docker-compose logs -f

# 查看特定容器日志
sudo docker-compose logs -f app     # 应用日志
sudo docker-compose logs -f nginx   # Nginx 日志
```

#### 常用运维命令

```bash
# 重启服务
sudo docker-compose restart

# 查看资源使用
sudo docker stats

# 进入应用容器
sudo docker-compose exec app bash

# 查看应用配置
sudo docker-compose exec app env | grep -E "DATABASE|REDIS|JWT"

# 手动执行数据库迁移（调试用）
sudo docker-compose exec app alembic current
sudo docker-compose exec app alembic upgrade head

# 查看迁移历史
sudo docker-compose exec app alembic history
```

#### 回滚部署

如果新版本有问题，可以快速回滚：

```bash
# 查看备份
ls -lh /opt/backups/

# 回滚到之前的版本
cd /opt/server
sudo docker-compose down
sudo cp -r /opt/backups/server-YYYYMMDD-HHMMSS/* .
sudo docker-compose up -d
```

### 部署检查清单

部署前确认以下事项：

**GitHub 配置**

- [ ] 所有 GitHub Secrets 已正确配置
- [ ] Docker Hub Access Token 有效
- [ ] SSH 私钥格式正确（包含 BEGIN/END 标记）

**服务器准备**

- [ ] 服务器已安装 Ubuntu 20.04+ 或 Debian 11+
- [ ] SSH 公钥已添加到服务器的 `~/.ssh/authorized_keys`
- [ ] 服务器防火墙已开放端口：
  - 数据库服务器：3306 (MySQL), 6379 (Redis)
  - 应用服务器：80 (HTTP), 443 (HTTPS)
- [ ] 应用服务器已配置 SSL 证书（Let's Encrypt 或其他）

**环境配置**

- [ ] `ENV_PRODUCTION_FILE` 包含所有必需变量
- [ ] 数据库连接信息正确（IP、端口、用户名、密码）
- [ ] Redis 连接信息正确
- [ ] 第三方服务密钥已配置（AWS、Stripe、OAuth 等）

**域名和 SSL**

- [ ] 域名 DNS 已正确指向应用服务器 IP
- [ ] SSL 证书已配置（推荐使用 Let's Encrypt）
- [ ] Nginx 配置中的域名正确

**首次部署特别检查**

- [ ] Docker Hub 私有仓库已创建
- [ ] 数据库服务器可从应用服务器访问
- [ ] 已准备好初始化数据（如需要）

### 故障排查

#### GitHub Actions 部署失败

**问题 1：SSH 连接失败**

```bash
# 症状：Permission denied (publickey)
# 解决方案：
# 1. 检查 SSH 私钥格式是否完整（包含 BEGIN/END 标记）
# 2. 验证公钥是否已添加到服务器
ssh-copy-id -i ~/.ssh/github_actions.pub ubuntu@<SERVER_IP>

# 3. 测试 SSH 连接
ssh -i ~/.ssh/github_actions ubuntu@<SERVER_IP>
```

**问题 2：Docker Hub 推送失败**

```bash
# 症状：unauthorized: authentication required
# 解决方案：
# 1. 验证 DOCKER_USERNAME 和 DOCKER_PASSWORD
# 2. 确认 Access Token 有 Read & Write 权限
# 3. 检查仓库是否存在（在 Docker Hub 创建）
```

**问题 3：文件上传失败**

```bash
# 症状：No space left on device
# 解决方案：在服务器上清理磁盘空间
df -h
docker system prune -a --volumes
rm -rf /opt/backups/server-* # 删除旧备份
```

**问题 4：数据库迁移失败**

```bash
# 症状：Can't locate revision
# 原因：数据库版本与迁移文件不匹配
# 解决方案：
# 1. 查看当前数据库版本
sudo docker-compose exec app alembic current

# 2. 查看迁移历史
sudo docker-compose exec app alembic history

# 3. 如果版本不一致，需要手动修复或重置数据库
```

#### 应用运行问题

**问题 1：容器启动失败**

```bash
# 查看详细日志
cd /opt/server
sudo docker-compose logs --tail=200 app

# 检查容器状态
sudo docker-compose ps

# 检查配置文件
sudo docker-compose config

# 重新启动
sudo docker-compose restart app
```

**问题 2：数据库连接失败**

```bash
# 从应用服务器测试数据库连接
mysql -h <DB_SERVER_IP> -u <MYSQL_APP_USER> -p

# 检查数据库服务器防火墙
# 在数据库服务器执行：
sudo ufw status
sudo ufw allow from <APP_SERVER_IP> to any port 3306

# 检查 MySQL 绑定地址
sudo cat /etc/mysql/mysql.conf.d/mysqld.cnf | grep bind-address
# 应该是：bind-address = 0.0.0.0
```

**问题 3：Redis 连接失败**

```bash
# 测试 Redis 连接
redis-cli -h <DB_SERVER_IP> -p 6379 -a <REDIS_PASS> ping

# 检查 Redis 配置
# 在数据库服务器执行：
sudo cat /etc/redis/redis.conf | grep -E "bind|requirepass"
```

**问题 4：环境变量未生效**

```bash
# 检查环境变量是否正确加载
sudo docker-compose exec app env | grep -E "DATABASE|REDIS|JWT"

# 重新生成 .env.production
# 在 GitHub Secrets 中更新 ENV_PRODUCTION_FILE
# 然后重新触发部署
```

#### 性能问题

**问题 1：内存不足**

```bash
# 查看内存使用情况
free -h
sudo docker stats

# 优化配置（在 ENV_PRODUCTION_FILE 中添加）
UVICORN_WORKERS=2           # 减少 worker 数量
MYSQL_POOL_SIZE=5           # 减小连接池
REDIS_MAX_CONNECTIONS=20    # 减少 Redis 连接

# 启用 swap（临时方案）
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

**问题 2：响应速度慢**

```bash
# 检查数据库查询性能
sudo docker-compose exec app alembic current

# 查看 Nginx 访问日志
sudo docker-compose logs nginx | tail -100

# 检查网络延迟
ping <DB_SERVER_IP>
```

### 性能优化建议

#### 小内存服务器（2GB RAM）

在 `ENV_PRODUCTION_FILE` 中配置：

```env
UVICORN_WORKERS=2
MYSQL_POOL_SIZE=5
MYSQL_MAX_OVERFLOW=10
REDIS_MAX_CONNECTIONS=20
```

## 💻 开发指南

### 代码风格

项目使用 Ruff 进行代码检查和格式化：

```bash
# 检查代码
ruff check .

# 自动修复
ruff check --fix .

# 格式化代码
ruff format .
```

### 项目规范

- 使用 async/await 编写异步代码
- 所有 API 路由必须有类型注解
- 使用 Pydantic 模型进行数据验证
- 业务逻辑放在 service 层
- 数据库操作放在 crud 层
- 添加适当的日志记录
- 编写必要的单元测试

### 添加新功能

1. **创建数据模型** (`app/models/`)
2. **创建 Pydantic 模式** (`app/schemas/`)
3. **实现 CRUD 操作** (`app/crud/`)
4. **编写业务逻辑** (`app/services/`)
5. **创建 API 路由** (`app/router/v1/`)
6. **创建数据库迁移**
7. **编写测试**

### 示例：添加新模块

```python
# 1. 模型 (app/models/example_model.py)
from sqlmodel import SQLModel, Field

class Example(SQLModel, table=True):
    __tablename__ = "examples"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str | None = None

# 2. 模式 (app/schemas/example_schemas.py)
from pydantic import BaseModel

class ExampleCreate(BaseModel):
    name: str
    description: str | None = None

# 3. CRUD (app/crud/example_crud.py)
class ExampleCrud:
    async def create_example(self, data: ExampleCreate) -> int:
        # 实现创建逻辑
        pass

# 4. 服务 (app/services/example_service.py)
class ExampleService:
    async def create_example(self, data: ExampleCreate) -> dict:
        # 实现业务逻辑
        pass

# 5. 路由 (app/router/v1/example_router.py)
from fastapi import APIRouter

router = APIRouter(prefix="/examples", tags=["Examples"])

@router.post("/")
async def create_example(data: ExampleCreate):
    # 调用服务
    pass
```

## 🧪 测试

### 运行测试

```bash
# 运行所有测试
uv run pytest

# 运行特定测试文件
uv run pytest tests/test_auth.py

# 运行并显示覆盖率
uv run pytest --cov=app --cov-report=html

# 运行并显示详细输出
uv run pytest -v
```

### 编写测试

```python
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_create_blog():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/blogs",
            json={"title": "Test Blog", "content": "Test Content"}
        )
        assert response.status_code == 201
```

## ❓ 常见问题

### 1. 数据库连接失败

**问题**: `Can't connect to MySQL server`

**解决方案**:

- 检查 MySQL 服务是否运行
- 验证数据库配置（主机、端口、用户名、密码）
- 确保数据库已创建
- 检查防火墙设置

### 2. Redis 连接失败

**问题**: `Error connecting to Redis`

**解决方案**:

- 检查 Redis 服务是否运行
- 验证 Redis 配置
- 检查 Redis 密码设置

### 3. SSL 证书错误（开发环境）

**问题**: `SSL certificate verification failed`

**解决方案**:

- 生成自签名证书（见快速开始部分）
- 浏览器信任证书
- 或在开发环境禁用 SSL

### 4. Celery 任务不执行

**问题**: 异步任务未被处理

**解决方案**:

- 确保 Celery Worker 正在运行
- 检查 Redis 连接
- 查看 Celery 日志
- 确认任务已正确注册

### 5. 文件上传失败

**问题**: AWS S3 上传错误

**解决方案**:

- 验证 AWS 凭证
- 检查 S3 存储桶权限
- 确认 CORS 配置
- 检查文件大小限制

### 6. 内存不足

**问题**: 服务器内存耗尽

**解决方案**:

- 减少 Uvicorn Workers 数量
- 优化数据库连接池大小
- 使用 swap 分区
- 升级服务器配置

## 🤝 贡献指南

欢迎贡献！请遵循以下步骤：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 贡献规范

- 遵循项目代码风格
- 添加必要的测试
- 更新相关文档
- 确保所有测试通过
- 编写清晰的提交信息

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 📞 联系方式

- 作者: NING3739
- 仓库: [https://github.com/NING3739/blogbackendserver](https://github.com/NING3739/blogbackendserver)
- 问题反馈: [GitHub Issues](https://github.com/NING3739/blogbackendserver/issues)

## 🙏 致谢

感谢以下开源项目：

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLModel](https://sqlmodel.tiangolo.com/)
- [Celery](https://docs.celeryproject.org/)
- [Pydantic](https://pydantic-docs.helpmanual.io/)

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐️**

Made with ❤️ by NING3739

</div>
