"""GitLab API 路由

提供 GitLab 相关的 REST API 接口
"""

import logging
import sys
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.gitlab.client import GitLabClient
from src.gitlab.models import MergeRequestInfo, DiffFile, ProjectInfo
from src.core.database import DatabaseManager
from src.core.auth import verify_token
from src.core.exceptions import (
    GitLabException,
    GitLabConnectionError,
    GitLabAuthError,
    GitLabNotFoundError,
    GitLabAPIError,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# HTTP Bearer 认证
security = HTTPBearer()


# ==================== 依赖注入 ====================

def get_db() -> DatabaseManager:
    """获取数据库管理器"""
    from server.main import app
    db: DatabaseManager = app.state.db
    return db


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: DatabaseManager = Depends(get_db),
) -> int:
    """从 token 获取当前用户 ID"""
    token = credentials.credentials
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=401,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=401,
            detail="Token 中没有用户信息",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Token 中的用户 ID 格式无效",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_gitlab_client(
    user_id: int = Depends(get_current_user_id),
    db: DatabaseManager = Depends(get_db),
) -> GitLabClient:
    """
    获取当前用户的 GitLab 客户端
    从数据库读取用户的配置并创建客户端
    """
    config = db.get_gitlab_config(user_id)
    if not config:
        raise HTTPException(
            status_code=400,
            detail="请先连接到 GitLab",
        )

    return GitLabClient(
        url=config["url"],
        token=config["token"],
    )


# ==================== Request/Response 模型 ====================

class ConnectRequest(BaseModel):
    """连接请求"""
    url: str
    token: str


class ConnectResponse(BaseModel):
    """连接响应"""
    status: str
    message: str
    user: dict | None = None


class ProjectModel(BaseModel):
    """项目模型"""
    id: int
    name: str
    path: str
    path_with_namespace: str
    description: str | None = None
    default_branch: str | None = None
    web_url: str

    @classmethod
    def from_info(cls, info: ProjectInfo) -> "ProjectModel":
        return cls(
            id=info.id,
            name=info.name,
            path=info.path,
            path_with_namespace=info.path_with_namespace,
            description=info.description,
            default_branch=info.default_branch,
            web_url=info.web_url,
        )


class MRModel(BaseModel):
    """MR 模型"""
    iid: int
    id: int
    project_id: int
    title: str
    description: str | None = None
    source_branch: str
    target_branch: str
    state: str
    author_name: str
    author_avatar: str | None = None
    web_url: str
    created_at: str
    updated_at: str
    user_notes_count: int = 0
    approved_by_current_user: bool = False
    approved_by: list[dict] = []
    assignees: list[dict] = []
    reviewers: list[dict] = []
    # 合并相关字段
    merge_status: str | None = None
    has_conflicts: bool = False
    can_merge: bool = False

    @classmethod
    def from_info(cls, info: MergeRequestInfo) -> "MRModel":
        # 处理时间字段转换为字符串
        created_at_str = info.created_at.isoformat() if info.created_at else ""
        updated_at_str = info.updated_at.isoformat() if info.updated_at else ""

        # 处理作者信息
        author_name = info.author.name if info.author else "Unknown"
        author_avatar = info.author.avatar_url if info.author else None

        # 处理 assignees, reviewers, approved_by
        assignees_list = [
            {"id": a.id, "name": a.name, "avatar_url": a.avatar_url}
            for a in info.assignees
        ]
        reviewers_list = [
            {"id": r.id, "name": r.name, "avatar_url": r.avatar_url}
            for r in info.reviewers
        ]
        approved_by_list = [
            {"id": a.id, "name": a.name, "username": a.username, "avatar_url": a.avatar_url}
            for a in getattr(info, 'approved_by', [])
        ]

        return cls(
            iid=info.iid,
            id=info.id,
            project_id=info.project_id,
            title=info.title,
            description=info.description,
            source_branch=info.source_branch,
            target_branch=info.target_branch,
            state=info.state.value,
            author_name=author_name,
            author_avatar=author_avatar,
            web_url=info.web_url or "",
            created_at=created_at_str,
            updated_at=updated_at_str,
            user_notes_count=info.user_notes_count,
            approved_by_current_user=getattr(info, 'approved_by_current_user', False),
            approved_by=approved_by_list,
            assignees=assignees_list,
            reviewers=reviewers_list,
            merge_status=getattr(info, 'merge_status', None),
            has_conflicts=getattr(info, 'has_conflicts', False),
            can_merge=getattr(info, 'can_merge', False),
        )


