"""自动审查任务调度器

负责管理和执行用户的自动审查任务
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from src.core.database import DatabaseManager
from src.core.exceptions import AIAuthError, AIQuotaError
from src.gitlab.client import GitLabClient
from src.ai.reviewer import create_reviewer
from server.api.auto_review import update_user_task_status

logger = logging.getLogger(__name__)


def now_utc() -> datetime:
    """获取当前UTC时间"""
    return datetime.now(timezone.utc)


def now_utc_str() -> str:
    """获取当前UTC时间字符串"""
    return now_utc().isoformat()


class AutoReviewScheduler:
    """自动审查调度器"""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._tasks: Dict[int, asyncio.Task] = {}  # user_id -> task
        self._stop_events: Dict[int, asyncio.Event] = {}  # user_id -> stop event
        self._single_run_events: Dict[int, asyncio.Event] = {}  # user_id -> single run event
        self._processing_locks: Dict[int, asyncio.Lock] = {}  # user_id -> processing lock (防止并发执行)
        self._lock = asyncio.Lock()  # 保护 _processing_locks 访问的锁

    async def start_user_task(self, user_id: int):
        """启动用户的自动审查任务"""
        if user_id in self._tasks and not self._tasks[user_id].done():
            logger.warning(f"用户 {user_id} 的自动审查任务已在运行")
            return

        # 创建停止事件
        self._stop_events[user_id] = asyncio.Event()

        # 启动任务
        self._tasks[user_id] = asyncio.create_task(
            self._run_user_auto_review(user_id)
        )
        logger.info(f"已启动用户 {user_id} 的自动审查任务")

        # 更新状态
        update_user_task_status(user_id, is_running=True)

    async def stop_user_task(self, user_id: int):
        """停止用户的自动审查任务"""
        if user_id in self._stop_events:
            self._stop_events[user_id].set()
            logger.info(f"已发送停止信号给用户 {user_id} 的自动审查任务")

            # 等待任务停止
            if user_id in self._tasks:
                try:
                    await asyncio.wait_for(self._tasks[user_id], timeout=5)
                except asyncio.TimeoutError:
                    logger.warning(f"用户 {user_id} 的任务停止超时")
                except Exception:
                    pass

            # 清理
            self._stop_events.pop(user_id, None)
            self._tasks.pop(user_id, None)

            # 更新状态
            update_user_task_status(user_id, is_running=False)

    def _get_processing_lock(self, user_id: int) -> asyncio.Lock:
        """获取用户的处理锁（防止并发执行）"""
        if user_id not in self._processing_locks:
            self._processing_locks[user_id] = asyncio.Lock()
        return self._processing_locks[user_id]

    async def restart_user_task(self, user_id: int, interval_seconds: int):
        """重启用户的自动审查任务（配置更新时）"""
        # 先标记为正在重启（防止其他操作干扰）
        old_task = self._tasks.get(user_id)
        old_stop_event = self._stop_events.get(user_id)

        # 停止旧任务
        if old_stop_event:
            old_stop_event.set()

        # 等待旧任务停止
        if old_task:
            try:
                await asyncio.wait_for(old_task, timeout=5)
            except asyncio.TimeoutError:
                logger.warning(f"用户 {user_id} 的旧任务停止超时")
            except Exception:
                pass

        # 清理旧状态
        self._stop_events.pop(user_id, None)
        self._tasks.pop(user_id, None)

        # 创建新的停止事件
        self._stop_events[user_id] = asyncio.Event()

        # 启动新任务
        self._tasks[user_id] = asyncio.create_task(
            self._run_user_auto_review(user_id)
        )
        logger.info(f"已重启用户 {user_id} 的自动审查任务")

    async def trigger_single_run(self, user_id: int):
        """触发单次运行（不启动定时任务）"""
        # 创建单次运行事件
        self._single_run_events[user_id] = asyncio.Event()

        # 获取配置并处理
        config = self.db.get_auto_review_config(user_id)
        if config and config["enabled"]:
            await self._process_auto_review(user_id, config)

        # 清理
        self._single_run_events.pop(user_id, None)

    async def stop_all(self):
        """停止所有任务"""
        for user_id in list(self._stop_events.keys()):
            await self.stop_user_task(user_id)

    async def _run_user_auto_review(self, user_id: int):
        """执行用户的自动审查循环"""
        stop_event = self._stop_events.get(user_id)
        single_run_event = self._single_run_events.get(user_id)
        if not stop_event:
            return

        logger.info(f"用户 {user_id} 的自动审查任务开始运行")

        while not stop_event.is_set():
            try:
                # 获取用户配置
                config = self.db.get_auto_review_config(user_id)

                if not config or not config["enabled"]:
                    logger.debug(f"用户 {user_id} 的自动审查未启用，停止任务")
                    break

                interval = config["interval_seconds"]

                # 记录开始运行时间
                run_start_time = now_utc_str()
                update_user_task_status(user_id, last_run_at=run_start_time)

                # 执行一次审查
                await self._process_auto_review(user_id, config)

                # 计算下次运行时间
                next_run_time = now_utc()
                next_run_time = next_run_time.replace(second=0, microsecond=0)
                next_run_time = next_run_time.replace(
                    second=(interval % 60),
                    minute=(next_run_time.minute + interval // 60) % 60,
                )
                update_user_task_status(user_id, next_run_at=next_run_time.isoformat())

                # 等待下一次运行或停止信号
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=interval)
                    break  # 收到停止信号
                except asyncio.TimeoutError:
                    continue  # 超时，继续下一次循环

            except Exception as e:
                logger.error(f"用户 {user_id} 自动审查任务出错: {e}", exc_info=True)
                # 出错后等待一段时间再重试
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=60)
                except asyncio.TimeoutError:
                    continue

        logger.info(f"用户 {user_id} 的自动审查任务已停止")
        update_user_task_status(user_id, is_running=False, next_run_at=None)

    async def _process_auto_review(self, user_id: int, config: Dict[str, Any]):
        """处理一次自动审查"""
        # 获取处理锁，防止同一用户的多次审查同时执行
        lock = self._get_processing_lock(user_id)

        if lock.locked():
            logger.info(f"用户 {user_id} 的自动审查正在执行中，跳过本次")
            return

        async with lock:
            logger.info(f"开始处理用户 {user_id} 的自动审查")

        # 获取用户的 GitLab 配置
        gitlab_config = self.db.get_gitlab_config(user_id)
        if not gitlab_config:
            logger.warning(f"用户 {user_id} 未配置 GitLab")
            return

        # 获取用户的 AI 配置
        ai_config = self.db.get_ai_config(user_id)
        if not ai_config:
            logger.warning(f"用户 {user_id} 未配置 AI")
            return

        client = GitLabClient(
            url=gitlab_config["url"],
            token=gitlab_config["token"],
        )

        # 解析目标项目列表
        target_projects = config.get("target_projects") or []
        target_creators = config.get("target_creators") or []

        try:
            # 获取相关的 MR
            merge_requests = client.list_all_merge_requests_related_to_me(
                state="opened"
            )
        except Exception as e:
            logger.error(f"获取用户 {user_id} 的 MR 列表失败: {e}")
            return

        # 筛选 MR
        filtered_mrs = []
        for mr_info, project_info in merge_requests:
            mr_iid = getattr(mr_info, "iid", None)
            mr_project_id = getattr(mr_info, "project_id", None)
            mr_title = getattr(mr_info, "title", "")
            mr_author = getattr(mr_info, "author", "")

            # 获取作者名称
            if hasattr(mr_author, "name"):
                # GitLabUser 对象
                author_name = mr_author.name
            elif isinstance(mr_author, dict):
                author_name = mr_author.get("name", "")
            else:
                author_name = str(mr_author)

            logger.debug(f"检查 MR: {mr_project_id}!{mr_iid} - {mr_title} (作者: {author_name})")

            # 检查项目筛选
            if target_projects:
                if str(mr_project_id) not in target_projects:
                    logger.debug(f"  → 跳过: 项目 {mr_project_id} 不在目标项目列表中")
                    continue

            # 检查创建者筛选
            if target_creators:
                if author_name not in target_creators:
                    logger.debug(f"  → 跳过: 作者 {author_name} 不在目标创建者列表中")
                    continue

            # 检查是否已处理过
            if mr_iid and mr_project_id:
                if self.db.is_mr_processed(user_id, mr_project_id, mr_iid):
                    logger.debug(f"  → 跳过: MR {mr_project_id}!{mr_iid} 已处理过")
                    continue

            logger.info(f"  → 筛选通过: {mr_project_id}!{mr_iid} - {mr_title}")
            filtered_mrs.append(mr_info)

        logger.info(f"用户 {user_id} 找到 {len(filtered_mrs)} 个待处理的 MR")

        # 处理每个 MR
        for mr in filtered_mrs:
            try:
                await self._review_and_approve_mr(
                    client, mr, user_id, config, ai_config
                )
                # 记录已处理
                mr_iid = getattr(mr, "iid", None)
                mr_project_id = getattr(mr, "project_id", None)
                mr_web_url = getattr(mr, "web_url", None)
                mr_title = getattr(mr, "title", None)
                if mr_iid and mr_project_id:
                    self.db.upsert_processed_mr(
                        user_id, mr_project_id, mr_iid,
                        web_url=mr_web_url,
                        title=mr_title
                    )
            except Exception as e:
                logger.error(f"处理 MR 失败: {e}")

    async def _review_and_approve_mr(
        self, client: GitLabClient, mr, user_id: int,
        config: Dict[str, Any], ai_config: Dict[str, Any]
    ):
        """审查并批准单个 MR"""
        mr_iid = getattr(mr, "iid", None)
        mr_project_id = getattr(mr, "project_id", None)

        if not mr_iid or not mr_project_id:
            logger.warning(f"MR 缺少必要字段: iid={mr_iid}, project_id={mr_project_id}")
            return

        # 生成 AI 总结
        summary = await self._generate_mr_summary(
            client, mr_project_id, mr_iid, mr, ai_config
        )

        # 添加为评论
        if config.get("add_as_comment", True):
            try:
                client.create_merge_request_note(
                    mr_project_id,
                    mr_iid,
                    f"## AI Review Summary\n\n{summary}"
                )
                logger.info(f"已为 MR {mr_project_id}!{mr_iid} 添加 AI 总结评论")
            except Exception as e:
                logger.error(f"添加评论失败: {e}")

        # 判断是否自动批准
        should_approve = self._should_auto_approve(summary, config)

        if should_approve:
            try:
                client.approve_merge_request(mr_project_id, mr_iid)
                logger.info(f"已自动批准 MR {mr_project_id}!{mr_iid}")
            except Exception as e:
                logger.error(f"自动批准 MR {mr_project_id}!{mr_iid} 失败: {e}")

    _AUTH_QUOTA_KEYWORDS = ("认证失败", "api_key", "api key", "密钥", "配额", "quota", "429", "401", "unauthorized", "authentication failed", "rate limit", "expired")

    def _is_auth_or_quota_error(self, error_text: str) -> bool:
        """判断错误文本是否属于认证/配额类错误"""
        text_lower = error_text.lower()
        return any(kw in text_lower for kw in self._AUTH_QUOTA_KEYWORDS)

    async def _generate_mr_summary(
        self, client: GitLabClient, project_id: int, mr_iid: int, mr, ai_config: Dict[str, Any]
    ) -> str:
        """生成 MR 总结，支持多 Provider fallback（仅认证/配额错误时）"""
        from server.api.ai import _build_review_config_from_provider, stream_summarize

        user_id = ai_config.get("user_id")
        if not user_id:
            raise RuntimeError("无法获取用户 ID")

        # 获取激活的 provider
        active_provider = self.db.get_active_ai_provider(user_id)
        if not active_provider:
            raise RuntimeError("AI Provider 未配置或未激活")

        # 获取所有 provider，active 排第一，其余按创建时间排序
        all_providers = self.db.list_ai_providers(user_id)
        providers = sorted(
            all_providers,
            key=lambda p: 0 if p["id"] == active_provider["id"] else 1
        )

        last_error = None
        for provider in providers:
            provider_name = provider.get("name", provider.get("provider_type", "unknown"))
            config = _build_review_config_from_provider(provider, ai_config.get("review_rules", []))

            summary_parts = []
            try:
                async for chunk in stream_summarize(
                    client, str(project_id), mr_iid, config, ai_config
                ):
                    summary_parts.append(chunk)
            except (AIAuthError, AIQuotaError) as e:
                # 防御性代码：当前 stream_summarize 会吞掉所有异常转为 yield 文本
                # 此分支暂不会触发，保留以应对 stream_summarize 未来可能的行为变更
                logger.warning(f"Provider '{provider_name}' 失败: {e}，尝试下一个")
                last_error = e
                continue
            except Exception as e:
                logger.error(f"MR {project_id}!{mr_iid} 的 AI 总结生成异常: {e}")
                raise

            result = "".join(summary_parts)
            # 检测 stream_summarize 内部捕获异常后 yield 的错误标记
            if "[错误:" in result:
                if self._is_auth_or_quota_error(result):
                    logger.warning(f"Provider '{provider_name}' 失败: {result.strip()}，尝试下一个")
                    last_error = RuntimeError(result)
                    continue
                raise RuntimeError(f"AI 总结失败: {result}")

            if provider["id"] != active_provider["id"]:
                logger.info(f"MR {project_id}!{mr_iid} 成功使用 fallback provider '{provider_name}' 完成总结")
            return result

        # 所有 provider 都失败了
        raise last_error or RuntimeError("所有 AI Provider 均不可用")

    def _should_auto_approve(self, summary: str, config: Dict[str, Any]) -> bool:
        """判断是否应该自动批准"""
        # 防御性检查：正常情况下 _generate_mr_summary 已在返回前 raise 异常
        # 此处作为兜底，防止异常路径上的边界情况
        if "[错误:" in summary:
            logger.warning("总结中包含错误信息，跳过自动批准")
            return False

        mode = config.get("auto_approve_mode", "always")

        if mode == "never":
            return False
        elif mode == "always":
            return True
        elif mode == "keyword_only":
            keywords = config.get("auto_approve_keywords", [])
            if not keywords:
                return False  # 没有关键词时不批准
            # 检查总结中是否包含任一关键词
            return any(kw.lower() in summary.lower() for kw in keywords)

        return False
