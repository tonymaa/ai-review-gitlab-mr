"""GitLab数据模型 - 用于表示GitLab API返回的数据结构"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class MRState(Enum):
    """MR状态枚举"""
    OPENED = "opened"
    CLOSED = "closed"
    LOCKED = "locked"
    MERGED = "merged"


@dataclass
class GitLabUser:
    """GitLab用户信息"""

    id: int
    username: str
    name: str
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    web_url: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GitLabUser":
        """从字典创建用户对象"""
        return cls(
            id=data.get("id", 0),
            username=data.get("username", ""),
            name=data.get("name", ""),
            email=data.get("email"),
            avatar_url=data.get("avatar_url"),
            web_url=data.get("web_url"),
        )


@dataclass
class MergeRequestInfo:
    """Merge Request信息"""

    # 基本信息
    id: int
    iid: int
    project_id: int
    title: str
    description: Optional[str]
    state: MRState

    # 分支信息
    source_branch: str
    target_branch: str

    # 作者信息
    author: GitLabUser
    assignees: List[GitLabUser] = field(default_factory=list)
    reviewers: List[GitLabUser] = field(default_factory=list)

    # 时间信息
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    # 统计信息
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0

    # 链接
    web_url: Optional[str] = None
    diff_refs: Optional[Dict[str, str]] = None

    # 标签和里程碑
    labels: List[str] = field(default_factory=list)
    milestone: Optional[str] = None

    # 其他
    work_in_progress: bool = False
    merge_when_pipeline_succeeds: bool = False
    has_conflicts: bool = False
    blocking_discussions_resolved: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MergeRequestInfo":
        """从字典创建MR对象"""
        # 解析作者信息
        author_data = data.get("author", {})
        author = GitLabUser.from_dict(author_data) if author_data else None

        # 解析assignees
        assignees = [
            GitLabUser.from_dict(assignee)
            for assignee in data.get("assignees", [])
        ]

        # 解析reviewers
        reviewers = [
            GitLabUser.from_dict(reviewer)
            for reviewer in data.get("reviewers", [])
        ]

        # 解析时间
        def parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
            if not dt_str:
                return None
            try:
                return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return None

        return cls(
            id=data.get("id", 0),
            iid=data.get("iid", 0),
            project_id=data.get("project_id", 0),
            title=data.get("title", ""),
            description=data.get("description"),
            state=MRState(data.get("state", "opened")),
            source_branch=data.get("source_branch", ""),
            target_branch=data.get("target_branch", ""),
            author=author,
            assignees=assignees,
            reviewers=reviewers,
            created_at=parse_datetime(data.get("created_at")),
            updated_at=parse_datetime(data.get("updated_at")),
            merged_at=parse_datetime(data.get("merged_at")),
            closed_at=parse_datetime(data.get("closed_at")),
            additions=data.get("additions", 0),
            deletions=data.get("deletions", 0),
            changed_files=data.get("changed_files", 0),
            web_url=data.get("web_url"),
            diff_refs=data.get("diff_refs"),
            labels=data.get("labels", []),
            milestone=data.get("milestone") or None,
            work_in_progress=data.get("work_in_progress", False),
            merge_when_pipeline_succeeds=data.get("merge_when_pipeline_succeeds", False),
            has_conflicts=data.get("has_conflicts", False),
            blocking_discussions_resolved=data.get(
                "blocking_discussions_resolved", True
            ),
        )

    def to_database_dict(self) -> Dict[str, Any]:
        """转换为数据库字典格式"""
        return {
            "gitlab_mr_id": self.id,
            "gitlab_project_id": self.project_id,
            "iid": self.iid,
            "title": self.title,
            "description": self.description,
            "state": self.state.value,
            "author_name": self.author.name if self.author else "",
            "author_username": self.author.username if self.author else "",
            "source_branch": self.source_branch,
            "target_branch": self.target_branch,
            "web_url": self.web_url,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "merged_at": self.merged_at,
        }


@dataclass
class DiffHunk:
    """Diff片段"""

    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    header: str
    lines: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiffHunk":
        return cls(
            old_start=data.get("old_start", 0),
            old_lines=data.get("old_lines", 0),
            new_start=data.get("new_start", 0),
            new_lines=data.get("new_lines", 0),
            header=data.get("header", ""),
            lines=data.get("lines", []),
        )


@dataclass
class DiffFile:
    """Diff文件信息"""

    old_path: str
    new_path: str
    old_file: Optional[str] = None
    new_file: bool = False
    renamed_file: bool = False
    deleted_file: bool = False

    # Diff内容
    diff: str = ""
    patch: Optional[str] = None
    diff_hunks: List[DiffHunk] = field(default_factory=list)

    # 统计
    additions: int = 0
    deletions: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiffFile":
        """从字典创建DiffFile对象"""
        diff_hunks = [
            DiffHunk.from_dict(hunk)
            for hunk in data.get("diff_hunks", [])
        ]

        return cls(
            old_path=data.get("old_path", ""),
            new_path=data.get("new_path", ""),
            old_file=data.get("old_file"),
            new_file=data.get("new_file", False),
            renamed_file=data.get("renamed_file", False),
            deleted_file=data.get("deleted_file", False),
            diff=data.get("diff", ""),
            patch=data.get("patch"),
            diff_hunks=diff_hunks,
            additions=data.get("additions", 0),
            deletions=data.get("deletions", 0),
        )

    def to_database_dict(self) -> Dict[str, Any]:
        """转换为数据库字典格式"""
        return {
            "old_path": self.old_path,
            "new_path": self.new_path,
            "is_new_file": self.new_file,
            "is_renamed_file": self.renamed_file,
            "is_deleted_file": self.deleted_file,
            "diff": self.diff,
            "patch": self.patch,
            "additions": self.additions,
            "deletions": self.deletions,
        }

    def get_display_path(self) -> str:
        """获取显示用的文件路径"""
        if self.new_file:
            return self.new_path
        if self.deleted_file:
            return self.old_path
        if self.renamed_file:
            return f"{self.old_path} → {self.new_path}"
        return self.new_path or self.old_path


@dataclass
class LineChange:
    """代码行变更信息"""

    line_number: int
    old_line_number: Optional[int]
    content: str
    type: str  # addition, deletion, context, header


@dataclass
class ReviewComment:
    """审查评论"""

    id: Optional[int]
    content: str
    line_number: Optional[int]
    file_path: str
    comment_type: str = "ai_review"  # ai_review, user_comment, etc.
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIReviewResult:
    """AI审查结果"""

    # 基本信息
    provider: str  # openai, ollama, etc.
    model: str

    # 整体评估
    summary: str
    overall_score: int  # 1-10分
    issues_count: int
    suggestions_count: int

    # 详细意见 (按文件和行组织)
    file_reviews: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    # 分类统计
    critical_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    tokens_used: Optional[int] = None

    def to_database_dict(self) -> Dict[str, Any]:
        """转换为数据库字典格式"""
        import json

        return {
            "review_type": "ai_review",
            "provider": self.provider,
            "model": self.model,
            "summary": self.summary,
            "overall_score": self.overall_score,
            "issues_count": self.issues_count,
            "suggestions_count": self.suggestions_count,
            "details": json.dumps({
                "file_reviews": self.file_reviews,
                "critical_issues": self.critical_issues,
                "warnings": self.warnings,
                "suggestions": self.suggestions,
                "tokens_used": self.tokens_used,
            }),
        }


@dataclass
class ProjectInfo:
    """项目信息"""

    id: int
    name: str
    path: str
    path_with_namespace: str
    description: Optional[str] = None
    default_branch: str = "main"
    web_url: Optional[str] = None
    avatar_url: Optional[str] = None
    star_count: int = 0
    forks_count: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectInfo":
        """从字典创建项目对象"""
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            path=data.get("path", ""),
            path_with_namespace=data.get("path_with_namespace", ""),
            description=data.get("description"),
            default_branch=data.get("default_branch", "main"),
            web_url=data.get("web_url"),
            avatar_url=data.get("avatar_url"),
            star_count=data.get("star_count", 0),
            forks_count=data.get("forks_count", 0),
        )

    def __str__(self) -> str:
        return f"{self.path_with_namespace}"
