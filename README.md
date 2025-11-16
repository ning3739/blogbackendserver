# Backend Server

一个基于 FastAPI 的现代化内容管理系统（CMS）后端服务，采用分层架构设计，支持博客、项目管理、支付、媒体管理等多种功能。

## 📋 目录

- [技术栈](#技术栈)
- [项目架构](#项目架构)
- [功能模块](#功能模块)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [API 文档](#api-文档)
- [异步任务](#异步任务)
- [数据库迁移](#数据库迁移)
- [开发指南](#开发指南)

## 🛠 技术栈

### 核心框架

- **FastAPI** - 现代、快速的 Web 框架
- **Python 3.13+** - 编程语言

### 数据库

- **MySQL** - 主数据库（使用 aiomysql 异步驱动）
- **Redis** - 缓存和会话存储
- **SQLModel** - ORM 框架
- **Alembic** - 数据库迁移工具

### 异步任务

- **Celery** - 分布式任务队列
- **Redis** - Celery 消息代理和结果后端

### 认证与安全

- **JWT** - JSON Web Token 认证
- **Argon2** - 密码加密
- **Session** - 会话管理
- **CSRF** - 跨站请求伪造保护

### 第三方服务集成

- **AWS S3** - 对象存储服务
- **Stripe** - 支付处理
- **Azure Speech** - 文本转语音（TTS）
- **通义千问（DashScope）** - AI 功能（内容摘要、翻译等）

### 工具库

- **Loguru** - 结构化日志记录
- **Pydantic** - 数据验证
- **WeasyPrint** - PDF 生成
- **QRCode** - 二维码生成
- **PyCryptodome** - 数据加密

## 🏗 项目架构

项目采用分层架构设计，职责清晰，易于维护：

```
backend-server/
├── app/
│   ├── core/              # 核心配置和基础设施
│   │   ├── config/        # 配置模块（模块化配置管理）
│   │   ├── database/      # 数据库连接管理
│   │   ├── i18n/          # 国际化支持
│   │   ├── logger.py      # 日志管理
│   │   ├── security.py    # 安全相关
│   │   └── celery.py      # Celery 配置
│   │
│   ├── models/            # 数据模型（SQLModel）
│   ├── schemas/          # Pydantic 数据验证模式
│   ├── crud/             # 数据库操作层（数据访问）
│   ├── services/         # 业务逻辑层
│   ├── router/           # API 路由层
│   │   └── v1/           # API v1 版本
│   │
│   ├── tasks/            # Celery 异步任务
│   ├── utils/            # 工具函数
│   ├── decorators/       # 装饰器（限流等）
│   └── main.py           # 应用入口
│
├── alembic/              # 数据库迁移文件
├── static/               # 静态文件（字体、图片、模板）
├── certs/                # SSL 证书
└── pyproject.toml        # 项目配置和依赖
```

### 架构层次说明

1. **Router 层** (`router/`) - 处理 HTTP 请求，参数验证
2. **Service 层** (`services/`) - 业务逻辑处理
3. **CRUD 层** (`crud/`) - 数据库操作封装
4. **Model 层** (`models/`) - 数据模型定义

## 🎯 功能模块

### 1. 认证授权 (`/api/v1/auth`)

- ✅ 邮箱验证码登录/注册
- ✅ JWT Token 认证
- ✅ 社交账号登录（OAuth）
- ✅ 密码重置
- ✅ 邮箱验证

### 2. 用户管理 (`/api/v1/user`)

- ✅ 用户信息 CRUD
- ✅ 用户角色管理（普通用户/管理员）
- ✅ 用户资料更新

### 3. 博客系统 (`/api/v1/blog`)

- ✅ 博客文章管理（创建、编辑、删除、发布）
- ✅ 标签系统
- ✅ 评论功能
- ✅ 收藏功能
- ✅ 内容摘要生成（AI）
- ✅ 文本转语音（TTS）
- ✅ 博客统计（浏览量、点赞等）

### 4. 项目管理 (`/api/v1/project`)

- ✅ 项目展示与管理
- ✅ 项目附件管理
- ✅ 项目付费功能
- ✅ 项目分类

### 5. 媒体管理 (`/api/v1/media`)

- ✅ 文件上传与管理
- ✅ 缩略图自动生成
- ✅ 水印处理
- ✅ AWS S3 存储集成
- ✅ 媒体文件元数据管理

### 6. 支付系统 (`/api/v1/payment`)

- ✅ Stripe 支付集成
- ✅ 支付记录管理
- ✅ 发票生成（PDF）
- ✅ 二维码生成
- ✅ 税务管理

### 7. SEO 管理 (`/api/v1/seo`)

- ✅ SEO 元数据管理
- ✅ 页面 SEO 优化配置

### 8. 标签系统 (`/api/v1/tag`)

- ✅ 标签 CRUD 操作
- ✅ 标签关联管理

### 9. 留言板 (`/api/v1/board`)

- ✅ 留言发布与管理
- ✅ 留言评论功能

### 10. 友链管理 (`/api/v1/friend`)

- ✅ 友链列表管理
- ✅ 友链分类

### 11. 订阅者管理 (`/api/v1/subscriber`)

- ✅ 订阅者信息管理
- ✅ 订阅邮件发送

### 12. 数据分析 (`/api/v1/analytic`)

- ✅ 访问统计与分析
- ✅ 用户行为分析

### 13. 分区管理 (`/api/v1/section`)

- ✅ 内容分区管理
- ✅ 分区层级结构

### 14. 文档 (`/api/v1/docs`)

- ✅ API 文档查看
- ✅ 项目配置查看

## 🚀 快速开始

### 环境要求

- Python 3.13+
- MySQL 8.0+
- Redis 6.0+
- Node.js (用于某些工具)

### 安装步骤

1. **克隆项目**（如果适用）

```bash
cd backend-server
```

2. **安装依赖**

使用 `uv`（推荐）：

```bash
uv sync
```

或使用 `pip`：

```bash
pip install -r requirements.txt
```

3. **配置环境变量**

创建 `.env` 文件，配置必要的环境变量：

```env
# 数据库配置
DATABASE_URL=mysql+aiomysql://user:password@localhost/dbname

# Redis 配置（用于应用缓存）
# 无密码: redis://localhost:6379/0
# 有密码: redis://:your-password@localhost:6379/0
REDIS_CONNECTION_URL=redis://localhost:6379/0

# Celery 配置（默认使用 Redis，可单独配置）
# 如果未设置，默认使用 redis://localhost:6379/0
# 有密码: redis://:your-password@localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# JWT 配置
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256

# 其他配置...
```

4. **数据库迁移**

```bash
# 初始化数据库（首次运行）
alembic upgrade head
```

5. **启动服务**

开发模式：

```bash
python -m app.main
```

或使用 uvicorn：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

6. **启动 Celery Worker**（可选，用于异步任务）

```bash
celery -A app.core.celery.celery_app worker --loglevel=info
```

### 访问服务

- **API 服务**: `https://localhost:8000`
- **API 文档**: `https://localhost:8000/docs` (Swagger UI)
- **ReDoc 文档**: `https://localhost:8000/redoc`

## ⚙️ 配置说明

项目采用模块化配置管理，所有配置位于 `app/core/config/modules/` 目录：

### 主要配置模块

- **AppSettings** - 应用基本信息（名称、版本、描述）
- **DatabaseSettings** - MySQL 数据库配置
- **RedisSettings** - Redis 配置
- **JWTSettings** - JWT 认证配置
- **CORSSettings** - CORS 跨域配置
- **CelerySettings** - Celery 异步任务配置
- **AWSSettings** - AWS S3 配置
- **StripeSettings** - Stripe 支付配置
- **EmailSettings** - 邮件服务配置
- **QwenSettings** - 通义千问 AI 配置
- **AzureSettings** - Azure Speech 配置

配置通过环境变量或 `.env` 文件加载，使用 `pydantic-settings` 管理。

## 📚 API 文档

所有 API 路由统一使用 `/api/v1` 前缀。

### 主要 API 端点

| 模块   | 前缀                 | 说明                 |
| ------ | -------------------- | -------------------- |
| 认证   | `/api/v1/auth`       | 登录、注册、验证码等 |
| 用户   | `/api/v1/user`       | 用户信息管理         |
| 博客   | `/api/v1/blog`       | 博客文章管理         |
| 项目   | `/api/v1/project`    | 项目管理             |
| 媒体   | `/api/v1/media`      | 文件上传和管理       |
| 支付   | `/api/v1/payment`    | 支付处理             |
| SEO    | `/api/v1/seo`        | SEO 配置             |
| 标签   | `/api/v1/tag`        | 标签管理             |
| 留言板 | `/api/v1/board`      | 留言管理             |
| 友链   | `/api/v1/friend`     | 友链管理             |
| 订阅者 | `/api/v1/subscriber` | 订阅者管理           |
| 分析   | `/api/v1/analytic`   | 数据分析             |
| 分区   | `/api/v1/section`    | 分区管理             |
| 文档   | `/api/v1/docs`       | API 文档             |

### 认证方式

大部分 API 需要 JWT 认证，通过 Cookie 中的 `access_token` 进行验证。

### 响应格式

成功响应：

```json
{
  "status": 200,
  "data": {...},
  "message": "Success"
}
```

错误响应：

```json
{
  "status": 400,
  "error": "Error message"
}
```

## 🔄 异步任务

项目使用 Celery 处理耗时任务，主要任务包括：

### 任务列表

1. **内容翻译** (`large_content_translation_task`)

   - 大文本内容的多语言翻译

2. **内容摘要** (`summary_content_task`)

   - 使用 AI 生成内容摘要

3. **音频生成** (`generate_content_audio_task`)

   - 文本转语音（TTS）

4. **缩略图生成** (`thumbnail_task`)

   - 自动生成图片缩略图

5. **水印处理** (`watermark_task`)

   - 为图片添加水印

6. **邮件发送**

   - 欢迎邮件 (`greeting_email_task`)
   - 发票邮件 (`send_invoice_email_task`)

7. **通知发送** (`notification_task`)

   - 系统通知推送

8. **媒体删除** (`delete_user_media_task`)

   - 异步删除用户媒体文件

9. **客户端信息** (`client_info_task`)

   - 收集客户端访问信息

10. **数据库备份** (`backup_database_task`)
    - 自动备份 MySQL 数据库到 S3
    - 支持定时自动备份和手动触发
    - 自动压缩备份文件

### 启动 Celery Worker

```bash
celery -A app.core.celery.celery_app worker --loglevel=info
```

### 启动 Celery Beat（定时任务调度器）

```bash
celery -A app.core.celery.celery_app beat --loglevel=info
```

**使用 uv 运行 Celery（推荐）**

```bash
# 同时启动 worker 和 beat（定时任务）
ENV=development uv run python -m celery -A app.core.celery.celery_app worker --beat --loglevel=info

# 或者分别启动
ENV=development uv run python -m celery -A app.core.celery.celery_app worker --loglevel=info
ENV=development uv run python -m celery -A app.core.celery.celery_app beat --loglevel=info
```

### Celery 配置

- Worker 并发数：2
- 任务超时：1 小时
- 软超时：50 分钟
- 每个 worker 处理 100 个任务后重启

### 定时备份配置

数据库备份任务已配置为每天凌晨 3 点自动执行，备份文件将上传到 S3：

- S3 路径：`backups/database/YYYY/MM/DD/database_backup_TIMESTAMP.sql.gz`
- 默认保留 30 天，超过保留期的旧备份文件会自动删除
- 自动压缩备份文件（gzip），节省存储空间

**自动清理功能：**

- 每次备份完成后，会自动清理超过保留期的旧备份文件
- 只清理匹配当前数据库名称的备份文件
- 清理失败不会影响备份任务的成功状态

手动触发备份：

```python
from app.tasks.backup_database_task import backup_database_task

# 备份默认数据库（从 DATABASE_URL 解析），保留 30 天
result = backup_database_task.delay()

# 指定数据库名称和保留天数
result = backup_database_task.delay(database_name='blog', retention_days=30)

# 禁用自动清理（保留天数设为 0 或负数）
result = backup_database_task.delay(database_name='blog', retention_days=0)
```

## 🗄 数据库迁移

使用 Alembic 进行数据库版本管理：

```bash
# 创建迁移文件
alembic revision --autogenerate -m "描述信息"

# 执行迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1

# 查看迁移历史
alembic history
```

## 🌍 国际化（i18n）

项目支持多语言，目前支持：

- 中文（zh）
- 英文（en）

语言通过请求头 `Accept-Language` 自动识别，所有错误消息和提示信息都支持国际化。

## 🔒 安全特性

1. **JWT 认证** - 基于 Token 的无状态认证
2. **密码加密** - 使用 Argon2 算法
3. **CSRF 保护** - Session 中间件保护
4. **限流** - 基于装饰器的 API 限流
5. **HTTPS** - 生产环境强制 HTTPS
6. **CORS** - 可配置的跨域资源共享

## 📝 开发指南

### 代码规范

项目使用 `ruff` 进行代码格式化和检查：

```bash
# 检查代码
ruff check .

# 自动修复
ruff check --fix .
```

### 添加新功能

1. **创建数据模型** (`app/models/`)
2. **创建 Schema** (`app/schemas/`)
3. **实现 CRUD** (`app/crud/`)
4. **实现 Service** (`app/services/`)
5. **创建 Router** (`app/router/v1/`)
6. **注册路由** (`app/main.py`)

### 测试

```bash
# 运行测试
pytest

# 带覆盖率
pytest --cov=app
```

## 📦 依赖管理

项目使用 `pyproject.toml` 管理依赖，主要依赖包括：

- `fastapi[standard]` - Web 框架
- `sqlmodel` - ORM
- `aiomysql` - MySQL 异步驱动
- `redis` - Redis 客户端
- `celery` - 异步任务队列
- `pydantic-settings` - 配置管理
- `loguru` - 日志记录
- `alembic` - 数据库迁移
- 等等...

## 🐛 故障排查

### 常见问题

1. **数据库连接失败**

   - 检查 MySQL 服务是否运行
   - 验证数据库配置是否正确

2. **Redis 连接失败**

   - 检查 Redis 服务是否运行
   - 验证 Redis 配置

3. **Celery 任务不执行**

   - 确保 Celery Worker 正在运行
   - 检查 Redis 连接

4. **SSL 证书错误**
   - 确保 `certs/` 目录下有有效的证书文件

## 📄 许可证

[添加许可证信息]

## 👥 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 联系方式

[添加联系方式]

---

**注意**: 这是一个生产级应用的后端服务，请确保在生产环境中正确配置所有安全设置和环境变量。

```
sudo apt update && sudo apt upgrade -y && sudo apt autoremove -y && sudo apt autoclean
```

# 配置 swap 交换空间(建议 2GB)

# 创建 swap 文件

sudo fallocate -l 2G /swapfile

# 设置权限

sudo chmod 600 /swapfile

# 格式化为 swap

sudo mkswap /swapfile

# 启用 swap

sudo swapon /swapfile

# 开机自动挂载

echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 验证是否生效

swapon --show
free -h

# 配置防火墙

sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# 禁用 root 登录,使用密钥认证

# 编辑 /etc/ssh/sshd_config

PermitRootLogin no
PasswordAuthentication no

# mysql

-- 登录 MySQL root
mysql -u root -p

-- 创建用户（如果还没创建）
CREATE USER 'ningli3739'@'%' IDENTIFIED BY 'Ln8218270!';

-- 授权
GRANT ALL PRIVILEGES ON blog.\* TO 'ningli3739'@'%';

-- 刷新权限
FLUSH PRIVILEGES;

-- 退出
EXIT;

测试