class DiffFileModel(BaseModel):
    """Diff 文件模型"""
    old_path: str
    new_path: str
    new_file: bool
    renamed_file: bool
    deleted_file: bool
    diff: str
    additions: int
    deletions: int

    @classmethod
    def from_file(cls, file: DiffFile) -> "DiffFileModel":
        return cls(
            old_path=file.old_path,
            new_path=file.new_path,
            new_file=file.new_file,
            renamed_file=file.renamed_file,
            deleted_file=file.deleted_file,
            diff=file.diff,
            additions=file.additions,
            deletions=file.deletions,
        )


class NoteModel(BaseModel):
    """评论模型"""
    id: int
    author_name: str
    author_avatar: str | None = None
    body: str
    created_at: str
    system: bool = False
    type: str = "note"  # note, discussion
    file_path: str | None = None
    line_number: int | None = None


class CommentRequest(BaseModel):
    """评论请求"""
    body: str
    file_path: str | None = None
    line_number: int | None = None
    line_type: str = "new"  # new, old


class AcceptMergeRequestRequest(BaseModel):
    """合并 MR 请求"""
    merge_commit_message: str | None = None
    should_remove_source_branch: bool = False
    merge_when_pipeline_succeeds: bool = False


# ==================== API 端点 ====================

@router.post("/connect", response_model=ConnectResponse)
async def connect_gitlab(
    request: ConnectRequest,
    user_id: int = Depends(get_current_user_id),
    db: DatabaseManager = Depends(get_db),
):
    """连接到 GitLab"""
    try:
        # 创建临时客户端验证连接
        temp_client = GitLabClient(
            url=request.url,
            token=request.token,
        )

        # 获取当前用户信息验证连接
        user = temp_client.get_current_user()

        # 保存配置到数据库
        db.upsert_gitlab_config(
            user_id=user_id,
            url=request.url,
            token=request.token,
        )
        logger.info(f"用户 {user_id} 的 GitLab 配置已保存")

        return ConnectResponse(
            status="ok",
            message="连接成功",
            user=user,
        )

    except GitLabAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except GitLabConnectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except GitLabException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"连接 GitLab 失败: {e}")
        raise HTTPException(status_code=500, detail=f"连接失败: {str(e)}")


@router.get("/projects")
async def list_projects(
    search: str | None = None,
    membership: bool = True,
    client: GitLabClient = Depends(get_gitlab_client),
):
    """列出项目"""
    try:
        projects = client.list_projects(
            membership=membership,
            search=search,
            per_page=100,
        )
        return [ProjectModel.from_info(p) for p in projects]

    except GitLabException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"列出项目失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    client: GitLabClient = Depends(get_gitlab_client),
):
    """获取项目详情"""
    try:
        project = client.get_project(project_id)
        return ProjectModel.from_info(project)

    except GitLabNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except GitLabException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"获取项目失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/merge-requests")
async def list_merge_requests(
    project_id: str,
    state: str = "opened",
    client: GitLabClient = Depends(get_gitlab_client),
):
    """列出项目的 Merge Requests"""
    try:
        mrs = client.list_merge_requests(
            project_id=project_id,
            state=state,
        )
        return [MRModel.from_info(m) for m in mrs]

    except GitLabNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except GitLabException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"列出 MR 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/merge-requests/related")
async def list_related_merge_requests(
    state: str = "opened",
    client: GitLabClient = Depends(get_gitlab_client),
):
    """列出与当前用户相关的所有 Merge Requests"""
    try:
        result = client.list_all_merge_requests_related_to_me(state=state)
        return [
            {
                "mr": MRModel.from_info(mr),
                "project": ProjectModel.from_info(project) if project else None,
            }
            for mr, project in result
        ]

    except GitLabException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"列出相关 MR 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/merge-requests/authored")
