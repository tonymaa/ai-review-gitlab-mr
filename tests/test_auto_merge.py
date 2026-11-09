"""自动合并逻辑与配置持久化测试

使用标准库 unittest，不引入额外测试依赖。
"""

import os
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from src.core.database import DatabaseManager
from src.gitlab.models import MRState
from src.scheduler.auto_review_scheduler import AutoReviewScheduler


class AutoMergeTriggerTests(unittest.IsolatedAsyncioTestCase):
    """单次触发时的开关门控测试"""

    def _scheduler(self, config):
        scheduler = AutoReviewScheduler(Mock())
        scheduler.db.get_auto_review_config.return_value = config
        scheduler._process_auto_merge = AsyncMock()
        scheduler._process_auto_review = AsyncMock()
        return scheduler

    async def test_trigger_runs_auto_merge_without_auto_review(self):
        scheduler = self._scheduler({"enabled": False, "auto_merge_enabled": True})
        await scheduler.trigger_single_run(1)

        scheduler._process_auto_merge.assert_awaited_once_with(1)
        scheduler._process_auto_review.assert_not_awaited()

    async def test_trigger_runs_both_when_both_enabled(self):
        scheduler = self._scheduler({"enabled": True, "auto_merge_enabled": True})
        await scheduler.trigger_single_run(1)

        scheduler._process_auto_merge.assert_awaited_once_with(1)
        scheduler._process_auto_review.assert_awaited_once()

    async def test_trigger_skips_auto_merge_when_disabled(self):
        scheduler = self._scheduler({"enabled": True, "auto_merge_enabled": False})
        await scheduler.trigger_single_run(1)

        scheduler._process_auto_merge.assert_not_awaited()
        scheduler._process_auto_review.assert_awaited_once()

    async def test_trigger_does_nothing_when_both_disabled(self):
        scheduler = self._scheduler({"enabled": False, "auto_merge_enabled": False})
        await scheduler.trigger_single_run(1)

        scheduler._process_auto_merge.assert_not_awaited()
        scheduler._process_auto_review.assert_not_awaited()

    async def test_trigger_does_nothing_without_config(self):
        scheduler = self._scheduler(None)
        await scheduler.trigger_single_run(1)

        scheduler._process_auto_merge.assert_not_awaited()
        scheduler._process_auto_review.assert_not_awaited()


class AutoMergeProcessingTests(unittest.IsolatedAsyncioTestCase):
    """自动合并执行测试"""

    def _mr(self, **overrides):
        data = {
            "state": MRState.OPENED,
            "project_id": 10,
            "iid": 1,
            "title": "Test MR",
            "approved_by": [SimpleNamespace(id=2, username="reviewer", name="Reviewer")],
            "is_approved": True,
            "approvals_left": 0,
            "approvals_required": 1,
            "has_conflicts": False,
            "work_in_progress": False,
            "draft": False,
            "blocking_discussions_resolved": True,
            "detailed_merge_status": "mergeable",
            "merge_status": "can_be_merged",
        }
        data.update(overrides)
        return SimpleNamespace(**data)

    async def test_merges_only_approved_and_mergeable_authored_mrs(self):
        scheduler = AutoReviewScheduler(Mock())
        scheduler.db.get_gitlab_config.return_value = {
            "url": "https://gitlab.example.com",
            "token": "token",
        }

        approved = self._mr()
        not_approved = self._mr(iid=2, is_approved=False)
        not_mergeable = self._mr(iid=3, detailed_merge_status="ci_still_running")

        client = Mock()
        client.list_all_merge_requests_authored_by_me.return_value = [
            (approved, SimpleNamespace(path_with_namespace="group/project")),
            (not_approved, None),
            (not_mergeable, None),
        ]
        client.accept_merge_request.return_value = True

        with patch(
            "src.scheduler.auto_review_scheduler.GitLabClient", return_value=client
        ):
            await scheduler._process_auto_merge(1)

        client.accept_merge_request.assert_called_once_with(
            project_id=10,
            mr_iid=1,
            should_remove_source_branch=False,
        )

    async def test_skips_when_gitlab_not_configured(self):
        scheduler = AutoReviewScheduler(Mock())
        scheduler.db.get_gitlab_config.return_value = None

        with patch(
            "src.scheduler.auto_review_scheduler.GitLabClient"
        ) as client_cls:
            await scheduler._process_auto_merge(1)

        client_cls.assert_not_called()


