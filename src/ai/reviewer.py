"""AI代码审查模块 - 支持OpenAI和Ollama"""

import json
import logging
from typing import List, Optional, Dict, Any, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..gitlab.models import MergeRequestInfo, DiffFile, AIReviewResult
from .prompts import (
    SYSTEM_PROMPT,
    build_review_prompt,
    build_file_review_prompt,
    build_quick_review_prompt,
)

logger = logging.getLogger(__name__)


class ReviewProvider(Enum):
    """AI服务提供商"""
    OPENAI = "openai"
    OLLAMA = "ollama"
    AZURE = "azure"


@dataclass
class ReviewIssue:
    """审查问题"""
    file_path: str
    line_number: Optional[int]
    description: str
    severity: str = "suggestion"  # critical, warning, suggestion


@dataclass
class FileReview:
    """单文件审查结果"""
    file_path: str
    issues: List[ReviewIssue] = field(default_factory=list)
    warnings: List[ReviewIssue] = field(default_factory=list)
    suggestions: List[ReviewIssue] = field(default_factory=list)
    summary: str = ""


class AIReviewer:
    """AI代码审查器基类"""

    def __init__(
        self,
        provider: ReviewProvider,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ):
        """
        初始化AI审查器

        Args:
            provider: AI服务提供商
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数
        """
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def review_merge_request(
        self,
        mr: MergeRequestInfo,
        diff_files: List[DiffFile],
        review_rules: List[str],
        quick_mode: bool = False,
    ) -> AIReviewResult:
        """
        审查整个Merge Request

        Args:
            mr: Merge Request信息
            diff_files: Diff文件列表
            review_rules: 审查规则列表
            quick_mode: 快速模式（只审查摘要）

        Returns:
            AIReviewResult对象
        """
        raise NotImplementedError("子类必须实现此方法")

    def review_diff_file(self, diff_file: DiffFile) -> FileReview:
        """
        审查单个Diff文件

        Args:
            diff_file: Diff文件对象

        Returns:
            FileReview对象
        """
        raise NotImplementedError("子类必须实现此方法")


