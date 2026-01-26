"""GitLab客户端封装 - 提供GitLab API调用的简化接口"""

import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

import gitlab
from gitlab.exceptions import GitlabError, GitlabAuthenticationError, GitlabGetError

from .models import (
    MergeRequestInfo,
    DiffFile,
    ProjectInfo,
    MRState,
)
from ..core.database import DatabaseManager

logger = logging.getLogger(__name__)


class GitLabClient:
    """GitLab API客户端封装"""

    def __init__(self, url: str, token: str, db_manager: Optional[DatabaseManager] = None):
        """
        初始化GitLab客户端

        Args:
            url: GitLab服务器地址
            token: 个人访问令牌
            db_manager: 数据库管理器（可选，用于缓存）
        """
        self.url = url
        self.token = token
        self.db_manager = db_manager

        # 创建GitLab客户端
        try:
            self._client = gitlab.Gitlab(url, private_token=token)
            # 验证连接
            self._client.auth()
            logger.info(f"成功连接到GitLab: {url}")
        except GitlabAuthenticationError:
            raise ValueError("GitLab认证失败，请检查Token是否正确")
        except GitlabError as e:
            raise ValueError(f"连接GitLab失败: {e}")

    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """获取当前用户信息"""
        try:
            return self._client.user.__dict__['_attrs']
        except GitlabError as e:
            logger.error(f"获取当前用户信息失败: {e}")
            return None

    def get_project(self, project_id: str | int) -> Optional[ProjectInfo]:
        """
        获取项目信息

        Args:
            project_id: 项目ID或路径 (如: "group/project")

        Returns:
            ProjectInfo对象或None
        """
        try:
            project = self._client.projects.get(project_id)
            return ProjectInfo.from_dict(project.asdict())
        except GitlabGetError:
            logger.error(f"项目不存在: {project_id}")
            return None
        except GitlabError as e:
            logger.error(f"获取项目信息失败: {e}")
            return None

    def list_projects(
        self,
        membership: bool = True,
        search: Optional[str] = None,
        per_page: int = 50,
    ) -> List[ProjectInfo]:
        """
        列出项目

        Args:
            membership: 是否只列出成员项目
            search: 搜索关键词
            per_page: 每页数量

        Returns:
            项目列表
        """
        try:
            projects = self._client.projects.list(
                membership=membership,
                search=search,
                per_page=per_page,
                order_by="last_activity_at",
                sort="desc",
                get_all=True,
            )
            return [ProjectInfo.from_dict(p.asdict()) for p in projects]
        except GitlabError as e:
            logger.error(f"列出项目失败: {e}")
            return []

    def list_merge_requests(
        self,
        project_id: str | int,
        state: str = "opened",
        order_by: str = "updated_at",
        sort: str = "desc",
        per_page: int = 100,
    ) -> List[MergeRequestInfo]:
        """
        列出项目的Merge Requests

        Args:
            project_id: 项目ID或路径
            state: MR状态 (opened, closed, merged, all)
            order_by: 排序字段
            sort: 排序方向
            per_page: 每页数量

        Returns:
            MergeRequestInfo列表
        """
        try:
            project = self._client.projects.get(project_id)
            mrs = project.mergerequests.list(
                state=state,
                order_by=order_by,
                sort=sort,
                per_page=per_page,
                get_all=False,  # 明确指定分页行为
            )

            mr_list = []
            for mr in mrs:
                mr_info = MergeRequestInfo.from_dict(mr.asdict())

                # 缓存到数据库
                if self.db_manager:
                    self.db_manager.save_merge_request(mr_info.to_database_dict())

                mr_list.append(mr_info)

            return mr_list

        except GitlabGetError:
            logger.error(f"项目不存在: {project_id}")
            return []
        except GitlabError as e:
            logger.error(f"列出MR失败: {e}")
            return []

    def list_all_merge_requests_related_to_me(
        self,
        state: str = "opened",
    ) -> List[tuple[MergeRequestInfo, ProjectInfo]]:
        """
        列出所有项目中与当前用户相关的Merge Requests（我是reviewer或assignee）

        Args:
            state: MR状态 (opened, closed, merged, all)
            order_by: 排序字段
            sort: 排序方向
            per_page: 每页数量

        Returns:
            (MergeRequestInfo, ProjectInfo) 元组列表
        """
        try:
            # 获取当前用户信息
            current_user = self.get_current_user()
            if not current_user:
                logger.error("无法获取当前用户信息")
                return []

            current_user_id = current_user.get("id")

            # 1. 获取 assignee 为我的 MR (使用全局 API，包含 approval 状态)
            assigned_mrs = self._client.mergerequests.list(
                scope="assigned_to_me",
                state=state,
                all=True,
                with_approval_status=True,  # 包含 approval 状态
            )

            # 合并结果（使用字典去重，key 为 (project_id, mr_iid)）
            mr_dict = {}

            for mr in assigned_mrs:
                key = (mr.project_id, mr.iid)
                if key not in mr_dict:
                    mr_dict[key] = mr

            reviewer_mrs = self._client.mergerequests.list(
                scope="all",
                reviewer_id=current_user_id,
                state=state,
                all=True,
                with_approval_status=True,  # 包含 approval 状态
            )

            for mr in reviewer_mrs:
                key = (mr.project_id, mr.iid)
                if key not in mr_dict:
                    mr_dict[key] = mr

            result = []

            import time
            total_count = len(mr_dict)

            # 项目缓存，避免重复获取同一个项目
            project_cache = {}

            for idx, mr in enumerate(mr_dict.values(), 1):
                loop_start = time.time()

                # 步骤1: 创建MR对象
                step1_start = time.time()
                try:
                    mr_info = MergeRequestInfo.from_dict(mr.asdict())
                except (GitlabError, Exception) as e:
                    logger.warning(f"创建MR对象失败 [{idx}/{total_count}] !{mr.iid}: {e}")
                    continue
                step1_time = time.time() - step1_start

                # 步骤2: 获取项目信息（使用缓存）
                step2_start = time.time()
                if mr.project_id not in project_cache:
                    try:
                        project = self._client.projects.get(mr.project_id)
                        project_cache[mr.project_id] = project
                    except GitlabError:
                        project_cache[mr.project_id] = None

                project = project_cache.get(mr.project_id)
                project_info = ProjectInfo.from_dict(project.asdict()) if project else None
                step2_time = time.time() - step2_start

                # 步骤3: 从 MR 对象中提取 approval 状态（已在列表API中获取）
                step3_start = time.time()
                try:
                    if mr.detailed_merge_status == 'approvals_missing' and project:
                        mr_obj = project.mergerequests.get(mr.iid)
                        approval = mr_obj.approvals.get()
                        approved_by = approval.approved_by if hasattr(approval, 'approved_by') else []
                        for approver in approved_by:
                            user_dict = approver.asdict() if hasattr(approver, 'asdict') else approver
                            if user_dict.get('user', {}).get('id') == current_user_id:
                                mr_info.approved_by_current_user = True
                                break
                except Exception as e:
                    logger.debug(f"解析MR {mr.iid} 的approval状态失败: {e}")
                step3_time = time.time() - step3_start

                result.append((mr_info, project_info))

                # 缓存到数据库
                if self.db_manager:
                    step4_start = time.time()
                    self.db_manager.save_merge_request(mr_info.to_database_dict())
                    step4_time = time.time() - step4_start
                else:
                    step4_time = 0

                loop_time = time.time() - loop_start
                logger.info(
                    f"处理MR [{idx}/{total_count}] !{mr.iid} 总耗时: {loop_time:.2f}秒 | "
                    f"创建对象: {step1_time:.3f}s, "
                    f"获取项目: {step2_time:.3f}s, "
                    f"获取审批: {step3_time:.3f}s, "
                    f"数据库: {step4_time:.3f}s"
                )
            return result

        except GitlabError as e:
            logger.error(f"列出所有项目相关MR失败: {e}")
            return []


    def get_merge_request(
        self,
        project_id: str | int,
        mr_iid: int,
        include_diff: bool = False,
    ) -> Optional[MergeRequestInfo]:
        """
        获取单个Merge Request详情

        Args:
            project_id: 项目ID或路径
            mr_iid: MR的IID
            include_diff: 是否包含Diff信息

        Returns:
            MergeRequestInfo对象或None
        """
        try:
            project = self._client.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid, include_diff=include_diff)
            mr_info = MergeRequestInfo.from_dict(mr.asdict())

            # 缓存到数据库
            if self.db_manager:
                db_mr = self.db_manager.save_merge_request(mr_info.to_database_dict())

                # 如果需要diff，获取并缓存diff文件
                if include_diff:
                    diff_files = self.get_merge_request_diffs(project_id, mr_iid)
                    for diff_file in diff_files:
                        self.db_manager.save_diff_file(db_mr.id, diff_file.to_database_dict())

            return mr_info

        except GitlabGetError:
            logger.error(f"MR不存在: {project_id}!{mr_iid}")
            return None
        except GitlabError as e:
            logger.error(f"获取MR详情失败: {e}")
            return None

    def get_merge_request_diffs(
        self,
        project_id: str | int,
        mr_iid: int,
    ) -> List[DiffFile]:
        """
        获取MR的Diff文件列表

        Args:
            project_id: 项目ID或路径
            mr_iid: MR的IID

        Returns:
            DiffFile列表
        """
        try:
            project = self._client.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)

            # 使用changes()方法获取完整的变更信息
            changes = mr.changes()
            diff_files = []
            for change in changes.get("changes", []):
                # change包含: old_path, new_path, diff, new_file, renamed_file, deleted_file
                diff_file = DiffFile(
                    old_path=change.get("old_path", ""),
                    new_path=change.get("new_path", ""),
                    new_file=change.get("new_file", False),
                    renamed_file=change.get("renamed_file", False),
                    deleted_file=change.get("deleted_file", False),
                    diff=change.get("diff", ""),
                )

                # 计算增删行数
                diff_text = change.get("diff", "")
                additions = diff_text.count("\n+") - diff_text.count("\n+++")
                deletions = diff_text.count("\n-") - diff_text.count("\n---")
                diff_file.additions = max(0, additions)
                diff_file.deletions = max(0, deletions)

                diff_files.append(diff_file)

            return diff_files

        except GitlabGetError:
            logger.error(f"MR不存在: {project_id}!{mr_iid}")
            return []
        except GitlabError as e:
            logger.error(f"获取MR Diff失败: {e}")
            return []

    def get_merge_request_changes(
        self,
        project_id: str | int,
        mr_iid: int,
    ) -> Optional[Dict[str, Any]]:
        """
        获取MR的变更信息

        Args:
            project_id: 项目ID或路径
            mr_iid: MR的IID

        Returns:
            变更信息字典
        """
        try:
            project = self._client.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            changes = mr.changes()

            return {
                "id": changes["id"],
                "iid": changes["iid"],
                "changes": changes.get("changes", []),
                "diff_refs": changes.get("diff_refs", {}),
            }

        except GitlabGetError:
            logger.error(f"MR不存在: {project_id}!{mr_iid}")
            return None
        except GitlabError as e:
            logger.error(f"获取MR变更失败: {e}")
            return None

    def get_file_content(
        self,
        project_id: str | int,
        file_path: str,
        ref: str = "main",
    ) -> Optional[str]:
        """
        获取文件内容

        Args:
            project_id: 项目ID或路径
            file_path: 文件路径
            ref: 分支或提交引用

        Returns:
            文件内容或None
        """
        try:
            project = self._client.projects.get(project_id)
            file = project.files.get(file_path=file_path, ref=ref)
            return file.decode()
        except GitlabGetError:
            logger.error(f"文件不存在: {file_path} @ {ref}")
            return None
        except GitlabError as e:
            logger.error(f"获取文件内容失败: {e}")
            return None

    def create_merge_request_note(
        self,
        project_id: str | int,
        mr_iid: int,
        body: str,
    ) -> bool:
        """
        创建MR评论

        Args:
            project_id: 项目ID或路径
            mr_iid: MR的IID
            body: 评论内容

        Returns:
            是否成功
        """
        try:
            project = self._client.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            mr.notes.create({"body": body})
            logger.info(f"成功为MR {mr_iid}添加评论")
            return True
        except GitlabError as e:
            logger.error(f"添加MR评论失败: {e}")
            return False

    def get_merge_request_notes(
        self,
        project_id: str | int,
        mr_iid: int,
    ) -> List[Dict[str, Any]]:
        """
        获取MR的评论列表

        Args:
            project_id: 项目ID或路径
            mr_iid: MR的IID

        Returns:
            评论列表
        """
        try:
            project = self._client.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            notes = mr.notes.list(all=True)

            # 转换为字典列表
            result = []
            for note in notes:
                result.append(note.asdict())

            return result

        except GitlabError as e:
            logger.error(f"获取MR评论失败: {e}")
            return []

    def delete_merge_request_note(
        self,
        project_id: str | int,
        mr_iid: int,
        note_id: int,
    ) -> bool:
        """
        删除MR评论

        Args:
            project_id: 项目ID或路径
            mr_iid: MR的IID
            note_id: 评论ID

        Returns:
            是否成功
        """
        try:
            project = self._client.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            note = mr.notes.get(note_id)
            note.delete()
            logger.info(f"成功删除MR评论 {note_id}")
            return True

        except GitlabError as e:
            logger.error(f"删除MR评论失败: {e}")
            return False

    def create_merge_request_discussion(
        self,
        project_id: str | int,
        mr_iid: int,
        body: str,
        file_path: str,
        line_number: int,
        line_type: str = "new",
    ) -> bool:
        """
        创建MR行评论

        Args:
            project_id: 项目ID或路径
            mr_iid: MR的IID
            body: 评论内容
            file_path: 文件路径
            line_number: 行号
            line_type: 行类型 (old/new)

        Returns:
            是否成功
        """
        try:
            project = self._client.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)

            # 获取MR的diff_refs（包含所需的SHA值）
            changes = mr.changes()
            diff_refs = changes.get("diff_refs", {})

            # 构造line_code (格式: "{sha}_{line_type}_{line_number}")
            # 使用head_sha作为line_code的前缀
            head_sha = diff_refs.get("head_sha", "")
            line_code = f"{head_sha}_{line_type}_{line_number}"

            # 构造位置参数
            position = {
                "base_sha": diff_refs.get("base_sha"),
                "start_sha": diff_refs.get("start_sha"),
                "head_sha": diff_refs.get("head_sha"),
                "position_type": "text",
                "new_path": file_path,
                "old_path": file_path,
                "line_code": line_code,
            }

            if line_type == "new":
                position["new_line"] = line_number
            else:
                position["old_line"] = line_number

            try:
                mr.discussions.create({"body": body, "position": position})
                logger.info(f"成功为MR {mr_iid}的文件 {file_path}:{line_number} 添加行评论")
                return True
            except GitlabError as e:
                # 如果行评论失败（可能是行号不存在），改为普通MR评论
                error_msg = str(e)
                if "line_code" in error_msg or "can't be blank" in error_msg:
                    # 添加文件位置信息到评论内容，改为普通评论
                    file_note_body = f"**{file_path}:{line_number}**\n\n{body}"
                    mr.notes.create({"body": file_note_body})
                    logger.info(f"行号不存在，已为MR {mr_iid}的文件 {file_path}:{line_number} 添加普通评论")
                    return True
                else:
                    raise

        except GitlabError as e:
            logger.error(f"添加MR行评论失败: {e}")
            return False

    def accept_merge_request(
        self,
        project_id: str | int,
        mr_iid: int,
        merge_commit_message: Optional[str] = None,
        should_remove_source_branch: bool = False,
    ) -> bool:
        """
        接受（合并）Merge Request

        Args:
            project_id: 项目ID或路径
            mr_iid: MR的IID
            merge_commit_message: 合并提交消息
            should_remove_source_branch: 是否删除源分支

        Returns:
            是否成功
        """
        try:
            project = self._client.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)

            merge_params = {}
            if merge_commit_message:
                merge_params["merge_commit_message"] = merge_commit_message
            if should_remove_source_branch:
                merge_params["should_remove_source_branch"] = True

            mr.merge(merge_params)
            logger.info(f"成功合并MR {mr_iid}")
            return True

        except GitlabError as e:
            logger.error(f"合并MR失败: {e}")
            return False

    def approve_merge_request(
        self,
        project_id: str | int,
        mr_iid: int,
    ) -> bool:
        """
        批准Merge Request

        Args:
            project_id: 项目ID或路径
            mr_iid: MR的IID

        Returns:
            是否成功
        """
        try:
            project = self._client.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            mr.approve()
            logger.info(f"成功批准MR {mr_iid}")
            return True

        except GitlabError as e:
            logger.error(f"批准MR失败: {e}")
            return False

    def unapprove_merge_request(
        self,
        project_id: str | int,
        mr_iid: int,
    ) -> bool:
        """
        取消批准Merge Request

        Args:
            project_id: 项目ID或路径
            mr_iid: MR的IID

        Returns:
            是否成功
        """
        try:
            project = self._client.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            mr.unapprove()
            logger.info(f"成功取消批准MR {mr_iid}")
            return True

        except GitlabError as e:
            logger.error(f"取消批准MR失败: {e}")
            return False


def parse_project_identifier(identifier: str) -> tuple[str, str | int]:
    """
    解析项目标识符

    支持以下格式:
    - 123 (纯数字ID)
    - group/project (路径)
    - https://gitlab.com/group/project (URL)

    Args:
        identifier: 项目标识符

    Returns:
        (host, project_id_or_path) 元组
    """
    # 检查是否是URL
    if identifier.startswith("http://") or identifier.startswith("https://"):
        from urllib.parse import urlparse

        parsed = urlparse(identifier)
        host = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path.strip("/")
        return host, path

    # 如果是纯数字，作为ID处理
    if identifier.isdigit():
        return "", int(identifier)

    # 否则作为路径处理
    return "", identifier