class AutoMergeDecisionTests(unittest.TestCase):
    """自动合并判定逻辑测试"""

    def setUp(self):
        self.scheduler = AutoReviewScheduler(Mock())

    def _mr(self, **overrides):
        data = {
            "approved_by": [SimpleNamespace(id=2, username="reviewer", name="Reviewer")],
            "is_approved": True,
            "approvals_left": 0,
            "approvals_required": 1,
            "has_conflicts": False,
            "work_in_progress": False,
            "draft": False,
            "blocking_discussions_resolved": True,
            "detailed_merge_status": "mergeable",
            "merge_status": "can_be_merged",
        }
        data.update(overrides)
        return SimpleNamespace(**data)

    def test_approved_and_mergeable(self):
        self.assertTrue(self.scheduler._is_mr_approved(self._mr()))
        self.assertTrue(self.scheduler._is_mr_mergeable(self._mr()))

    def test_requires_at_least_one_approver(self):
        self.assertFalse(self.scheduler._is_mr_approved(self._mr(approved_by=[])))

    def test_requires_all_approvals(self):
        self.assertFalse(self.scheduler._is_mr_approved(self._mr(approvals_left=1)))

    def test_requires_approved_flag(self):
        self.assertFalse(self.scheduler._is_mr_approved(self._mr(is_approved=False)))

    def test_skips_conflicts(self):
        self.assertFalse(self.scheduler._is_mr_mergeable(self._mr(has_conflicts=True)))

    def test_skips_draft(self):
        self.assertFalse(self.scheduler._is_mr_mergeable(self._mr(draft=True)))

    def test_skips_wip(self):
        self.assertFalse(self.scheduler._is_mr_mergeable(self._mr(work_in_progress=True)))

    def test_skips_unresolved_discussions(self):
        self.assertFalse(
            self.scheduler._is_mr_mergeable(
                self._mr(blocking_discussions_resolved=False)
            )
        )

    def test_skips_non_mergeable_detailed_status(self):
        self.assertFalse(
            self.scheduler._is_mr_mergeable(
                self._mr(detailed_merge_status="ci_still_running")
            )
        )

    def test_falls_back_to_merge_status(self):
        self.assertTrue(
            self.scheduler._is_mr_mergeable(
                self._mr(detailed_merge_status=None, merge_status="can_be_merged")
            )
        )
        self.assertFalse(
            self.scheduler._is_mr_mergeable(
                self._mr(detailed_merge_status=None, merge_status="cannot_be_merged")
            )
        )


class AutoMergeConfigPersistenceTests(unittest.TestCase):
    """auto_merge_enabled 配置持久化与迁移测试"""

    def test_auto_merge_flag_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = DatabaseManager(os.path.join(tmp, "test.db"))

            db.upsert_auto_review_config(
                user_id=1, enabled=False, auto_merge_enabled=True
            )
            config = db.get_auto_review_config(1)
            self.assertIsNotNone(config)
            self.assertTrue(config["auto_merge_enabled"])

            db.upsert_auto_review_config(
                user_id=1, enabled=False, auto_merge_enabled=False
            )
            self.assertFalse(db.get_auto_review_config(1)["auto_merge_enabled"])
            db.engine.dispose()

    def test_list_enabled_includes_auto_merge_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = DatabaseManager(os.path.join(tmp, "test.db"))
            db.upsert_auto_review_config(
                user_id=1, enabled=False, auto_merge_enabled=True
            )
            db.upsert_auto_review_config(
                user_id=2, enabled=False, auto_merge_enabled=False
            )

            configs = db.list_enabled_auto_review_configs()
            self.assertEqual({c["user_id"] for c in configs}, {1})
            self.assertTrue(
                next(c for c in configs if c["user_id"] == 1)["auto_merge_enabled"]
            )
            db.engine.dispose()

    def test_migration_adds_column_to_old_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "legacy.db")

            conn = sqlite3.connect(path)
            conn.execute(
                """
                CREATE TABLE auto_review_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    enabled BOOLEAN NOT NULL DEFAULT 0,
                    interval_seconds INTEGER NOT NULL DEFAULT 120,
                    target_creators TEXT,
                    target_projects TEXT,
                    auto_approve_keywords TEXT,
                    auto_approve_mode VARCHAR(20) NOT NULL DEFAULT 'always',
                    add_as_comment BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            )
            conn.commit()
            conn.close()

            db = DatabaseManager(path)
            check_conn = sqlite3.connect(path)
            try:
                columns = [
                    row[1]
                    for row in check_conn.execute(
                        "PRAGMA table_info(auto_review_configs)"
                    )
                ]
            finally:
                check_conn.close()
            self.assertIn("auto_merge_enabled", columns)

            db.upsert_auto_review_config(user_id=1, auto_merge_enabled=True)
            self.assertTrue(db.get_auto_review_config(1)["auto_merge_enabled"])
            db.engine.dispose()


if __name__ == "__main__":
    unittest.main()
