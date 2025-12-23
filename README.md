<div align="center">
  <h1><strong>Blog Backend Server</strong></h1>
  <p>
    <a href="https://www.python.org/">
      <img src="https://img.shields.io/badge/Python-3.13+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
    </a>
    <a href="https://fastapi.tiangolo.com/">
      <img src="https://img.shields.io/badge/FastAPI-0.116+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
    </a>
    <a href="LICENSE">
      <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge&logo=opensourceinitiative&logoColor=white" alt="License" />
    </a>
  </p>
  <p><strong>Production-ready backend for modern blogs, built with FastAPI. Features async architecture, multi-language, payment, AI content, and advanced media management.</strong></p>
</div>

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [System Architecture](#system-architecture)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Database Migration](#database-migration)
- [Async Tasks](#async-tasks)
- [Deployment Guide](#deployment-guide)
- [Development Guide](#development-guide)
- [Testing](#testing)
- [FAQ](#faq)
- [Contributing](#contributing)
- [License](#license)

## Features

### Authentication & Security

- Email verification code-based login
- OAuth 2.0 social login (Google, GitHub)
- JWT dual-token authentication (access & refresh)
- Argon2 password hashing
- CSRF protection middleware
- Configurable rate limiting

### Content Management

- Multi-language support (Chinese/English)
- Rich text editor integration
- Draft/publish workflow
- Hierarchical tags & categories
- SEO metadata optimization
- Cover image management
- Content versioning & history

### Media Management

- AWS S3 cloud storage
- Automatic image watermarking (customizable)
- Dynamic thumbnail generation
- Intelligent file type categorization
- User-scoped media library
- Batch upload with progress tracking

### Payment Integration

- Stripe payment gateway
- Automated PDF invoice generation
- Transactional email delivery
- Payment history & analytics
- Secure webhook event processing

### AI-Powered Features

- Automated content translation (Alibaba Cloud Qwen)
- High-quality text-to-speech (Azure Cognitive Services)
- Intelligent content summarization
- Multi-language AI processing

### Analytics & Monitoring

- Real-time access statistics
- User behavior analytics
- Client device detection
- Performance monitoring & logging

### Additional Features

- Interactive message board
- Friend link directory
- Project portfolio showcase
- Newsletter subscription management
- Automated email notifications
- Structured logging with rotation

## Tech Stack

### Core Framework

- **[FastAPI](https://fastapi.tiangolo.com/)** - High-performance async web framework with automatic API documentation
- **[SQLModel](https://sqlmodel.tiangolo.com/)** - SQL ORM with seamless Pydantic integration
- **[Pydantic](https://docs.pydantic.dev/)** - Data validation and settings management using Python type hints
- **[Alembic](https://alembic.sqlalchemy.org/)** - Database migration management tool

### Database & Caching

- **MySQL 8.0+** - Primary relational database with full UTF-8 support
- **Redis 7.0+** - In-memory data store for caching and message brokering
- **aiomysql** - Asynchronous MySQL database driver

### Task Queue

- **[Celery](https://docs.celeryproject.org/)** - Distributed asynchronous task queue
- **Celery Beat** - Periodic task scheduler for recurring jobs

### Cloud Services & Third-Party APIs

- **AWS S3** - Scalable object storage for media files
- **Stripe** - Secure payment processing and subscription management
- **Alibaba Cloud Qwen** - Advanced AI translation and NLP services
- **Azure Cognitive Services** - Neural text-to-speech synthesis
- **SMTP** - Reliable email delivery infrastructure

### DevOps & Development Tools

- **Docker & Docker Compose** - Container orchestration and deployment
- **Nginx** - High-performance reverse proxy and load balancer
- **GitHub Actions** - Automated CI/CD pipeline
- **Pytest** - Comprehensive testing framework
- **Ruff** - Lightning-fast Python linter and code formatter
- **Loguru** - Elegant and powerful logging solution
- **uv** - Next-generation Python package and project manager

## System Architecture

```
┌─────────────┐
│   Nginx     │  ← Reverse Proxy & SSL Termination
└──────┬──────┘
       │
┌──────▼──────┐
│   FastAPI   │  ← Web Application Server
│  (Uvicorn)  │
└──────┬──────┘
       │
       ├──────────────┬──────────────┬──────────────┐
       │              │              │              │
┌──────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐ ┌────▼─────┐
│    MySQL    │ │  Redis   │ │   AWS S3    │ │  Stripe  │
│ (Database)  │ │ (Cache)  │ │ (Storage)   │ │ (Payment)│
└─────────────┘ └────┬─────┘ └─────────────┘ └──────────┘
                     │
              ┌──────▼──────┐
              │   Celery    │  ← Async Task Processing
              │   Worker    │
              └─────────────┘
```

## Quick Start

### Prerequisites

Ensure the following dependencies are installed on your system:

- **Python 3.13+**
- **[uv](https://docs.astral.sh/uv/)** - Modern Python package manager
- **MySQL 8.0+** - Relational database
- **Redis 7.0+** - In-memory data store
- **Docker & Docker Compose** (optional, recommended for production deployment)

### Local Development Setup

#### 1. Clone the Repository

```bash
git clone https://github.com/NING3739/blogbackendserver.git
cd blogbackendserver
```

#### 2. Install uv Package Manager

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### 3. Install Dependencies

```bash
# Sync dependencies (automatically creates virtual environment)
uv sync
```

#### 4. Configure Environment Variables

Create environment configuration files:

```bash
mkdir -p secret
touch secret/.env.development
touch secret/.env.production
```

Refer to the [Configuration](#-configuration) section for detailed environment variable setup.

#### 5. Initialize Database

```bash
# Create database with UTF-8 support
mysql -u root -p -e "CREATE DATABASE blog CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Apply database migrations
uv run alembic upgrade head

# Seed initial data (optional)
uv run python script/initial_data.py
```

#### 6. Generate SSL Certificates (Development)

```bash
# Install mkcert
brew install mkcert  # macOS
# For other platforms: https://github.com/FiloSottile/mkcert

# Install local CA
mkcert -install

# Generate certificates
mkdir -p certs
cd certs
mkcert 127.0.0.1 localhost
mv 127.0.0.1+1-key.pem localhost-key.pem
mv 127.0.0.1+1.pem localhost.pem
cd ..
```

#### 7. Start Development Server

```bash
# Start FastAPI application
export ENV=development
uv run python -m app.main

# Or use uvicorn directly
ENV=development uv run uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --reload \
  --ssl-keyfile certs/localhost-key.pem \
  --ssl-certfile certs/localhost.pem
```

#### 8. Start Celery Workers (New Terminal)

```bash
# Start worker and beat scheduler together
ENV=development uv run celery -A app.core.celery:celery_app worker --beat --loglevel=info

# Or start separately:
# Worker only
ENV=development uv run celery -A app.core.celery:celery_app worker --loglevel=info

# Beat scheduler only
ENV=development uv run celery -A app.core.celery:celery_app beat --loglevel=info
```

#### 9. Access the Application

- **API Documentation (Swagger)**: https://127.0.0.1:8000/docs
- **API Documentation (ReDoc)**: https://127.0.0.1:8000/redoc
- **Application Root**: https://127.0.0.1:8000

## Project Structure

```
backend-server/
├── alembic/                    # Database migration files
│   ├── versions/              # Migration versions
│   ├── env.py                 # Alembic configuration
│   └── script.py.mako         # Migration script template
├── app/                        # Main application directory
│   ├── core/                  # Core modules
│   │   ├── config/           # Configuration management
│   │   │   ├── modules/      # Config modules (database, JWT, AWS, etc.)
│   │   │   ├── base.py       # Base configuration class
│   │   │   └── settings.py   # Global settings
│   │   ├── database/         # Database connection management
│   │   ├── i18n/            # Internationalization
│   │   ├── celery.py        # Celery configuration
│   │   ├── logger.py        # Logging management
│   │   └── security.py      # Security (passwords, JWT)
│   ├── crud/                  # Database CRUD operations
│   │   ├── auth_crud.py
│   │   ├── blog_crud.py
│   │   ├── user_crud.py
│   │   └── ...
│   ├── decorators/            # Decorators
│   │   └── rate_limiter.py   # Rate limiting decorator
│   ├── models/                # Data models
│   │   ├── auth_model.py
│   │   ├── blog_model.py
│   │   ├── user_model.py
│   │   └── ...
│   ├── router/                # API routes
│   │   └── v1/               # API v1 version
│   │       ├── auth_router.py
│   │       ├── blog_router.py
│   │       └── ...
│   ├── schemas/               # Pydantic data schemas
│   │   ├── auth_schemas.py
│   │   ├── blog_schemas.py
│   │   └── ...
│   ├── services/              # Business logicayer
│   │   ├── auth_service.py
│   │   ├── blog_service.py
│   │   └── ...
│   ├── tasks/                 # Celery async tasks
│   │   ├── backup_database_task.py
│   │   ├── generate_content_audio_task.py
│   │   ├── large_content_translation_task.py
│   │   └── ...
│   ├── utils/                 # Utility functions
│   └── main.py               # Application entry point
├── certs/                     # SSL certificates (development)
├── docs/                      # Project documentation
├── logs/                      # Log files
├── script/                    # Script files
│   ├── initial_data.py       # Initialize data
│   ├── setup-docker.sh       # Docker setup script
│   └── setup-server.sh       # Server setup script
├── secret/                    # Secrets and environment variables
│   ├── .env.development      # Development environment config
│   └── .env.production       # Production environment config
├── static/                    # Static files
│   ├── font/                 # Font files
│   ├── image/                # Image resources
│   └── template/             # Template files
├── tests/                     # Test files
├── alembic.ini               # Alembic configuration file
├── docker-compose.yml        # Docker Compose configuration
├── Dockerfile                # Docker image build file
├── nginx.conf                # Nginx configuration
├── pyproject.toml            # Project dependency configuration
└── README.md                 # Project documentation
```

## Configuration

### Environment Variables

Configure the following environment variables in `secret/.env.development` or `secret/.env.production`:

#### Complete Configuration Example

```env
# Application Configuration
APP_NAME=YourAppName

# Database Configuration
# Format: mysql+aiomysql://username:password@host:port/database
DATABASE_URL=mysql+aiomysql://your_user:your_password@localhost:3306/your_database

# JWT Configuration
JWT_SECRET_KEY=your_random_secret_key_here_at_least_32_characters

# Email Configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password

# CORS Configuration
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://api.yourdomain.com

# CSRF Configuration
CSRF_SECRET_KEY=your_csrf_secret_key

# Celery and Redis Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
REDIS_CONNECTION_URL=redis://localhost:6379/0

# OAuth Configuration
# GitHub OAuth
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_REDIRECT_URI=https://api.yourdomain.com/api/v1/auth/github-callback

# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=https://api.yourdomain.com/api/v1/auth/google-callback

# Logging Configuration
LOG_TO_FILE=True
LOG_FILE_PATH=logs/app.log

# AWS S3 Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_BUCKET_NAME=your_bucket_name
AWS_REGION=ap-southeast-1

# AI Service Configuration
# Alibaba Cloud Qwen
QWEN_API_KEY=your_qwen_api_key
QWEN_API_MAX_RETRIES=3

# Azure Speech Service
AZURE_SPEECH_KEY=your_azure_speech_key
AZURE_SPEECH_REGION=eastus

# Stripe Payment Configuration
STRIPE_SECRET_KEY=sk_live_your_stripe_secret_key
STRIPE_PUBLIC_KEY=pk_live_your_stripe_public_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
SUCCESS_URL=https://yourdomain.com/payment/success
CANCEL_URL=https://yourdomain.com/payment/cancel

# Domain and Company Information
DOMAIN_URL=https://api.yourdomain.com
COMPANY_NAME=YourCompanyName
COMPANY_PHONE=+1234567890
COMPANY_EMAIL=contact@yourdomain.com
```

#### Configuration Notes

Important Notes:

- Never commit real production configurations to version control
- Production configurations should be stored in GitHub Secrets (see deployment guide)
- Regularly rotate sensitive keys

## API Documentation

### Accessing Documentation

After starting the service, visit the following URLs to view API documentation:

- **Swagger UI**: https://127.0.0.1:8000/docs
- **ReDoc**: https://127.0.0.1:8000/redoc

### API Modules Overview

| Module      | Route Prefix          | Description                        |
| ----------- | --------------------- | ---------------------------------- |
| Auth        | `/api/v1/auth`        | Login, registration, token refresh |
| Users       | `/api/v1/users`       | User management                    |
| Blogs       | `/api/v1/blogs`       | Blog post CRUD                     |
| Sections    | `/api/v1/sections`    | Blog category management           |
| Tags        | `/api/v1/tags`        | Tag management                     |
| Media       | `/api/v1/media`       | File upload and management         |
| SEO         | `/api/v1/seo`         | SEO configuration                  |
| Boards      | `/api/v1/boards`      | Message management                 |
| Friends     | `/api/v1/friends`     | Friend link management             |
| Payments    | `/api/v1/payments`    | Payment processing                 |
| Projects    | `/api/v1/projects`    | Project showcase                   |
| Analytics   | `/api/v1/analytics`   | Data analytics                     |
| Subscribers | `/api/v1/subscribers` | Subscriber management              |

### Authentication Mechanism

The API uses JWT tokens via **HTTP-Only Cookies** for authentication. Tokens are automatically managed without manual Authorization header setup.

```bash
# 1. Login to get token (token automatically saved in Cookie)
curl -X 'POST' \
  'https://127.0.0.1:8000/api/v1/auth/account-login' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "password": "Ln8218270@",
  "email": "ln729500172@gmail.com"
}'

# 2. Access protected API (Cookie automatically included)
curl -X 'GET' \
  'https://127.0.0.1:8000/api/v1/user/me/get-my-profile' \
  -H 'accept: application/json'

# 3. Refresh token
curl -X 'PATCH' \
  'https://127.0.0.1:8000/api/v1/auth/generate-access-token' \
  -H 'accept: application/json'

# 4. Logout (clear Cookie)
curl -X 'DELETE' \
  'https://127.0.0.1:8000/api/v1/auth/account-logout' \
  -H 'accept: application/json'
```

Note: Browsers automatically manage Cookies, no manual operation required.

## Database Migration

### Creating New Migrations

```bash
# Auto-generate migration file
uv run alembic revision --autogenerate -m "Describe your changes"

# Manually create migration file
uv run alembic revision -m "Describe your changes"
```

### Executing Migrations

```bash
# Upgrade to latest version
uv run alembic upgrade head

# Upgrade to specific version
uv run alembic upgrade <revision_id>

# Downgrade one version
uv run alembic downgrade -1

# View current version
uv run alembic current

# View migration history
uv run alembic history
```

### Migration Best Practices

1. Create migrations immediately after changing data models
2. Add clear comments in migration files
3. Test both upgrade and downgrade migrations
4. Backup database before executing production migrations

## Async Tasks

### Available Tasks

| Task                             | Description               | Schedule                       |
| -------------------------------- | ------------------------- | ------------------------------ |
| `backup_database_task`           | Database backup           | Daily at 2:00 AM               |
| `generate_content_audio_task`    | Generate content audio    | On-demand                      |
| `large_content_translation_task` | AI content translation    | On-demand                      |
| `greeting_email_task`            | Send welcome email        | Triggered on user registration |
| `send_invoice_email_task`        | Send invoice email        | Triggered after payment        |
| `watermark_task`                 | Add image watermark       | Triggered on image upload      |
| `thumbnail_task`                 | Generate thumbnail        | Triggered on image upload      |
| `delete_user_media_task`         | Delete user media         | Triggered on user deletion     |
| `client_info_task`               | Record client information | Triggered on API request       |
| `summary_content_task`           | Generate content summary  | On-demand                      |

### Starting Celery Worker

```bash
# Start Worker
ENV=development uv run celery -A app.core.celery:celery_app worker --loglevel=info

# Start Beat scheduler
ENV=development uv run celery -A app.core.celery:celery_app beat --loglevel=info

# Start both Worker and Beat together
ENV=development uv run celery -A app.core.celery:celery_app worker --beat --loglevel=info
```

### Monitoring Tasks

```bash
# Use Flower for monitoring (needs to be added to dependencies)
uv add flower
ENV=development uv run celery -A app.core.celery:celery_app flower
```

Visit http://localhost:5555 to view the task monitoring dashboard.

## Deployment Guide

### Fully Automated GitHub Actions Deployment

This project uses a **fully automated** CI/CD workflow that requires no manual server operations. When you push code to the `main` branch, GitHub Actions automatically:

1. Builds Docker image
2. Pushes to Docker Hub (private repository)
3. Connects to server via SSH
4. Pulls latest image and deploys containers
5. Executes database migrations
6. Runs health checks

### Deployment Architecture Overview

```
GitHub Actions (Triggered by push to main branch)
    |
    +-- Build & Push Docker Image (Private Repo)
    |
    +-- SSH Deploy to Server
            |
            +-- DB Server (MySQL + Redis)
            +-- App Server (App + Nginx)
            +-- Docker Hub (Private)
```

### Prerequisites

#### 1. Server Requirements

- **Database Server**:
  - Ubuntu 20.04+ / Debian 11+
  - Minimum 1GB RAM, recommended 2GB+
  - MySQL 8.0+ and Redis 7.0+
- **Application Server**:
  - Ubuntu 20.04+ / Debian 11+
  - Minimum 2GB RAM, recommended 4GB+
  - Docker and Docker Compose
  - Open ports: 80 (HTTP), 443 (HTTPS)

#### 2. Docker Hub Account

Create a private repository for storing images:

- Visit [Docker Hub](https://hub.docker.com/)
- Create an account and create a private repository
- Generate Access Token (Settings → Security → New Access Token)

### Configuring GitHub Secrets

Set up Secrets in your GitHub repository (Settings → Secrets and variables → Actions):

#### Docker Configuration

| Secret Name       | Description             | Example          |
| ----------------- | ----------------------- | ---------------- |
| `DOCKER_USERNAME` | Docker Hub username     | `your_username`  |
| `DOCKER_PASSWORD` | Docker Hub Access Token | `dckr_pat_xxxxx` |

#### Server SSH Configuration

| Secret Name     | Description                | How to Obtain                                                      |
| --------------- | -------------------------- | ------------------------------------------------------------------ |
| `DB_SERVER_IP`  | Database server IP         | `123.456.789.100`                                                  |
| `DB_SSH_KEY`    | Database server SSH key    | Complete private key content (including `-----BEGIN ... KEY-----`) |
| `APP_SERVER_IP` | Application server IP      | `123.456.789.101`                                                  |
| `APP_SSH_KEY`   | Application server SSH key | Complete private key content (including `-----BEGIN ... KEY-----`) |

**Obtaining SSH Private Key**:

```bash
# Generate SSH key pair locally
ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/github_actions

# Add public key to server
ssh-copy-id -i ~/.ssh/github_actions.pub ubuntu@<SERVER_IP>

# Copy private key content to GitHub Secret
cat ~/.ssh/github_actions
```

#### Database Configuration

| Secret Name       | Description                   | Example                        |
| ----------------- | ----------------------------- | ------------------------------ |
| `MYSQL_ROOT_PASS` | MySQL root password           | Strong password (min 16 chars) |
| `MYSQL_APP_USER`  | Application database user     | `app_user`                     |
| `MYSQL_APP_PASS`  | Application database password | Strong password (min 16 chars) |
| `REDIS_PASS`      | Redis password                | Strong password (min 16 chars) |

#### Application Environment Configuration

| Secret Name           | Description                                                                     |
| --------------------- | ------------------------------------------------------------------------------- |
| `ENV_PRODUCTION_FILE` | Complete production environment config (**Pure KEY=VALUE format, no comments**) |

**`ENV_PRODUCTION_FILE` Configuration Example**:

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

⚠️ **Important Notes**:

- **Do not include comment lines** (lines starting with `#`)
- **Do not include separator lines**
- Only keep `KEY=VALUE` format
- Ensure all required variables are configured

### Configuring SSL Certificates (Must Complete Before First Deployment)

The application server needs SSL certificates configured to provide HTTPS service through Nginx. **Please complete this step before the first deployment.**

#### Method 1: Using Let's Encrypt (Recommended)

```bash
# SSH login to application server
ssh ubuntu@<APP_SERVER_IP>

# Install Certbot
sudo apt update
sudo apt install certbot -y

# Obtain certificate (replace with your domain)
sudo certbot certonly --standalone \
  -d api.yourdomain.com \
  --non-interactive \
  --agree-tos \
  --email your-email@example.com

# Certificates will be saved at:
# /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/api.yourdomain.com/privkey.pem

# Create certificate directory and copy
sudo mkdir -p /opt/server/certs
sudo cp /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem /opt/server/certs/cert.pem
sudo cp /etc/letsencrypt/live/api.yourdomain.com/privkey.pem /opt/server/certs/key.pem
sudo chmod 644 /opt/server/certs/cert.pem
sudo chmod 600 /opt/server/certs/key.pem

# Set up automatic renewal
sudo certbot renew --dry-run
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

#### Method 2: Using Your Own Certificate

```bash
# Upload your certificate files to server
scp cert.pem ubuntu@<APP_SERVER_IP>:/tmp/
scp key.pem ubuntu@<APP_SERVER_IP>:/tmp/

# SSH login to server
ssh ubuntu@<APP_SERVER_IP>

# Move certificates to deployment directory
sudo mkdir -p /opt/server/certs
sudo mv /tmp/cert.pem /opt/server/certs/
sudo mv /tmp/key.pem /opt/server/certs/
sudo chmod 644 /opt/server/certs/cert.pem
sudo chmod 600 /opt/server/certs/key.pem
sudo chown ubuntu:ubuntu /opt/server/certs/*
```

#### Verify SSL Configuration

```bash
# Check certificate files
ls -lh /opt/server/certs/

# Check certificate validity period
sudo openssl x509 -in /opt/server/certs/cert.pem -noout -dates

# Test HTTPS connection after deployment
curl -I https://api.yourdomain.com
```

### Automated Deployment Workflow

#### Triggering Deployment

```bash
git add .
git commit -m "feat: add new feature"
git push origin main
```

After pushing, GitHub Actions will automatically execute the following steps:

#### Stage 1: Database Server Deployment

1. Upload setup-mysql-redis.sh to database server
2. Execute script via SSH:
   - Install/update MySQL 8.0
   - Install/update Redis 7.0
   - Create blog database (CHARACTER SET utf8mb4)
   - Create application database user and grant permissions
   - Configure remote access permissions
   - Set up firewall rules
3. Verify database and Redis connections

#### Stage 2: Application Server Deployment

1. Code checkout and validation

   - Verify required files exist
   - Check database migration files

2. Build Docker image

   - Build using Docker Buildx
   - Tags: latest, commit-sha, timestamp
   - Push to Docker Hub private repository

3. Prepare deployment files

   - Generate .env.production
   - Upload configuration files to server:
     - docker-compose.yml
     - nginx.conf
     - alembic migration files
     - Initialization data scripts

4. Server environment preparation

   - Install Docker (if needed)
   - Configure SSL certificates (Let's Encrypt)
   - Backup current configuration (keep last 5 copies)
   - Create deployment directory structure

5. Pull and start containers

   - Login to Docker Hub
   - Pull latest image
   - Stop and clean up old containers
   - Start new containers (app + nginx)
   - Wait for container health checks to pass

6. Database migration

   - Check migration status
   - Automatically execute alembic upgrade head
   - Verify migration success

7. Initialize data

   - Run initial_data.py
   - Create default data (if needed)

8. Health check

   - Verify API accessibility
   - Check container status
   - Display resource usage

9. Deployment completion notification

### Monitoring Deployment Status

#### Viewing Deployment Progress on GitHub

1. Go to the repository's **Actions** tab
2. View running Workflows:
   - `Deploy DB Server` - Database deployment
   - `Deploy App Server` - Application deployment
3. Click to view detailed logs and execution status of each step

#### Deployment Status Indicators

| Status      | Description           |
| ----------- | --------------------- |
| In Progress | Deploying             |
| Success     | Deployment successful |
| Failed      | Deployment failed     |

### Operations Management

#### Viewing Service Status

```bash
# SSH login to application server
ssh ubuntu@<APP_SERVER_IP>

# View container status
cd /opt/server
sudo docker-compose ps

# View real-time logs
sudo docker-compose logs -f

# View specific container logs
sudo docker-compose logs -f app     # Application logs
sudo docker-compose logs -f nginx   # Nginx logs
```

#### Common Operations Commands

```bash
# Restart services
sudo docker-compose restart

# View resource usage
sudo docker stats

# Enter application container
sudo docker-compose exec app bash

# View application configuration
sudo docker-compose exec app env | grep -E "DATABASE|REDIS|JWT"

# Manually execute database migration (for debugging)
sudo docker-compose exec app alembic current
sudo docker-compose exec app alembic upgrade head

# View migration history
sudo docker-compose exec app alembic history
```

#### Rolling Back Deployment

If the new version has issues, you can quickly roll back:

```bash
# View backups
ls -lh /opt/backups/

# Roll back to previous version
cd /opt/server
sudo docker-compose down
sudo cp -r /opt/backups/server-YYYYMMDD-HHMMSS/* .
sudo docker-compose up -d
```

### Deployment Checklist

Confirm the following before deployment:

GitHub Configuration:

- [ ] All GitHub Secrets are correctly configured
- [ ] Docker Hub Access Token is valid
- [ ] SSH private key format is correct (includes BEGIN/END markers)

Server Preparation:

- [ ] Server has Ubuntu 20.04+ or Debian 11+ installed
- [ ] SSH public key has been added to server's `~/.ssh/authorized_keys`
- [ ] Server firewall has opened ports:
  - Database server: 3306 (MySQL), 6379 (Redis)
  - Application server: 80 (HTTP), 443 (HTTPS)
- [ ] Application server has SSL certificates configured (Let's Encrypt or other)

Environment Configuration:

- [ ] `ENV_PRODUCTION_FILE` contains all required variables
- [ ] Database connection information is correct (IP, port, username, password)
- [ ] Redis connection information is correct
- [ ] Third-party service keys are configured (AWS, Stripe, OAuth, etc.)

Domain and SSL:

- [ ] Domain DNS correctly points to application server IP
- [ ] SSL certificates are configured (Let's Encrypt recommended)
- [ ] Domain in Nginx configuration is correct

First Deployment Special Checks:

- [ ] Docker Hub private repository has been created
- [ ] Database server is accessible from application server
- [ ] Initialization data is ready (if needed)

### Troubleshooting

#### GitHub Actions Deployment Failed

Issue 1: SSH Connection Failed

```bash
# Symptom: Permission denied (publickey)
# Solutions:
# 1. Check if SSH private key format is complete (includes BEGIN/END markers)
# 2. Verify public key has been added to server
ssh-copy-id -i ~/.ssh/github_actions.pub ubuntu@<SERVER_IP>

# 3. Test SSH connection
ssh -i ~/.ssh/github_actions ubuntu@<SERVER_IP>
```

Issue 2: Docker Hub Push Failed

```bash
# Symptom: unauthorized: authentication required
# Solutions:
# 1. Verify DOCKER_USERNAME and DOCKER_PASSWORD
# 2. Confirm Access Token has Read & Write permissions
# 3. Check if repository exists (create in Docker Hub)
```

Issue 3: File Upload Failed

```bash
# Symptom: No space left on device
# Solution: Clean up disk space on server
df -h
docker system prune -a --volumes
rm -rf /opt/backups/server-* # Delete old backups
```

Issue 4: Database Migration Failed

```bash
# Symptom: Can't locate revision
# Cause: Database version doesn't match migration files
# Solutions:
# 1. View current database version
sudo docker-compose exec app alembic current

# 2. View migration history
sudo docker-compose exec app alembic history

# 3. If versions don't match, need to manually fix or reset database
```

#### Application Runtime Issues

Issue 1: Container Startup Failed

```bash
# View detailed logs
cd /opt/server
sudo docker-compose logs --tail=200 app

# Check container status
sudo docker-compose ps

# Check configuration file
sudo docker-compose config

# Restart
sudo docker-compose restart app
```

Issue 2: Database Connection Failed

```bash
# Test database connection from application server
mysql -h <DB_SERVER_IP> -u <MYSQL_APP_USER> -p

# Check database server firewall
# Execute on database server:
sudo ufw status
sudo ufw allow from <APP_SERVER_IP> to any port 3306

# Check MySQL bind address
sudo cat /etc/mysql/mysql.conf.d/mysqld.cnf | grep bind-address
# Should be: bind-address = 0.0.0.0
```

Issue 3: Redis Connection Failed

```bash
# Test Redis connection
redis-cli -h <DB_SERVER_IP> -p 6379 -a <REDIS_PASS> ping

# Check Redis configuration
# Execute on database server:
sudo cat /etc/redis/redis.conf | grep -E "bind|requirepass"
```

Issue 4: Environment Variables Not Taking Effect

```bash
# Check if environment variables are loaded correctly
sudo docker-compose exec app env | grep -E "DATABASE|REDIS|JWT"

# Regenerate .env.production
# Update ENV_PRODUCTION_FILE in GitHub Secrets
# Then trigger deployment again
```

#### Performance Issues

Issue 1: Out of Memory

```bash
# View memory usage
free -h
sudo docker stats

# Optimize configuration (add to ENV_PRODUCTION_FILE)
UVICORN_WORKERS=2           # Reduce worker count
MYSQL_POOL_SIZE=5           # Reduce connection pool
REDIS_MAX_CONNECTIONS=20    # Reduce Redis connections

# Enable swap (temporary solution)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

Issue 2: Slow Response

```bash
# Check database query performance
sudo docker-compose exec app alembic current

# View Nginx access logs
sudo docker-compose logs nginx | tail -100

# Check network latency
ping <DB_SERVER_IP>
```

### Performance Optimization Recommendations

#### Small Memory Server (2GB RAM)

Configure in `ENV_PRODUCTION_FILE`:

```env
UVICORN_WORKERS=2
MYSQL_POOL_SIZE=5
MYSQL_MAX_OVERFLOW=10
REDIS_MAX_CONNECTIONS=20
```

## Development Guide

### Code Style

The project uses Ruff for code linting and formatting:

```bash
# Check code
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

### Project Standards

- Use async/await for asynchronous code
- All API routes must have type annotations
- Use Pydantic models for data validation
- Business logic goes in the service layer
- Database operations go in the crud layer
- Add appropriate logging
- Write necessary unit tests

### Adding New Features

1. **Create data model** (`app/models/`)
2. **Create Pydantic schemas** (`app/schemas/`)
3. **Implement CRUD operations** (`app/crud/`)
4. **Write business logic** (`app/services/`)
5. **Create API routes** (`app/router/v1/`)
6. **Create database migration**
7. **Write tests**

### Example: Adding a New Module

```python
# 1. Model (app/models/example_model.py)
from sqlmodel import SQLModel, Field

class Example(SQLModel, table=True):
    __tablename__ = "examples"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str | None = None

# 2. Schema (app/schemas/example_schemas.py)
from pydantic import BaseModel

class ExampleCreate(BaseModel):
    name: str
    description: str | None = None

# 3. CRUD (app/crud/example_crud.py)
class ExampleCrud:
    async def create_example(self, data: ExampleCreate) -> int:
        # Implement creation logic
        pass

# 4. Service (app/services/example_service.py)
class ExampleService:
    async def create_example(self, data: ExampleCreate) -> dict:
        # Implement business logic
        pass

# 5. Router (app/router/v1/example_router.py)
from fastapi import APIRouter

router = APIRouter(prefix="/examples", tags=["Examples"])

@router.post("/")
async def create_example(data: ExampleCreate):
    # Call service
    pass
```

## Testing

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_auth.py

# Run with coverage report
uv run pytest --cov=app --cov-report=html

# Run with verbose output
uv run pytest -v
```

### Writing Tests

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

## FAQ

### 1. Database Connection Failed

Issue: `Can't connect to MySQL server`

Solutions:

- Check if MySQL service is running
- Verify database configuration (host, port, username, password)
- Ensure database is created
- Check firewall settings

### 2. Redis Connection Failed

**Issue**: `Error connecting to Redis`

**Solutions**:

- Check if Redis service is running
- Verify Redis configuration
- Check Redis password settings

### 3. SSL Certificate Error (Development)

**Issue**: `SSL certificate verification failed`

**Solutions**:

- Generate self-signed certificate (see Quick Start section)
- Trust certificate in browser
- Or disable SSL in development environment

### 4. Celery Tasks Not Executing

**Issue**: Async tasks not being processed

**Solutions**:

- Ensure Celery Worker is running
- Check Redis connection
- View Celery logs
- Confirm tasks are properly registered

### 5. File Upload Failed

**Issue**: AWS S3 upload error

**Solutions**:

- Verify AWS credentials
- Check S3 bucket permissions
- Confirm CORS configuration
- Check file size limits

### 6. Out of Memory

**Issue**: Server running out of memory

**Solutions**:

- Reduce number of Uvicorn Workers
- Optimize database connection pool size
- Use swap partition
- Upgrade server configuration

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork this repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Contribution Guidelines

- Follow project code style
- Add necessary tests
- Update relevant documentation
- Ensure all tests pass
- Write clear commit messages

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details

## Contact

- Author: NING3739
- Repository: [https://github.com/NING3739/blogbackendserver](https://github.com/NING3739/blogbackendserver)
- Issue Tracker: [GitHub Issues](https://github.com/NING3739/blogbackendserver/issues)

## Acknowledgments

Thanks to the following open source projects:

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLModel](https://sqlmodel.tiangolo.com/)
- [Celery](https://docs.celeryproject.org/)
- [Pydantic](https://pydantic-docs.helpmanual.io/)

---

<div align="center">

**If this project helps you, please give it a ⭐️**

Made with ❤️ by NING3739

</div>
