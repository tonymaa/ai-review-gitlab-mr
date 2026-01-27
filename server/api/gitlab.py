"""GitLab API 路由

提供 GitLab 相关的 REST API 接口
"""

import logging
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.gitlab.client import GitLabClient
from src.gitlab.models import MergeRequestInfo, DiffFile, ProjectInfo
from src.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# 全局 GitLab 客户端 (实际应该使用 SessionManager 管理)
_gitlab_client: Optional[GitLabClient] = None


def get_gitlab_client() -> Optional[GitLabClient]:
    """获取 GitLab 客户端实例，如果不存在则从配置创建"""
    global _gitlab_client

    # 如果客户端不存在但配置中有 GitLab URL 和 token，则自动重新创建
    if _gitlab_client is None and settings.gitlab.url and settings.gitlab.token:
        try:
            logger.info("自动重新创建 GitLab 客户端")
            _gitlab_client = GitLabClient(
                url=settings.gitlab.url,
                token=settings.gitlab.token,
            )
        except Exception as e:
            logger.error(f"自动创建 GitLab 客户端失败: {e}")

    return _gitlab_client


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
    approved_by_current_user: bool = False
    assignees: list[dict] = []
    reviewers: list[dict] = []

    @classmethod
    def from_info(cls, info: MergeRequestInfo) -> "MRModel":
        # 处理时间字段转换为字符串
        created_at_str = info.created_at.isoformat() if info.created_at else ""
        updated_at_str = info.updated_at.isoformat() if info.updated_at else ""

        # 处理作者信息
        author_name = info.author.name if info.author else "Unknown"
        author_avatar = info.author.avatar_url if info.author else None

        # 处理 assignees 和 reviewers
        assignees_list = [
            {"id": a.id, "name": a.name, "avatar_url": a.avatar_url}
            for a in info.assignees
        ]
        reviewers_list = [
            {"id": r.id, "name": r.name, "avatar_url": r.avatar_url}
            for r in info.reviewers
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
            approved_by_current_user=getattr(info, 'approved_by_current_user', False),
            assignees=assignees_list,
            reviewers=reviewers_list,
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


# ==================== API 端点 ====================

@router.post("/connect", response_model=ConnectResponse)
async def connect_gitlab(request: ConnectRequest):
    """连接到 GitLab"""
    global _gitlab_client

    try:
        # 创建客户端
        _gitlab_client = GitLabClient(
            url=request.url,
            token=request.token,
        )

        # 获取当前用户信息
        user = _gitlab_client.get_current_user()

        # 更新配置
        settings.gitlab.url = request.url
        settings.gitlab.token = request.token

        return ConnectResponse(
            status="ok",
            message="连接成功",
            user=user,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
    if not client:
        raise HTTPException(status_code=401, detail="未连接到 GitLab")

    try:
        projects = client.list_projects(
            membership=membership,
            search=search,
            per_page=100,
        )
        return [ProjectModel.from_info(p) for p in projects]

    except Exception as e:
        logger.error(f"列出项目失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    client: GitLabClient = Depends(get_gitlab_client),
):
    """获取项目详情"""
    if not client:
        raise HTTPException(status_code=401, detail="未连接到 GitLab")

    try:
        project = client.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        return ProjectModel.from_info(project)

    except HTTPException:
        raise
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
    if not client:
        raise HTTPException(status_code=401, detail="未连接到 GitLab")

    try:
        mrs = client.list_merge_requests(
            project_id=project_id,
            state=state,
        )
        return [MRModel.from_info(m) for m in mrs]

    except Exception as e:
        logger.error(f"列出 MR 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/merge-requests/related")
async def list_related_merge_requests(
    state: str = "opened",
    client: GitLabClient = Depends(get_gitlab_client),
):
    """列出与当前用户相关的所有 Merge Requests"""
    if not client:
        raise HTTPException(status_code=401, detail="未连接到 GitLab")

    try:
        result = client.list_all_merge_requests_related_to_me(state=state)
        return [
            {
                "mr": MRModel.from_info(mr),
                "project": ProjectModel.from_info(project) if project else None,
            }
            for mr, project in result
        ]

    except Exception as e:
        logger.error(f"列出相关 MR 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/merge-requests/{mr_iid}")
async def get_merge_request(
    project_id: str,
    mr_iid: int,
    include_diff: bool = False,
    client: GitLabClient = Depends(get_gitlab_client),
):
    """获取 Merge Request 详情"""
    if not client:
        raise HTTPException(status_code=401, detail="未连接到 GitLab")

    try:
        mr = client.get_merge_request(
            project_id=project_id,
            mr_iid=mr_iid,
            include_diff=include_diff,
        )
        if not mr:
            raise HTTPException(status_code=404, detail="MR 不存在")
        return MRModel.from_info(mr)

    except HTTPException:
        raise
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
    if not client:
        raise HTTPException(status_code=401, detail="未连接到 GitLab")

    try:
        diffs = client.get_merge_request_diffs(
            project_id=project_id,
            mr_iid=mr_iid,
        )
        return [DiffFileModel.from_file(d) for d in diffs]

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
    if not client:
        raise HTTPException(status_code=401, detail="未连接到 GitLab")

    try:
        notes = client.get_merge_request_notes(
            project_id=project_id,
            mr_iid=mr_iid,
        )
        # 转换为统一格式
        result = []
        for note in notes:
            result.append({
                "id": note.get("id"),
                "author_name": note.get("author", {}).get("name"),
                "author_avatar": note.get("author", {}).get("avatar_url"),
                "body": note.get("body"),
                "created_at": note.get("created_at"),
                "system": note.get("system", False),
                "type": "note",
            })
        return result

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
    if not client:
        raise HTTPException(status_code=401, detail="未连接到 GitLab")

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

    except HTTPException:
        raise
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
    if not client:
        raise HTTPException(status_code=401, detail="未连接到 GitLab")

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

    except HTTPException:
        raise
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
    if not client:
        raise HTTPException(status_code=401, detail="未连接到 GitLab")

    try:
        success = client.approve_merge_request(
            project_id=project_id,
            mr_iid=mr_iid,
        )

        if success:
            return {"status": "ok", "message": "已批准"}
        else:
            raise HTTPException(status_code=500, detail="批准失败")

    except HTTPException:
        raise
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
    if not client:
        raise HTTPException(status_code=401, detail="未连接到 GitLab")

    try:
        success = client.unapprove_merge_request(
            project_id=project_id,
            mr_iid=mr_iid,
        )

        if success:
            return {"status": "ok", "message": "已取消批准"}
        else:
            raise HTTPException(status_code=500, detail="取消批准失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消批准 MR 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
