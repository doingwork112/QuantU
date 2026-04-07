"""
QuantifyU — FastAPI 主入口
AI量化约会App后端
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.config import get_settings
from app.routers import auth, scoring, profile, matching, vault, privacy
from app.schemas.base import ErrorResponse


# ================================================================
# 生命周期管理
# ================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(f"QuantifyU API 启动 | env={settings.API_ENV}")
    logger.info(f"Supabase: {settings.SUPABASE_URL}")
    logger.info(f"加密密钥版本: v{settings.ENCRYPTION_KEY_VERSION}")
    yield
    logger.info("QuantifyU API 关闭")


# ================================================================
# App实例
# ================================================================
app = FastAPI(
    title="QuantifyU API",
    description="AI量化约会App — Looksmaxxing评分 + 智能匹配",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ================================================================
# 中间件
# ================================================================
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.API_CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"→ {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"← {request.method} {request.url.path} | {response.status_code}")
    return response


# ================================================================
# 全局错误处理
# ================================================================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field = " → ".join(str(loc) for loc in error["loc"])
        errors.append(f"{field}: {error['msg']}")

    logger.warning(
        f"参数验证失败 | path={request.url.path} | errors={errors}"
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            message="请求参数验证失败",
            error_code="VALIDATION_ERROR",
            detail="; ".join(errors),
        ).model_dump(mode="json"),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"未处理异常 | path={request.url.path} | "
        f"type={type(exc).__name__} | error={exc}"
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            message="服务器内部错误",
            error_code="INTERNAL_ERROR",
            detail=str(exc) if settings.API_ENV == "development" else None,
        ).model_dump(mode="json"),
    )


# ================================================================
# 注册路由
# ================================================================
app.include_router(auth.router)
app.include_router(scoring.router)
app.include_router(profile.router)
app.include_router(matching.router)
app.include_router(vault.router)
app.include_router(privacy.router)


# ================================================================
# 健康检查
# ================================================================
@app.get("/health", tags=["系统"])
async def health_check():
    return {
        "status": "healthy",
        "service": "quantifyu-api",
        "version": "1.0.0",
    }


@app.get("/", tags=["系统"])
async def root():
    return {
        "name": "QuantifyU API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "auth": ["/auth/signup", "/auth/login"],
            "scoring": ["/rating/calculate"],
            "profile": ["/profile/update", "/profile/me"],
            "matching": ["/matches", "/matches/compatibility", "/matches/daily-batch"],
            "vault": ["/private-vault/save"],
            "privacy": [
                "/privacy/consent/update",
                "/privacy/consent/status",
                "/privacy/vault",
                "/privacy/photo/upload",
                "/privacy/data-export",
                "/privacy/account",
            ],
        },
    }
