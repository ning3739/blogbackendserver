import os
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html


from app.core.i18n.i18n import get_message
from app.core.i18n.i18n import get_language
from app.core.logger import logger_manager
from app.core.database.connection import db_manager
from app.core.config.settings import settings
from app.router.v1 import (
    auth_router,
    user_router,
    blog_router,
    section_router,
    seo_router,
    tag_router,
    board_router,
    friend_router,
    media_router,
    docs_router,
    payment_router,
    project_router,
    analytic_router,
    subscriber_router
)


# 创建LoggerManager实例
logger_manager.setup()


# 创建Logger实例
logger = logger_manager.get_logger(__name__)


# 创建生命周期
async def lifespan(_app: FastAPI):
    logger.info("🚩 Starting the application...")
    logger.info(f"🚧 You are Working in {os.getenv('ENV')} Environment")

    try:
        # 初始化数据库连接
        await db_manager.initialize()
        logger.info("🎉 Database connections initialized successfully")
        await db_manager.test_connections()
        logger.info("🎉 Database connections test successfully")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        logger.warning(
            "⚠️ Application will start without database connections")

    yield

    # 关闭数据库连接
    try:
        await db_manager.close()
        logger.info("🎉 Database connections closed successfully")
    except Exception as e:
        logger.error(f"❌ Database connection closed failed: {e}")
        logger.warning("⚠️ Database connection closed failed")


# 创建FastAPI实例
app = FastAPI(
    lifespan=lifespan,
    title=settings.app.APP_NAME
)


# 全局异常处理器
@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    logger.error(f"HTTPException: {exc}")
    error_detail = exc.detail

    if isinstance(error_detail, dict):
        # 如果detail是字典，直接使用error字段
        error_message = error_detail.get("error", str(error_detail))
    else:
        # 如果detail是字符串，直接使用
        error_message = str(error_detail)

    return JSONResponse(
        status_code=exc.status_code,
        content={"status": exc.status_code, "error": error_message},
    )


@app.exception_handler(Exception)
async def general_exception_handler(_request: Request, exc: Exception):
    logger.error(f"Exception: {exc}")
    language = get_language(_request)
    return JSONResponse(
        status_code=500,
        content={
            "status": 500,
            "error": get_message("common.internalError", language),
        },
    )


# CORS中间件
# 处理逗号分隔的源列表
allow_origins = [x.strip()
                 for x in settings.cors.CORS_ALLOWED_ORIGINS.split(',') if x.strip()]
allow_methods = [x.strip()
                 for x in settings.cors.CORS_ALLOW_METHODS.split(',') if x.strip()]
allow_headers = [x.strip()
                 for x in settings.cors.CORS_ALLOW_HEADERS.split(',') if x.strip()]
allow_credentials = settings.cors.CORS_ALLOW_CREDENTIALS
expose_headers = [x.strip()
                  for x in settings.cors.CORS_EXPOSE_HEADERS.split(',') if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=allow_methods,
    allow_headers=allow_headers,
    allow_credentials=allow_credentials,
    expose_headers=expose_headers,
)


# Session中间件
session_secret_key = settings.csrf.CSRF_SECRET_KEY.get_secret_value()
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret_key,
    https_only=True,
    same_site="lax",
)


# 静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")


# 注册路由
app.include_router(docs_router.router, prefix="/api/v1")
app.include_router(auth_router.router, prefix="/api/v1")
app.include_router(user_router.router, prefix="/api/v1")
app.include_router(section_router.router, prefix="/api/v1")
app.include_router(blog_router.router, prefix="/api/v1")
app.include_router(board_router.router, prefix="/api/v1")
app.include_router(friend_router.router, prefix="/api/v1")
app.include_router(seo_router.router, prefix="/api/v1")
app.include_router(tag_router.router, prefix="/api/v1")
app.include_router(media_router.router, prefix="/api/v1")
app.include_router(payment_router.router, prefix="/api/v1")
app.include_router(project_router.router, prefix="/api/v1")
app.include_router(analytic_router.router, prefix="/api/v1")
app.include_router(subscriber_router.router, prefix="/api/v1")


# OPEN API 文档
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=settings.app.APP_NAME,
        version=settings.app.APP_VERSION,
        description=settings.app.APP_DESCRIPTION,
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# 启动FastAPI应用
if os.getenv("ENV") == "development":
    uvicorn.run(
        app="app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        ssl_keyfile="certs/localhost-key.pem",
        ssl_certfile="certs/localhost.pem",
    )
