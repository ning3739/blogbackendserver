# 使用 Python 3.13 作为基础镜像
FROM ghcr.io/astral-sh/uv:python3.13-bookworm

# 安装必需的工具和依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        ffmpeg \
        procps \
        fontconfig \
        default-mysql-client \
        && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户用于运行应用
RUN groupadd -r appuser && \
    useradd -r -g appuser -u 1000 -d /server -s /bin/bash appuser

# 设置工作目录
WORKDIR /server

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV ENV=production
ENV PATH="/server/.venv/bin:$PATH"


# 复制项目文件
COPY pyproject.toml uv.lock ./
COPY README.md ./
COPY app ./app
# alembic 和 alembic.ini 通过 volume 挂载，不复制到镜像中
COPY static ./static
COPY script/setup-server.sh ./script/setup-server.sh

# 使用 uv 安装依赖
RUN uv sync --frozen --no-dev

# 设置启动脚本为可执行
RUN chmod +x /server/script/setup-server.sh

# 确保 appuser 可以访问必要的目录和文件
# 创建 Celery 工作目录并设置权限
RUN mkdir -p /server/.celery /var/cache/fontconfig && \
    chown -R appuser:appuser /server/.celery && \
    chmod -R 777 /var/cache/fontconfig && \
    chmod -R o+rX /server && \
    chmod -R o+w /server/.venv 2>/dev/null || true

# 暴露端口
EXPOSE 8000



# 使用启动脚本作为入口点
ENTRYPOINT ["/server/script/setup-server.sh"]

