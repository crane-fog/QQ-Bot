# Gitea REST API 的最小客户端，仅覆盖 QQ 群回帖所需的端点。
from httpx import AsyncClient, Timeout

from src.gitea.Models import Attachment, Comment, Issue
from src.PrintLog import Log


class GiteaApiError(Exception):
    """
    Gitea API 请求失败。

    :param status_code: 非 2xx 响应的 HTTP 状态码，网络错误时为 None
    """

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class GiteaApi:
    def __init__(self, api_url: str, api_token: str):
        self.api_url = api_url.strip().rstrip("/")
        if not self.api_url:
            raise ValueError("[Gitea] api_url 不能为空")
        self.api_token = api_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"token {self.api_token}"}

    def _issue_url(self, full_name: str, number: int, *parts: str) -> str:
        suffix = f"/{'/'.join(parts)}" if parts else ""
        return f"{self.api_url}/api/v1/repos/{full_name}/issues/{number}{suffix}"

    async def get_issue(self, full_name: str, number: int) -> Issue:
        """获取单个 issue，用于回帖前校验编号是否存在。"""
        return Issue.model_validate(
            await self._request_json("GET", self._issue_url(full_name, number))
        )

    async def list_issue_comments(self, full_name: str, number: int) -> list[Comment]:
        """拉取 issue 的全部评论，用于构建合并转发消息。"""
        url = self._issue_url(full_name, number, "comments")
        payload = await self._request_json("GET", url)
        return [Comment.model_validate(c) for c in payload]

    async def create_issue_comment(self, full_name: str, number: int, body: str) -> Comment:
        """在 issue 下新建评论，返回创建后的评论（含 html_url）。"""
        url = self._issue_url(full_name, number, "comments")
        payload = await self._request_json("POST", url, json={"body": body})
        return Comment.model_validate(payload)

    async def update_issue_comment(self, full_name: str, comment_id: int, body: str) -> None:
        """编辑已有评论正文，用于附件上传后回填图片链接。"""
        url = f"{self.api_url}/api/v1/repos/{full_name}/issues/comments/{comment_id}"
        await self._request_json("PATCH", url, json={"body": body})

    async def create_comment_attachment(
        self, full_name: str, comment_id: int, file_path: str, filename: str, mime: str
    ) -> Attachment:
        """上传文件作为评论附件，返回含 uuid 的附件信息；文件对象直传 multipart，避免大文件整体进内存。"""
        url = f"{self.api_url}/api/v1/repos/{full_name}/issues/comments/{comment_id}/assets"
        try:
            f = open(file_path, "rb")
        except OSError as e:
            # 打开失败（文件被清理/权限变化）与 HTTP 错误同型处理，避免 OSError 冒泡出调用方的 GiteaApiError 捕获范围
            raise GiteaApiError(f"打开附件文件失败：{file_path}, error={e}") from e
        with f:
            payload = await self._request_json(
                "POST", url, files={"attachment": (filename, f, mime)}
            )
        return Attachment.model_validate(payload)

    async def _request_json(self, method: str, url: str, **kwargs) -> dict | list:
        try:
            async with AsyncClient(timeout=Timeout(10)) as client:
                resp = await client.request(method, url, headers=self._headers(), **kwargs)
        except Exception as e:
            raise GiteaApiError(f"Gitea API 请求失败：{e}") from e
        if resp.status_code >= 400:
            Log.warning(f"Gitea API 返回 {resp.status_code}：url={url}, body={resp.text[:200]}")
            raise GiteaApiError(f"Gitea API 返回 {resp.status_code}", resp.status_code)
        try:
            return resp.json()
        except Exception as e:
            raise GiteaApiError(f"Gitea API 响应解析失败：{e}") from e