async def list_authored_merge_requests(
    state: str = "opened",
    client: GitLabClient = Depends(get_gitlab_client),
):
    """列出由当前用户创建的所有 Merge Requests"""
    try:
        result = client.list_all_merge_requests_authored_by_me(state=state)
        return [
            {
                "mr": MRModel.from_info(mr),
                "project": ProjectModel.from_info(project) if project else None,
            }
            for mr, project in result
        ]

    except GitLabException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"列出用户创建的 MR 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/merge-requests/{mr_iid}")
async def get_merge_request(
    project_id: str,
    mr_iid: int,
    include_diff: bool = False,
    client: GitLabClient = Depends(get_gitlab_client),
):
    """获取 Merge Request 详情"""
    try:
        mr = client.get_merge_request(
            project_id=project_id,
            mr_iid=mr_iid,
            include_diff=include_diff,
        )
        return MRModel.from_info(mr)

    except GitLabNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except GitLabException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"获取 MR 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/merge-requests/{mr_iid}/diffs")
async def get_merge_request_diffs(
    project_id: str,
    mr_iid: int,
    client: GitLabClient = Depends(get_gitlab_client),
):
    """获取 Merge Request 的 Diff 文件列表"""
    try:
        diffs = client.get_merge_request_diffs(
            project_id=project_id,
            mr_iid=mr_iid,
        )
        return [DiffFileModel.from_file(d) for d in diffs]

    except GitLabNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except GitLabException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"获取 MR Diff 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/merge-requests/{mr_iid}/notes")
async def get_merge_request_notes(
    project_id: str,
    mr_iid: int,
    client: GitLabClient = Depends(get_gitlab_client),
):
    """获取 Merge Request 的评论列表"""
    try:
        notes = client.get_merge_request_notes(
            project_id=project_id,
            mr_iid=mr_iid,
        )
        # 转换为统一格式，包含位置信息
        result = []
        for note in notes:
            # 从 position 字段提取文件路径和行号
            position = note.get("position", {})
            file_path = None
            line_number = None

            if position:
                # 优先使用 new_path，如果没有则使用 old_path
                file_path = position.get("new_path") or position.get("old_path")
                # 优先使用 new_line，如果没有则使用 old_line
                line_number = position.get("new_line") or position.get("old_line")

            result.append({
                "id": note.get("id"),
                "author_name": note.get("author", {}).get("name"),
                "author_avatar": note.get("author", {}).get("avatar_url"),
                "body": note.get("body"),
                "created_at": note.get("created_at"),
                "system": note.get("system", False),
                "type": "note",
                "file_path": file_path,
                "line_number": line_number,
            })
        return result

    except GitLabException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"获取 MR 评论失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/merge-requests/{mr_iid}/notes")
async def create_merge_request_note(
    project_id: str,
    mr_iid: int,
    request: CommentRequest,
    client: GitLabClient = Depends(get_gitlab_client),
):
    """创建 Merge Request 评论"""
    try:
        # 如果指定了文件和行号，创建行评论
        if request.file_path and request.line_number:
            success = client.create_merge_request_discussion(
                project_id=project_id,
                mr_iid=mr_iid,
                body=request.body,
                file_path=request.file_path,
                line_number=request.line_number,
                line_type=request.line_type,
            )
        else:
            # 创建普通评论
            success = client.create_merge_request_note(
                project_id=project_id,
                mr_iid=mr_iid,
                body=request.body,
            )

        if success:
            return {"status": "ok", "message": "评论已发布"}
        else:
            raise HTTPException(status_code=500, detail="发布评论失败")

    except GitLabException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"创建 MR 评论失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/merge-requests/{mr_iid}/notes/{note_id}")
async def delete_merge_request_note(
    project_id: str,
    mr_iid: int,
    note_id: int,
    client: GitLabClient = Depends(get_gitlab_client),
):
    """删除 Merge Request 评论"""
    try:
        success = client.delete_merge_request_note(
            project_id=project_id,
            mr_iid=mr_iid,
            note_id=note_id,
        )

        if success:
            return {"status": "ok", "message": "评论已删除"}
        else:
            raise HTTPException(status_code=500, detail="删除评论失败")

    except GitLabException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"删除 MR 评论失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/merge-requests/{mr_iid}/approve")
