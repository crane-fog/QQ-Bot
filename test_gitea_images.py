"""Gitea 评论附件 / markdown 图片解析的单元测试。"""

from src.gitea.GiteaEventFormatter import (
    FileSegment,
    ForwardPlan,
    GiteaEventFormatter,
    ImageSegment,
    TextSegment,
    _extract_images,
    _parse_comment_segments,
    _resolve_image_url,
)
from src.gitea.Models import Attachment

NOW = "2026-04-29T12:00:00Z"
REPO_HTML_URL = "https://gitea.example.com/org/repo"


def _attachment(name: str, url: str, size: int = 10) -> Attachment:
    return Attachment.model_validate(
        {
            "id": 1,
            "name": name,
            "size": size,
            "download_count": 0,
            "created_at": NOW,
            "uuid": "uuid",
            "browser_download_url": url,
        }
    )


def test_parse_comment_segments_preserves_original_order():
    """body 中文字与图片的交替顺序应被保留。"""
    body = "hello ![alt text](/attachments/abc.png) world"
    segments = _parse_comment_segments(body, [], REPO_HTML_URL)

    assert len(segments) == 3
    assert isinstance(segments[0], TextSegment)
    assert segments[0].text == "hello "
    assert isinstance(segments[1], ImageSegment)
    assert segments[1].url == "https://gitea.example.com/attachments/abc.png"
    assert segments[1].alt == "alt text"
    assert isinstance(segments[2], TextSegment)
    assert segments[2].text == " world\n\n"


def test_parse_comment_segments_image_assets_appended_with_dedup():
    """所有附件都作为 FileSegment 追加（图片由 body markdown 处理）。"""
    body = "see ![pic](/attachments/uuid)"
    assets = [_attachment("pic.png", "https://gitea.example.com/attachments/uuid")]
    segments = _parse_comment_segments(body, assets, REPO_HTML_URL)

    # body 中的内联图仍是 ImageSegment，assets 中的图片变成 FileSegment
    images = [s for s in segments if isinstance(s, ImageSegment)]
    assert len(images) == 1
    assert images[0].url == "https://gitea.example.com/attachments/uuid"
    files = [s for s in segments if isinstance(s, FileSegment)]
    assert len(files) == 1
    assert files[0].name == "pic.png"
    assert files[0].download_url == "https://gitea.example.com/attachments/uuid"


def test_parse_comment_segments_non_image_assets_as_files():
    """所有附件统一生成 FileSegment，不再区分图片/非图片。"""
    body = "text"
    assets = [
        _attachment("report.pdf", "https://gitea.example.com/attachments/pdf", size=2048),
        _attachment("shot.png", "https://gitea.example.com/attachments/shot"),
    ]
    segments = _parse_comment_segments(body, assets, REPO_HTML_URL)

    files = [s for s in segments if isinstance(s, FileSegment)]
    images = [s for s in segments if isinstance(s, ImageSegment)]
    assert len(files) == 2
    assert files[0].name == "report.pdf"
    assert files[0].size == 2048
    assert files[1].name == "shot.png"
    assert files[1].download_url == "https://gitea.example.com/attachments/shot"
    assert len(images) == 0


def test_parse_comment_segments_multiple_inline_images():
    """多张内联图片保持与文本的交错顺序。"""
    body = "a ![1](a.png) b ![2](b.png) c"
    segments = _parse_comment_segments(body, [], REPO_HTML_URL)

    assert len(segments) == 5
    assert isinstance(segments[0], TextSegment) and segments[0].text == "a "
    assert isinstance(segments[1], ImageSegment) and segments[1].url.endswith("a.png")
    assert isinstance(segments[2], TextSegment) and segments[2].text == " b "
    assert isinstance(segments[3], ImageSegment) and segments[3].url.endswith("b.png")
    assert isinstance(segments[4], TextSegment) and segments[4].text == " c\n\n"


def test_resolve_image_url_handles_absolute_relative_and_root_paths():
    assert _resolve_image_url("https://other.com/x.png", REPO_HTML_URL) == "https://other.com/x.png"
    assert (
        _resolve_image_url("/attachments/uuid", REPO_HTML_URL)
        == "https://gitea.example.com/attachments/uuid"
    )
    # urljoin 相对路径会替换 base 最后一段，符合 RFC 3986 规范
    assert (
        _resolve_image_url("raw/main/img.png", REPO_HTML_URL)
        == "https://gitea.example.com/org/raw/main/img.png"
    )
    # 仓库内 raw 路径通常以 /org/repo/ 开头，使用站点绝对路径
    assert (
        _resolve_image_url("/org/repo/raw/main/img.png", REPO_HTML_URL)
        == "https://gitea.example.com/org/repo/raw/main/img.png"
    )


