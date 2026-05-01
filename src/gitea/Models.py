from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GiteaBaseModel(BaseModel):
    # Gitea 不同版本可能新增 webhook 字段，这里忽略暂时用不到的字段。
    model_config = ConfigDict(extra="ignore")


# 它是 Commit 中的 author/committer 信息，
# 对应 Gitea modules/structs/hook.go 中的 PayloadUser。
class CommitUser(GiteaBaseModel):
    name: str
    email: str
    username: str


# Gitea API 用户模型，用于仓库所有者、sender、pusher、issue 作者等字段。
class User(GiteaBaseModel):
    id: int
    login: str
    username: str | None = None
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


class Commit(GiteaBaseModel):
    id: str
    message: str
    url: str
    author: CommitUser | None = None
    committer: CommitUser | None = None
    timestamp: datetime
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    modified: list[str] = Field(default_factory=list)


class Permission(GiteaBaseModel):
    admin: bool
    push: bool
    pull: bool


# 仓库模型。多个 webhook 事件都会嵌入同一个 Gitea Repository 结构，
# 所以这里保留的字段比当前 formatter 实际使用的更多。
class Repository(GiteaBaseModel):
    id: int
    owner: User | None = None
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
    ssh_url: str | None = None
    clone_url: str | None = None
    original_url: str | None = None
    website: str | None = None
    stars_count: int | None = None
    forks_count: int | None = None
    watchers_count: int | None = None
    branch_count: int | None = None
    open_issues_count: int | None = None
    open_pr_counter: int | None = None
    release_counter: int | None = None
    default_branch: str | None = None
    default_target_branch: str | None = None
    archived: bool | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    archived_at: datetime | None = None
    permissions: Permission | None = None
    has_code: bool | None = None
    has_issues: bool | None = None
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
    licenses: list[str] = Field(default_factory=list)


class Attachment(GiteaBaseModel):
    id: int
    name: str
    size: int
    download_count: int
    created_at: datetime
    uuid: str
    browser_download_url: str


class Label(GiteaBaseModel):
    id: int | None = None
    name: str | None = None
    exclusive: bool | None = None
    is_archived: bool | None = None
    color: str | None = None
    description: str | None = None
    url: str | None = None


class Milestone(GiteaBaseModel):
    id: int
    title: str
    description: str | None = None
    state: str | None = None
    open_issues: int | None = None
    closed_issues: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    closed_at: datetime | None = None
    due_on: datetime | None = None


# Issue 相关嵌套模型。Gitea 会在 Issue.pull_request 中放 PR 元信息，
# 而 PR 评论 payload 中会额外携带完整的 pull_request 数据。
class PullRequestMeta(GiteaBaseModel):
    merged: bool | None = None
    merged_at: datetime | None = None
    draft: bool | None = None
    html_url: str | None = None


class RepositoryMeta(GiteaBaseModel):
    id: int
    name: str
    owner: str
    full_name: str


class Issue(GiteaBaseModel):
    id: int
    url: str
    html_url: str
    number: int
    user: User
    original_author: str | None = None
    original_author_id: int | None = None
    title: str
    body: str | None = None
    ref: str | None = None
    assets: list[Attachment] = Field(default_factory=list)
    labels: list[Label] = Field(default_factory=list)
    milestone: Milestone | None = None
    assignee: User | None = None
    assignees: list[User] = Field(default_factory=list)
    state: str
    is_locked: bool
    comments: int
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    due_date: datetime | None = None
    time_estimate: int | None = None
    pull_request: PullRequestMeta | None = None
    repository: RepositoryMeta | None = None
    pin_order: int | None = None
    content_version: int | None = None

    @field_validator("assets", "labels", "assignees", mode="before")
    @classmethod
    def none_list_as_empty(cls, value):
        return [] if value is None else value


class Comment(GiteaBaseModel):
    id: int
    html_url: str
    pull_request_url: str | None = None
    issue_url: str
    user: User
    original_author: str | None = None
    original_author_id: int | None = None
    body: str | None = None
    assets: list[Attachment] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @field_validator("assets", mode="before")
    @classmethod
    def none_list_as_empty(cls, value):
        return [] if value is None else value


class ChangesFromPayload(GiteaBaseModel):
    # from 是 Python 关键字，模型里用 from_，但仍然接收 JSON 中的 from 字段。
    from_: str | None = Field(default=None, alias="from")


class ChangesPayload(GiteaBaseModel):
    title: ChangesFromPayload | None = None
    body: ChangesFromPayload | None = None
    ref: ChangesFromPayload | None = None
    added_labels: list[Label] = Field(default_factory=list)
    removed_labels: list[Label] = Field(default_factory=list)

    @field_validator("added_labels", "removed_labels", mode="before")
    @classmethod
    def none_list_as_empty(cls, value):
        return [] if value is None else value


class PRBranchInfo(GiteaBaseModel):
    label: str | None = None
    ref: str | None = None
    sha: str | None = None
    repo_id: int | None = None
    repo: Repository | None = None


class PullRequest(GiteaBaseModel):
    id: int
    url: str
    number: int
    user: User
    title: str
    body: str | None = None
    labels: list[Label] = Field(default_factory=list)
    milestone: Milestone | None = None
    assignee: User | None = None
    assignees: list[User] = Field(default_factory=list)
    requested_reviewers: list[User] = Field(default_factory=list)
    state: str
    draft: bool | None = None
    is_locked: bool | None = None
    comments: int | None = None
    html_url: str
    diff_url: str | None = None
    patch_url: str | None = None
    mergeable: bool | None = None
    merged: bool | None = None
    merged_at: datetime | None = None
    merge_commit_sha: str | None = None
    merged_by: User | None = None
    allow_maintainer_edit: bool | None = None
    base: PRBranchInfo | None = None
    head: PRBranchInfo | None = None
    merge_base: str | None = None
    due_date: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    closed_at: datetime | None = None
    pin_order: int | None = None
    content_version: int | None = None

    @field_validator("labels", "assignees", "requested_reviewers", mode="before")
    @classmethod
    def none_list_as_empty(cls, value):
        return [] if value is None else value


# WebhookHandler 当前支持的根 payload 模型。
class GiteaPushEvent(GiteaBaseModel):
    ref: str
    before: str
    after: str
    compare_url: str
    commits: list[Commit] = Field(default_factory=list)
    total_commits: int = 0
    head_commit: Commit | None = None
    repository: Repository
    pusher: User
    sender: User


class GiteaIssuesEvent(GiteaBaseModel):
    # Gitea 的 issue_label/issue_assign/issue_milestone 也使用同一套 IssuePayload 结构。
    action: str
    number: int
    changes: ChangesPayload | None = None
    issue: Issue
    repository: Repository
    sender: User
    commit_id: str | None = None


class GiteaIssueCommentEvent(GiteaBaseModel):
    action: str
    issue: Issue
    pull_request: PullRequest | None = None
    comment: Comment
    changes: ChangesPayload | None = None
    repository: Repository
    sender: User
    is_pull: bool


# 当前支持的 webhook payload 联合类型。之后支持 pull_request、release 等根事件时再扩展。
type GiteaWebhookEvent = GiteaPushEvent | GiteaIssuesEvent | GiteaIssueCommentEvent
