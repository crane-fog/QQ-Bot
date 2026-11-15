import asyncio
import hmac
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import Authentication
from .config import MAX_SOURCE, ComposeDocument, DeploymentError, plain
from .toml_config import CONFIG_NAMES, ConfigStore, form_values


class Draft(BaseModel):
    source: str = Field(max_length=MAX_SOURCE)
    version: str = Field(pattern=r"^[a-f0-9]{64}$")


class Version(BaseModel):
    version: str = Field(pattern=r"^[a-f0-9]{64}$")


class Patch(BaseModel):
    source: str = Field(max_length=MAX_SOURCE)
    service: str = Field(max_length=128)
    changes: dict


class Login(BaseModel):
    password: str = Field(max_length=1024)


class ConfigChange(BaseModel):
    path: list[str] = Field(min_length=1, max_length=3)
    value: str | bool | int | dict | None = None
    delete: bool = False


class ConfigPatch(BaseModel):
    source: str = Field(max_length=MAX_SOURCE)
    changes: list[ConfigChange] = Field(max_length=1000)


def create_app(
    document: ComposeDocument | None,
    runner,
    credentials,
    *,
    configs=None,
    bot_control=None,
    host=None,
):
    authentication = Authentication(credentials)
    # 默认只接受回环 Host；显式指定绑定地址即表示接受对应的访问面：
    # 具体 IP 一并放行其 Host，通配地址（0.0.0.0/::）不再限制 Host 头。
    allowed_hosts = {"localhost", "127.0.0.1", "::1"}
    if host is not None:
        allowed_hosts = None if host in {"0.0.0.0", "::"} else allowed_hosts | {host}
    login_lock = asyncio.Lock()
    if configs is None:
        if document is None:
            raise ValueError("源码模式需要配置目录")
        configs = ConfigStore(document.root, document.state)
    operation_lock = asyncio.Lock()
    state = document.state if document is not None else configs.state
    initial_password = state / "initial-password"

    app = FastAPI(
        title="Theresa Deployment",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.document = document
    app.state.runner = runner
    app.state.operation_lock = operation_lock
    app.state.bot_control = bot_control
    assets = Path(__file__).parent / "static"
    app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.exception_handler(DeploymentError)
    async def deployment_error(request, exc):
        return JSONResponse({"error": {"message": str(exc)}}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Pydantic's default response includes the rejected input, potentially a password.
        return JSONResponse(
            {"error": {"message": "请求字段或格式不正确，请检查输入"}}, status_code=422
        )

    @app.middleware("http")
    async def secure(request: Request, call_next):
        try:
            if allowed_hosts is not None and request.url.hostname not in allowed_hosts:
                raise DeploymentError("面板仅接受 localhost、回环地址或绑定 IP 的访问", 400)
            length = request.headers.get("content-length")
            if length and (not length.isdigit() or int(length) > 2 * MAX_SOURCE):
                raise DeploymentError("请求过大", 413)
            if request.url.path.startswith("/api/"):
                if request.method not in {"GET", "HEAD"}:
                    body = bytearray()
                    async for chunk in request.stream():
                        body.extend(chunk)
                        if len(body) > 2 * MAX_SOURCE:
                            raise DeploymentError("请求过大", 413)
                    request._body = bytes(body)
                if request.method not in {"GET", "HEAD"}:
                    origin = request.headers.get("origin")
                    if origin and origin != str(request.base_url).rstrip("/"):
                        raise DeploymentError("请求来源不匹配", 403)
                if request.url.path != "/api/login":
                    session = authentication.authenticate(request.cookies.get("panel_session", ""))
                    if request.method not in {"GET", "HEAD"} and not hmac.compare_digest(
                        request.headers.get("x-csrf-token", ""), session["csrf"]
                    ):
                        raise DeploymentError("CSRF 校验失败，请重新登录", 403)
                    request.state.session = session
                if document is None and request.url.path.startswith(
                    ("/api/compose", "/api/backups")
                ):
                    raise DeploymentError("源码模式不提供 Compose 管理", 404)
            response = await call_next(request)
        except DeploymentError as exc:
            response = JSONResponse({"error": {"message": str(exc)}}, status_code=exc.status)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    @app.get("/", response_class=HTMLResponse)
    async def index():
        template = Path(__file__).parent / "templates" / "deployment.html"
        return await asyncio.to_thread(template.read_text, encoding="utf-8")

    @app.post("/api/login")
    async def login(body: Login):
        async with login_lock:
            token, session = await asyncio.to_thread(authentication.login, body.password)
        initial_password.unlink(missing_ok=True)
        response = JSONResponse({"csrf": session["csrf"]})
        response.set_cookie(
            "panel_session", token, httponly=True, samesite="strict", max_age=8 * 3600, path="/"
        )
        return response

    @app.get("/api/session")
    async def session(request: Request):
        return {"csrf": request.state.session["csrf"]}

    @app.post("/api/logout")
    async def logout(request: Request):
        authentication.logout(request.cookies.get("panel_session", ""))
        response = JSONResponse({"success": True})
        response.delete_cookie("panel_session", path="/")
        return response

    @app.get("/api/capabilities")
    async def capabilities():
        return {
            "mode": "compose" if document is not None else "source",
            "compose": document is not None,
            "configs": list(CONFIG_NAMES),
            "bot_restart": bot_control is not None,
        }

    @app.post("/api/bot/restart")
    async def restart_bot():
        if bot_control is None:
            raise DeploymentError("Bot 子进程未在运行", 503)
        # 生产路径：FileControl 代理把请求转发给守护进程执行。
        if hasattr(bot_control, "restart_bot"):
            seq = await asyncio.to_thread(bot_control.restart_bot)
            status = await bot_control.wait_status(seq)
            if status is None:
                raise DeploymentError("守护进程未响应重启请求，请稍后重试", 503)
            if not status.get("ok"):
                raise DeploymentError(status.get("message") or "重启 Bot 失败", 503)
            return {"restarted": True}
        # 进程内句柄（测试/直跑）：直接触发重启事件。
        if bot_control.process is None:
            raise DeploymentError("Bot 子进程未在运行", 503)
        bot_control.restart.set()
        if bot_control.process.returncode is None:
            bot_control.process.terminate()
        return {"restarted": True}

    @app.get("/api/configs")
    async def config_list():
        def snapshot():
            return [{"name": name, "exists": configs.path(name).is_file()} for name in CONFIG_NAMES]

        return {"configs": await asyncio.to_thread(snapshot)}

    @app.get("/api/configs/{name}")
    async def read_config(name: str):
        return await asyncio.to_thread(configs.read, name)

    @app.post("/api/configs/{name}/patch")
    async def patch_config(name: str, body: ConfigPatch):
        source = await asyncio.to_thread(
            configs.patch, name, body.source, [change.model_dump() for change in body.changes]
        )
        document = await asyncio.to_thread(configs.validate, name, source)
        return {"source": source, "values": form_values(document.unwrap())}

    @app.post("/api/configs/{name}/validate")
    async def validate_config(name: str, body: Draft):
        await asyncio.to_thread(configs.check_version, name, body.version)
        document = await asyncio.to_thread(configs.validate, name, body.source)
        diff = await asyncio.to_thread(configs.diff, name, body.source)
        return {"valid": True, "diff": diff, "values": form_values(document.unwrap())}

    def config_available():
        if operation_lock.locked():
            raise DeploymentError("已有保存、恢复或应用操作正在运行", 409)

    @app.put("/api/configs/{name}")
    async def save_config(name: str, body: Draft):
        config_available()
        async with operation_lock:
            return await asyncio.to_thread(configs.save, name, body.source, body.version)

    @app.get("/api/configs/{name}/backups")
    async def config_backups(name: str):
        return {"backups": await asyncio.to_thread(configs.backups, name)}

    @app.get("/api/configs/{name}/backups/{backup_id}")
    async def preview_config_backup(name: str, backup_id: str):
        source = await asyncio.to_thread(configs.backup_source, name, backup_id)
        return {"source": source, "diff": await asyncio.to_thread(configs.diff, name, source)}

    @app.post("/api/configs/{name}/backups/{backup_id}/restore")
    async def restore_config(name: str, backup_id: str, body: Version):
        config_available()
        async with operation_lock:
            source = await asyncio.to_thread(configs.backup_source, name, backup_id)
            return await asyncio.to_thread(configs.save, name, source, body.version)

    @app.get("/api/compose")
    async def read_compose():
        return await asyncio.to_thread(document.read)

    @app.post("/api/compose/patch")
    async def patch_compose(body: Patch):
        source = await asyncio.to_thread(document.patch, body.source, body.service, body.changes)
        services = plain(await asyncio.to_thread(document.parse, source))["services"]
        return {"source": source, "services": services}

    @app.post("/api/compose/parse")
    async def parse_compose(body: Draft):
        return {"services": plain(await asyncio.to_thread(document.parse, body.source))["services"]}

    @app.post("/api/compose/validate")
    async def validate_compose(body: Draft):
        await asyncio.to_thread(document.check_version, body.version)
        await asyncio.to_thread(document.parse, body.source)
        await runner.validate(body.source)
        await asyncio.to_thread(document.check_version, body.version)
        return {"valid": True, "diff": await asyncio.to_thread(document.diff, body.source)}

    @app.put("/api/compose")
    async def save_compose(body: Draft):
        config_available()
        async with operation_lock:
            await asyncio.to_thread(document.check_version, body.version)
            await asyncio.to_thread(document.parse, body.source)
            await runner.validate(body.source)
            return await asyncio.to_thread(document.save, body.source, body.version)

    @app.get("/api/backups")
    async def backups():
        return {"backups": await asyncio.to_thread(document.backups)}

    @app.get("/api/backups/{backup_id}")
    async def preview_backup(backup_id: str):
        source = await asyncio.to_thread(document.backup_source, backup_id)
        return {"source": source, "diff": await asyncio.to_thread(document.diff, source)}

    @app.post("/api/backups/{backup_id}/restore")
    async def restore(backup_id: str, body: Version):
        config_available()
        async with operation_lock:
            await asyncio.to_thread(document.check_version, body.version)
            source = await asyncio.to_thread(document.backup_source, backup_id)
            await asyncio.to_thread(document.parse, source)
            await runner.validate(source)
            return await asyncio.to_thread(document.save, source, body.version)

    return app
