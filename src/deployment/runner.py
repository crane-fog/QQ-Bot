import asyncio
import json
import os
import re
import tempfile
from pathlib import Path

from .config import ComposeDocument, DeploymentError, plain


def sensitive_values(value, values, sensitive=False):
    if isinstance(value, dict):
        for key, item in value.items():
            sensitive_values(
                item,
                values,
                sensitive
                or key == "environment"
                or bool(re.search(r"password|passwd|token|secret|api_key", key, re.I)),
            )
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str) and "=" in item:
                sensitive_values(item.split("=", 1)[1], values, sensitive)
            else:
                sensitive_values(item, values, sensitive)
    elif sensitive and value is not None and str(value):
        values.add(str(value))


class ComposeRunner:
    """Docker subprocess boundary. No request can supply arbitrary CLI arguments.

    Only client-side Compose operations are used (``config``); the panel never
    touches the Docker daemon, so no socket access is required.
    """

    def __init__(self, root: Path, project: str):
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", project):
            raise DeploymentError("无效的 Compose 项目名称")
        self.root = Path(root).resolve()
        self.project = project
        self.prefix = [
            "docker",
            "compose",
            "--ansi",
            "never",
            "--project-directory",
            str(self.root),
            "-p",
            project,
        ]
        env_file = self.root / ".env"
        if env_file.is_file():
            self.prefix += ["--env-file", str(env_file)]
        self.environment = {
            key: value for key, value in os.environ.items() if not key.startswith("COMPOSE_")
        }
        # Host Compose environment variables must not alter the panel's compose invocations.
        self.environment["COMPOSE_PROFILES"] = ""
        self.known_sensitive = set()

    def redaction_values(self, source):
        values = self.known_sensitive.copy()
        if source:
            sensitive_values(plain(ComposeDocument.decode(source)), values)
        env_file = self.root / ".env"
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    value = line.split("=", 1)[1].strip().strip("\"'")
                    if value:
                        values.add(value)
        return values

    def redact(self, text, source="", values=None):
        if values is None:
            values = self.redaction_values(source)
        for value in sorted(values, key=len, reverse=True):
            text = text.replace(value, "[REDACTED]")
        text = re.sub(r"(://[^\s:/]+:)[^\s@]+@", r"\1[REDACTED]@", text)
        return re.sub(
            r"(?i)((?:password|passwd|token|secret|api_key)\s*[=:]\s*)[^\s,]+",
            r"\1[REDACTED]",
            text,
        )

    async def execute(self, args, source="", timeout=60):
        values = self.redaction_values(source)
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                cwd=self.root,
                env=self.environment,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError:
            raise DeploymentError(
                "无法启动 Docker CLI，请检查运行环境是否安装 Docker CLI", 503
            ) from None
        chunks = {"stdout": bytearray(), "stderr": bytearray()}

        async def read(stream, name):
            while chunk := await stream.read(4096):
                chunks[name].extend(chunk)
                if len(chunks[name]) > 4 * 1024 * 1024:
                    raise DeploymentError("Docker 输出超过限制", 503)

        async def monitor():
            await asyncio.gather(
                read(process.stdout, "stdout"), read(process.stderr, "stderr"), process.wait()
            )

        try:
            await asyncio.wait_for(monitor(), timeout)
        except (TimeoutError, asyncio.CancelledError, DeploymentError) as exc:
            if process.returncode is None:
                process.kill()
            await process.wait()
            if isinstance(exc, TimeoutError):
                raise DeploymentError("Docker 操作超时，请检查实际容器状态", 503) from None
            raise
        stdout = chunks["stdout"].decode(errors="replace")
        stderr = chunks["stderr"].decode(errors="replace")
        if process.returncode:
            raise DeploymentError(
                "Docker 操作失败：" + self.redact(stderr or stdout, values=values)[-8000:], 503
            )
        return stdout

    async def validate(self, source):
        descriptor, temporary = tempfile.mkstemp(
            prefix=".compose-check-", suffix=".yaml", dir=self.root
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                output.write(source)
            args = self.prefix + ["-f", temporary]
            await self.execute(args + ["config", "--quiet"], source)
            result = json.loads(await self.execute(args + ["config", "--format", "json"], source))
            sensitive_values(result, self.known_sensitive)
            for service in result.get("services", {}).values():
                for mount in service.get("volumes") or []:
                    if mount.get("type") == "bind":
                        path = Path(mount["source"]).resolve()
                        # config cannot verify bind sources; paths under the deploy
                        # directory must exist to avoid silently creating empty
                        # directories. Sources outside it are not visible here.
                        if path.is_relative_to(self.root) and not path.exists():
                            raise DeploymentError(f"挂载源路径不存在：{path}")
            return result
        finally:
            Path(temporary).unlink(missing_ok=True)
