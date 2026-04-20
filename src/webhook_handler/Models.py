from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# 1. 提交者信息模型 (对应 commits 中的 author 和 committer)
class CommitUser(BaseModel):
    name: str
    email: str
    username: str


# 2. 通用用户模型 (对应 repository.owner, pusher, sender)
class User(BaseModel):
    id: int
    login: str
    full_name: str
    email: str
    avatar_url: str
    username: str


# 3. 单次提交模型
class Commit(BaseModel):
    id: str
    message: str
    url: str
    author: CommitUser
    committer: CommitUser
    timestamp: datetime


# 4. 仓库信息模型
class Repository(BaseModel):
    id: int
    owner: User
    name: str
    full_name: str
    description: str
    private: bool
    fork: bool
    html_url: str
    ssh_url: str
    clone_url: str
    website: str
    stars_count: int
    forks_count: int
    watchers_count: int
    open_issues_count: int
    default_branch: str
    created_at: datetime
    updated_at: datetime


# 5. 根模型：完整的 Webhook Push 事件
class GiteaPushEvent(BaseModel):
    secret: str
    ref: str
    before: str
    after: str
    compare_url: str
    commits: list[Commit]
    repository: Repository
    pusher: User
    sender: User


# 6. issue/评论事件中出现的完整用户模型
class WebhookUser(BaseModel):
    id: int
    login: str
    username: str
    login_name: str = ""
    source_id: int = 0
    full_name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    html_url: str | None = None
    language: str | None = None
    is_admin: bool | None = None
    last_login: datetime | None = None
    created: datetime | None = None
    restricted: bool | None = None
    active: bool | None = None
    prohibit_login: bool | None = None
    location: str | None = None
    website: str | None = None
    description: str | None = None
    visibility: str | None = None
    followers_count: int | None = None
    following_count: int | None = None
    starred_repos_count: int | None = None


class Asset(BaseModel):
    id: int
    name: str
    size: int
    download_count: int
    created_at: datetime
    uuid: str
    browser_download_url: str


class IssueLabel(BaseModel):
    id: int | None = None
    name: str | None = None
    color: str | None = None
    description: str | None = None
    url: str | None = None


class IssueRepositoryRef(BaseModel):
    id: int
    name: str
    owner: str
    full_name: str


class Issue(BaseModel):
    id: int
    url: str
    html_url: str
    number: int
    user: WebhookUser
    original_author: str | None = None
    original_author_id: int | None = None
    title: str
    body: str | None = None
    ref: str | None = None
    assets: list[Asset] = Field(default_factory=list)
    labels: list[IssueLabel] = Field(default_factory=list)
    milestone: dict[str, Any] | None = None
    assignee: WebhookUser | None = None
    assignees: list[WebhookUser] | None = None
    state: str
    is_locked: bool
    comments: int
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    due_date: datetime | None = None
    time_estimate: int | None = None
    pull_request: dict[str, Any] | None = None
    repository: IssueRepositoryRef
    pin_order: int | None = None


class Comment(BaseModel):
    id: int
    html_url: str
    pull_request_url: str | None = None
    issue_url: str
    user: WebhookUser
    original_author: str | None = None
    original_author_id: int | None = None
    body: str | None = None
    assets: list[Asset] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class Permissions(BaseModel):
    admin: bool
    push: bool
    pull: bool


class InternalTracker(BaseModel):
    enable_time_tracker: bool
    allow_only_contributors_to_track_time: bool
    enable_issue_dependencies: bool


class IssueEventRepository(BaseModel):
    id: int
    owner: WebhookUser
    name: str
    full_name: str
    description: str | None = None
    empty: bool | None = None
    private: bool
    fork: bool
    template: bool | None = None
    mirror: bool | None = None
    size: int | None = None
    language: str | None = None
    languages_url: str | None = None
    html_url: str
    url: str | None = None
    link: str | None = None
    ssh_url: str
    clone_url: str
    original_url: str | None = None
    website: str | None = None
    stars_count: int
    forks_count: int
    watchers_count: int
    open_issues_count: int
    open_pr_counter: int | None = None
    release_counter: int | None = None
    default_branch: str
    archived: bool | None = None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    permissions: Permissions | None = None
    has_code: bool | None = None
    has_issues: bool | None = None
    internal_tracker: InternalTracker | None = None
    has_wiki: bool | None = None
    has_pull_requests: bool | None = None
    has_projects: bool | None = None
    projects_mode: str | None = None
    has_releases: bool | None = None
    has_packages: bool | None = None
    has_actions: bool | None = None
    ignore_whitespace_conflicts: bool | None = None
    allow_merge_commits: bool | None = None
    allow_rebase: bool | None = None
    allow_rebase_explicit: bool | None = None
    allow_squash_merge: bool | None = None
    allow_fast_forward_only_merge: bool | None = None
    allow_rebase_update: bool | None = None
    allow_manual_merge: bool | None = None
    autodetect_manual_merge: bool | None = None
    default_delete_branch_after_merge: bool | None = None
    default_merge_style: str | None = None
    default_allow_maintainer_edit: bool | None = None
    avatar_url: str | None = None
    internal: bool | None = None
    mirror_interval: str | None = None
    object_format_name: str | None = None
    mirror_updated: datetime | None = None
    topics: list[str] = Field(default_factory=list)
    licenses: list[dict[str, Any]] = Field(default_factory=list)


# 7. issues 事件
class GiteaIssuesEvent(BaseModel):
    action: str
    number: int
    issue: Issue
    repository: IssueEventRepository
    sender: WebhookUser
    commit_id: str | None = None


# 8. issue_comment 事件
class GiteaIssueCommentEvent(BaseModel):
    action: str
    issue: Issue
    comment: Comment
    repository: IssueEventRepository
    sender: WebhookUser
    is_pull: bool


# 9. issue_label 事件
class GiteaIssueLabelEvent(BaseModel):
    action: str
    number: int
    issue: Issue
    repository: IssueEventRepository
    sender: WebhookUser
    commit_id: str | None = None


type GiteaWebhookEvent = (
    GiteaPushEvent | GiteaIssuesEvent | GiteaIssueCommentEvent | GiteaIssueLabelEvent
)