class OpenAIReviewer(AIReviewer):
    """OpenAI审查器实现"""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4",
        base_url: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ):
        super().__init__(
            provider=ReviewProvider.OPENAI,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self.api_key = api_key
        self.base_url = base_url

        try:
            import openai
            self.client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
            )
            logger.info(f"OpenAI审查器初始化成功，模型: {model}")
        except ImportError:
            raise ImportError("请安装openai包: pip install openai")

    async def _call_api(
        self,
        messages: List[Dict[str, str]],
        response_format: Optional[str] = None,
    ) -> str:
        """
        调用OpenAI API

        Args:
            messages: 消息列表
            response_format: 响应格式 (json_object/text)

        Returns:
            API响应文本
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API调用失败: {e}")
            raise

    def review_merge_request(
        self,
        mr: MergeRequestInfo,
        diff_files: List[DiffFile],
        review_rules: List[str],
        quick_mode: bool = False,
    ) -> AIReviewResult:
        """
        审查整个Merge Request

        Args:
            mr: Merge Request信息
            diff_files: Diff文件列表
            review_rules: 审查规则列表
            quick_mode: 快速模式

        Returns:
            AIReviewResult对象
        """
        import asyncio

        # 构建文件变更摘要
        file_changes = self._build_file_changes_summary(diff_files)

        # 构建提示词
        if quick_mode:
            prompt = build_quick_review_prompt(file_changes)
        else:
            prompt = build_review_prompt(
                title=mr.title,
                description=mr.description or "",
                source_branch=mr.source_branch,
                target_branch=mr.target_branch,
                file_changes=file_changes,
                review_rules=review_rules,
            )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        # 调用API
        try:
            response = asyncio.run(self._call_api(messages, response_format="json"))
            result = self._parse_review_response(response)
        except Exception as e:
            logger.error(f"AI审查失败: {e}")
            return self._create_error_result(str(e))

        # 补充详细信息
        result.provider = "openai"
        result.model = self.model

        return result

    def review_diff_file(self, diff_file: DiffFile) -> FileReview:
        """
        审查单个Diff文件

        Args:
            diff_file: Diff文件对象

        Returns:
            FileReview对象
        """
        import asyncio

        change_type = "新增" if diff_file.new_file else "修改" if not diff_file.deleted_file else "删除"
        prompt = build_file_review_prompt(
            file_path=diff_file.get_display_path(),
            change_type=change_type,
            diff_content=diff_file.diff,
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        try:
            response = asyncio.run(self._call_api(messages, response_format="json"))
            return self._parse_file_review(response, diff_file)
        except Exception as e:
            logger.error(f"文件审查失败: {e}")
            return FileReview(file_path=diff_file.get_display_path())

    def _build_file_changes_summary(self, diff_files: List[DiffFile]) -> str:
        """构建文件变更摘要"""
        summary_lines = []
        for df in diff_files:
            change_indicator = "+ " if df.new_file else "- " if df.deleted_file else "M "
            summary_lines.append(
                f"{change_indicator}{df.get_display_path()} "
                f"(+{df.additions}, -{df.deletions})"
            )
        return "\n".join(summary_lines)

    def _parse_review_response(self, response: str) -> AIReviewResult:
        """解析审查响应"""
        try:
            data = json.loads(response)

            return AIReviewResult(
                provider="",  # 由调用方设置
                model="",     # 由调用方设置
                summary=data.get("summary", ""),
                overall_score=data.get("overall_score", 5),
                issues_count=len(data.get("issues", [])),
                suggestions_count=len(data.get("suggestions", [])),
                file_reviews=data.get("file_reviews", {}),
                critical_issues=[i.get("description", "") for i in data.get("issues", [])],
                warnings=[w.get("description", "") for w in data.get("warnings", [])],
                suggestions=[s.get("description", "") for s in data.get("suggestions", [])],
            )
        except json.JSONDecodeError:
            # 如果解析失败，返回基本信息
            return AIReviewResult(
                provider="",
                model="",
                summary=response[:500] if len(response) > 500 else response,
                overall_score=5,
                issues_count=0,
                suggestions_count=0,
            )

    def _parse_file_review(self, response: str, diff_file: DiffFile) -> FileReview:
        """解析单文件审查响应"""
        try:
            data = json.loads(response)

            file_review = FileReview(
                file_path=diff_file.get_display_path(),
                summary=data.get("summary", ""),
            )

            # 解析issues
            for issue in data.get("issues", []):
                file_review.issues.append(ReviewIssue(
                    file_path=diff_file.get_display_path(),
                    line_number=issue.get("line_number"),
                    description=issue.get("description", ""),
                    severity="critical",
                ))

            # 解析warnings
            for warning in data.get("warnings", []):
                file_review.warnings.append(ReviewIssue(
                    file_path=diff_file.get_display_path(),
                    line_number=warning.get("line_number"),
                    description=warning.get("description", ""),
                    severity="warning",
                ))

            # 解析suggestions
            for suggestion in data.get("suggestions", []):
                file_review.suggestions.append(ReviewIssue(
                    file_path=diff_file.get_display_path(),
                    line_number=suggestion.get("line_number"),
                    description=suggestion.get("description", ""),
                    severity="suggestion",
                ))

            return file_review

        except json.JSONDecodeError:
            return FileReview(file_path=diff_file.get_display_path())

    def _create_error_result(self, error_message: str) -> AIReviewResult:
        """创建错误结果"""
        return AIReviewResult(
            provider="openai",
            model=self.model,
            summary=f"审查过程中发生错误: {error_message}",
            overall_score=1,
            issues_count=0,
            suggestions_count=0,
            critical_issues=[error_message],
        )


class OllamaReviewer(AIReviewer):
    """Ollama本地模型审查器实现"""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "codellama",
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ):
        super().__init__(
            provider=ReviewProvider.OLLAMA,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self.base_url = base_url

        try:
            import httpx
            self.client = httpx.AsyncClient(timeout=120.0)
            logger.info(f"Ollama审查器初始化成功，模型: {model}")
        except ImportError:
            raise ImportError("请安装httpx包: pip install httpx")

    async def _call_api(self, prompt: str) -> str:
        """调用Ollama API"""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except Exception as e:
            logger.error(f"Ollama API调用失败: {e}")
            raise

    def review_merge_request(
        self,
        mr: MergeRequestInfo,
        diff_files: List[DiffFile],
        review_rules: List[str],
        quick_mode: bool = False,
    ) -> AIReviewResult:
        """审查整个Merge Request"""
        import asyncio

        file_changes = self._build_file_changes_summary(diff_files)
        prompt = build_review_prompt(
            title=mr.title,
            description=mr.description or "",
            source_branch=mr.source_branch,
            target_branch=mr.target_branch,
            file_changes=file_changes,
            review_rules=review_rules,
        )

        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"

        try:
            response = asyncio.run(self._call_api(full_prompt))
            # Ollama可能不返回JSON，尝试解析
            return self._parse_text_response(response)
        except Exception as e:
            logger.error(f"Ollama审查失败: {e}")
            return self._create_error_result(str(e))

    def review_diff_file(self, diff_file: DiffFile) -> FileReview:
        """审查单个Diff文件"""
        # Ollama的文件审查实现
        return FileReview(file_path=diff_file.get_display_path())

    def _build_file_changes_summary(self, diff_files: List[DiffFile]) -> str:
        """构建文件变更摘要"""
        summary_lines = []
        for df in diff_files:
            change_indicator = "+ " if df.new_file else "- " if df.deleted_file else "M "
            summary_lines.append(
                f"{change_indicator}{df.get_display_path()} "
                f"(+{df.additions}, -{df.deletions})"
            )
        return "\n".join(summary_lines)

    def _parse_text_response(self, response: str) -> AIReviewResult:
        """解析文本响应"""
        return AIReviewResult(
            provider="ollama",
            model=self.model,
            summary=response[:1000],
            overall_score=5,
            issues_count=0,
            suggestions_count=0,
        )

    def _create_error_result(self, error_message: str) -> AIReviewResult:
        """创建错误结果"""
        return AIReviewResult(
            provider="ollama",
            model=self.model,
            summary=f"审查过程中发生错误: {error_message}",
            overall_score=1,
            issues_count=0,
            suggestions_count=0,
        )


def create_reviewer(
    provider: str,
    **kwargs,
) -> AIReviewer:
    """
    创建AI审查器工厂函数

    Args:
        provider: 服务提供商名称
        **kwargs: 额外参数

    Returns:
        AI审查器实例
    """
    provider = provider.lower()

    if provider == "openai":
        return OpenAIReviewer(
            api_key=kwargs.get("api_key", ""),
            model=kwargs.get("model", "gpt-4"),
            base_url=kwargs.get("base_url"),
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 2000),
        )
    elif provider == "ollama":
        return OllamaReviewer(
            base_url=kwargs.get("base_url", "http://localhost:11434"),
            model=kwargs.get("model", "codellama"),
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 2000),
        )
    else:
        raise ValueError(f"不支持的AI服务提供商: {provider}")