def test_extract_images_collects_all_image_segments():
    segs = [
        TextSegment(text="a"),
        ImageSegment(url="x.png", alt="x"),
        TextSegment(text="b"),
        ImageSegment(url="y.png", alt="y"),
    ]
    images = _extract_images(segs)
    assert len(images) == 2
    assert images[0].url == "x.png"
    assert images[1].url == "y.png"


def test_issue_comment_plain_returns_text_and_image_list():
    from src.gitea.Models import GiteaIssueCommentEvent

    payload = {
        "action": "created",
        "issue": {
            "id": 200,
            "url": "https://gitea.example.com/api/issues/1",
            "html_url": "https://gitea.example.com/org/repo/issues/1",
            "number": 1,
            "user": {"id": 1, "login": "alice"},
            "title": "T",
            "body": "body",
            "labels": [],
            "state": "open",
            "is_locked": False,
            "comments": 1,
            "created_at": NOW,
            "updated_at": NOW,
            "assets": [],
        },
        "comment": {
            "id": 300,
            "html_url": "https://gitea.example.com/org/repo/issues/1#comment-300",
            "issue_url": "https://gitea.example.com/api/issues/1",
            "user": {"id": 1, "login": "alice"},
            "body": "see ![x](/attachments/abc.png)",
            "assets": [],
            "created_at": NOW,
            "updated_at": NOW,
        },
        "repository": {
            "id": 100,
            "name": "repo",
            "owner": {"id": 1, "login": "org"},
            "full_name": "org/repo",
            "private": True,
            "fork": False,
            "html_url": REPO_HTML_URL,
        },
        "sender": {"id": 1, "login": "alice"},
        "is_pull": False,
    }
    event = GiteaIssueCommentEvent.model_validate(payload)
    text, images = GiteaEventFormatter().issue_comment_plain(event, "issue_comment")

    assert "[图片: x]" in text
    assert len(images) == 1
    assert images[0].url == "https://gitea.example.com/attachments/abc.png"


def test_issue_comment_forward_returns_forwardplan_with_segments():
    """issue_comment_forward 返回的 ContentNode 应有 segments 保留原始顺序。"""
    from src.gitea.Models import Comment, GiteaIssueCommentEvent

    payload = {
        "action": "created",
        "issue": {
            "id": 200,
            "url": "https://gitea.example.com/api/issues/1",
            "html_url": "https://gitea.example.com/org/repo/issues/1",
            "number": 1,
            "user": {"id": 1, "login": "alice"},
            "title": "T",
            "body": "issue body",
            "labels": [],
            "state": "open",
            "is_locked": False,
            "comments": 1,
            "created_at": NOW,
            "updated_at": NOW,
            "assets": [],
        },
        "comment": {
            "id": 300,
            "html_url": "https://gitea.example.com/org/repo/issues/1#comment-300",
            "issue_url": "https://gitea.example.com/api/issues/1",
            "user": {"id": 1, "login": "alice"},
            "body": "hello ![a](/attachments/abc.png) world",
            "assets": [],
            "created_at": NOW,
            "updated_at": NOW,
        },
        "repository": {
            "id": 100,
            "name": "repo",
            "owner": {"id": 1, "login": "org"},
            "full_name": "org/repo",
            "private": True,
            "fork": False,
            "html_url": REPO_HTML_URL,
        },
        "sender": {"id": 1, "login": "alice"},
        "is_pull": False,
    }
    event = GiteaIssueCommentEvent.model_validate(payload)
    comments = [
        Comment.model_validate(
            {
                "id": 300,
                "html_url": "https://gitea.example.com/org/repo/issues/1#comment-300",
                "issue_url": "https://gitea.example.com/api/issues/1",
                "user": {"id": 1, "login": "alice"},
                "body": "reply ![x](/attachments/uuid) end",
                "assets": [],
                "created_at": NOW,
                "updated_at": NOW,
            }
        )
    ]
    plan = GiteaEventFormatter().issue_comment_forward(event, comments)

    assert isinstance(plan, ForwardPlan)
    # 节点1: issue 正文
    assert len(plan.nodes[0].segments) == 1
    assert isinstance(plan.nodes[0].segments[0], TextSegment)
    assert plan.nodes[0].segments[0].text == "issue body\n\n"
    # 节点2: 评论，保留文字-图片-文字顺序
    assert len(plan.nodes[1].segments) == 3
    assert isinstance(plan.nodes[1].segments[0], TextSegment)
    assert isinstance(plan.nodes[1].segments[1], ImageSegment)
    assert isinstance(plan.nodes[1].segments[2], TextSegment)
    assert plan.nodes[1].segments[0].text == "reply "
    assert plan.nodes[1].segments[2].text == " end\n\n"