async def approve_merge_request(
    project_id: str,
    mr_iid: int,
    client: GitLabClient = Depends(get_gitlab_client),
):
    """批准 Merge Request"""
    try:
        success = client.approve_merge_request(
            project_id=project_id,
            mr_iid=mr_iid,
        )

        if success:
            return {"status": "ok", "message": "已批准"}
        else:
            raise HTTPException(status_code=500, detail="批准失败")

    except GitLabException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"批准 MR 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/merge-requests/{mr_iid}/unapprove")
async def unapprove_merge_request(
    project_id: str,
    mr_iid: int,
    client: GitLabClient = Depends(get_gitlab_client),
):
    """取消批准 Merge Request"""
    try:
        success = client.unapprove_merge_request(
            project_id=project_id,
            mr_iid=mr_iid,
        )

        if success:
            return {"status": "ok", "message": "已取消批准"}
        else:
            raise HTTPException(status_code=500, detail="取消批准失败")

    except GitLabException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"取消批准 MR 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/merge-requests/{mr_iid}/approval-state")
async def get_merge_request_approval_state(
    project_id: str,
    mr_iid: int,
    client: GitLabClient = Depends(get_gitlab_client),
):
    """获取 Merge Request 的批准状态"""
    try:
        approval_state = client.get_merge_request_approval_state(
            project_id=project_id,
            mr_iid=mr_iid,
        )
        return approval_state

    except GitLabException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"获取 MR 批准状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projects/{project_id}/merge-requests/{mr_iid}/merge")
async def accept_merge_request(
    project_id: str,
    mr_iid: int,
    request: AcceptMergeRequestRequest | None = None,
    client: GitLabClient = Depends(get_gitlab_client),
):
    """合并（接受）Merge Request"""
    try:
        # 如果没有提供请求体，使用默认值
        merge_commit_message = request.merge_commit_message if request else None
        should_remove_source_branch = request.should_remove_source_branch if request else False

        success = client.accept_merge_request(
            project_id=project_id,
            mr_iid=mr_iid,
            merge_commit_message=merge_commit_message,
            should_remove_source_branch=should_remove_source_branch,
        )

        if success:
            return {"status": "ok", "message": "合并成功"}
        else:
            raise HTTPException(status_code=500, detail="合并失败")

    except GitLabException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"合并 MR 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ReplyRequest(BaseModel):
    """回复请求"""
    body: str


@router.get("/projects/{project_id}/merge-requests/{mr_iid}/discussions")
async def get_merge_request_discussions(
    project_id: str,
    mr_iid: int,
    client: GitLabClient = Depends(get_gitlab_client),
):
    """获取 Merge Request 的讨论列表（包含回复）"""
    try:
        discussions = client.get_merge_request_discussions(
            project_id=project_id,
            mr_iid=mr_iid,
        )
        return discussions

    except GitLabException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"获取 MR 讨论失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/merge-requests/{mr_iid}/discussions/{discussion_id}/notes")
async def add_discussion_note(
    project_id: str,
    mr_iid: int,
    discussion_id: str,
    request: ReplyRequest,
    client: GitLabClient = Depends(get_gitlab_client),
):
    """在讨论中添加回复"""
    try:
        success = client.add_discussion_note(
            project_id=project_id,
            mr_iid=mr_iid,
            discussion_id=discussion_id,
            body=request.body,
        )

        if success:
            return {"status": "ok", "message": "回复已发布"}
        else:
            raise HTTPException(status_code=500, detail="发布回复失败")

    except GitLabException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"添加回复失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class UserModel(BaseModel):
    """用户模型"""
    id: int
    name: str
    username: str
    avatar_url: str | None = None


@router.get("/users")
async def list_users(
    search: str | None = None,
    client: GitLabClient = Depends(get_gitlab_client),
):
    """列出用户"""
    try:
        users = client.list_users(
            search=search,
            per_page=100,
        )
        return [
            UserModel(
                id=user.get("id"),
                name=user.get("name"),
                username=user.get("username"),
                avatar_url=user.get("avatar_url"),
            )
            for user in users
        ]

    except GitLabException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"列出用户失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
