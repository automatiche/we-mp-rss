import sys
import asyncio

# Windows 需要使用 ProactorEventLoop 以支持 Playwright 子进程
# 必须在任何事件循环创建之前设置
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, Request, APIRouter, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
from fastapi.openapi.models import OAuthFlowPassword
from fastapi.openapi.utils import get_openapi
from apis.auth import router as auth_router
from apis.user import router as user_router
from apis.article import router as article_router
from apis.mps import router as wx_router
from apis.res import router as res_router
from apis.rss import router as rss_router,feed_router
from apis.config_management import router as config_router
from apis.message_task import router as task_router
from apis.sys_info import router as sys_info_router
from apis.tags import router as tags_router
from apis.export import router as export_router
from apis.tools import router as tools_router
from apis.github_update import router as github_router
from apis.cascade import router as cascade_router
from apis.env_exception import router as env_exception_router
from apis.filter_rule import router as filter_rule_router
from apis.task_queue import router as task_queue_router
from apis.proxy import router as proxy_router
from apis.weread import router as weread_router
from views import router as views_router
import apis
import os
from core.config import cfg,VERSION,API_BASE
from starlette.middleware.base import BaseHTTPMiddleware


def _configured_cors_origins():
    """Return the exact origins explicitly allowed by configuration."""
    origins = cfg.get("safe.cors_origins", "")
    if isinstance(origins, str):
        return [
            origin.strip().rstrip("/")
            for origin in origins.split(",")
            if origin.strip() and origin.strip() != "*"
        ]
    if isinstance(origins, list):
        return [
            str(origin).strip().rstrip("/")
            for origin in origins
            if str(origin).strip() and str(origin).strip() != "*"
        ]
    return []

class AKMiddleware(BaseHTTPMiddleware):
    """Access Key 认证中间件"""
    async def dispatch(self, request: Request, call_next):
        # 提取 Authorization 头
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("AK-SK "):
            # 将AK/SK认证信息存储在 request state 中供后续使用
            request.state.ak_auth = auth_header
        response = await call_next(request)
        return response

api_docs_enabled = bool(cfg.get("safe.api_docs_enabled", False))

app = FastAPI(
    title="WeRSS API",
    description="微信公众号RSS生成服务API文档",
    version="1.0.0",
    docs_url="/api/docs" if api_docs_enabled else None,
    redoc_url="/api/redoc" if api_docs_enabled else None,
    # 指定OpenAPI schema路径
    openapi_url="/api/openapi.json" if api_docs_enabled else None,
    openapi_tags=[
        {
            "name": "认证",
            "description": "用户认证相关接口",
        }
    ],
    swagger_ui_parameters={
        "persistAuthorization": True,
        "withCredentials": True,
    }
)

# 同源部署不需要 CORS。只有明确配置可信 Origin 时才启用，禁止通配符。
cors_origins = _configured_cors_origins()
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    )

# AK认证中间件
app.add_middleware(AKMiddleware)

@app.middleware("http")
async def add_custom_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Version"] = VERSION
    response.headers["X-Powered-By"] = "Rachel"
    response.headers["GITHUB"] = "https://github.com/rachelos/we-mp-rss"
    response.headers["Server"] = cfg.get("app_name", "WeRSS")
    # 管理页面不允许被第三方站点嵌入；CSP 是现代浏览器的主控制，XFO 兼容旧客户端。
    if not request.url.path.startswith(f"{API_BASE}/proxy/"):
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
        response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
# 创建API路由分组
api_router = APIRouter(prefix=f"{API_BASE}")
api_router.include_router(auth_router)
api_router.include_router(user_router)
api_router.include_router(article_router)
api_router.include_router(wx_router)
api_router.include_router(config_router)
api_router.include_router(task_router)
api_router.include_router(sys_info_router)
api_router.include_router(tags_router)
api_router.include_router(export_router)
api_router.include_router(tools_router)
api_router.include_router(github_router)
api_router.include_router(cascade_router)
api_router.include_router(env_exception_router)
api_router.include_router(filter_rule_router)
api_router.include_router(task_queue_router)
api_router.include_router(proxy_router)
api_router.include_router(weread_router)

resource_router = APIRouter(prefix="/static")
resource_router.include_router(res_router)
feeds_router = APIRouter()
feeds_router.include_router(rss_router)
feeds_router.include_router(feed_router)
# 注册API路由分组
app.include_router(api_router)
app.include_router(resource_router)
app.include_router(feeds_router)
app.include_router(views_router)

# 静态文件服务配置
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
app.mount("/static", StaticFiles(directory="static"), name="static")
from core.res.avatar import files_dir
app.mount("/files", StaticFiles(directory=files_dir), name="files")
# app.mount("/docs", StaticFiles(directory="./data/docs"), name="docs")
@app.get("/{path:path}",tags=['默认'],include_in_schema=False)
async def serve_vue_app(request: Request, path: str):
    """处理Vue应用路由"""
    # 排除API和静态文件路由
    if path.startswith(('api', 'assets', 'static')) or path in ['favicon.ico','vite.svg','logo.svg']:
        return Response(status_code=404)
    
    # 返回Vue入口文件
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    
    return Response(status_code=404)

@app.get("/",tags=['默认'],include_in_schema=False)
async def serve_root(request: Request):
    """处理根路由"""
    return await serve_vue_app(request, "")
