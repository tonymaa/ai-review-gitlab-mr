"""AI代码审查模块 - 支持OpenAI和Ollama"""

import json
import logging
from typing import List, Optional, Dict, Any, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..gitlab.models import MergeRequestInfo, DiffFile, AIReviewResult
from ..core.exceptions import (
    AIConnectionError,
    AIAuthError,
    AIQuotaError,
    AIModelNotFoundError,
    AIException,
)
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


@dataclass
class TokenUsage:
    """Token使用统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: 'TokenUsage') -> 'TokenUsage':
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


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
    ) -> tuple[str, TokenUsage]:
        """
        调用OpenAI API (使用流式输出，实时显示到控制台)

        Args:
            messages: 消息列表
            response_format: 响应格式 (json_object/text)

        Returns:
            (API响应文本, Token使用统计)

        Raises:
            AIConnectionError: 连接AI服务失败
            AIAuthError: API密钥无效
            AIQuotaError: 配额不足
            AIModelNotFoundError: 模型不存在
            AIException: 其他AI错误
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,  # 启用流式输出
        }

        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        try:
            full_content = []
            usage = TokenUsage()
            print("\n\033[90m┌─ AI Response:\033[0m", end="", flush=True)

            stream = await self.client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content.append(content)
                    # 实时输出到控制台（灰色，不干扰正常输出）
                    print(content, end="", flush=True)

                # 捕获token使用情况（在最后一个chunk中）
                if chunk.usage:
                    usage.prompt_tokens = chunk.usage.prompt_tokens or 0
                    usage.completion_tokens = chunk.usage.completion_tokens or 0
                    usage.total_tokens = chunk.usage.total_tokens or 0

            print("\033[90m\n└─ End\033[0m\n")  # 结束标记

            # 记录token使用情况
            logger.info(
                f"Token使用 - 输入: {usage.prompt_tokens}, "
                f"输出: {usage.completion_tokens}, "
                f"总计: {usage.total_tokens}"
            )

            return "".join(full_content), usage

        except Exception as e:
            error_str = str(e).lower()
            error_msg = str(e)

            # 根据错误类型抛出相应的异常
            if "authentication" in error_str or "unauthorized" in error_str or "401" in error_str:
                raise AIAuthError("OpenAI API认证失败", "请检查API密钥是否正确")
            elif "quota" in error_str or "429" in error_str or "limit" in error_str:
                raise AIQuotaError("OpenAI API配额不足", "请检查账户余额或使用限制")
            elif "model" in error_str and "not found" in error_str:
                raise AIModelNotFoundError("模型不存在", f"模型: {self.model}")
            elif "connection" in error_str or "timeout" in error_str:
                raise AIConnectionError("连接OpenAI服务失败", error_msg)
            else:
                raise AIException("AI审查失败", error_msg)

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

        async def _review_all_files():
            """异步审查所有文件"""
            # 收集所有文件的审查结果
            all_file_reviews: Dict[str, List[Dict[str, Any]]] = {}
            all_issues: List[str] = []
            all_warnings: List[str] = []
            all_suggestions: List[str] = []
            total_usage = TokenUsage()

            # 逐个审查每个文件
            for diff_file in diff_files:
                try:
                    # 构建单文件审查提示词
                    change_type = "New" if diff_file.new_file else "Modified" if not diff_file.deleted_file else "Deleted"
                    prompt = self._build_detailed_file_review_prompt(
                        file_path=diff_file.get_display_path(),
                        change_type=change_type,
                        diff_content=diff_file.diff,
                        review_rules=review_rules,
                    )
                    messages = [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ]

                    # 调用API，获取响应和token使用量
                    response, usage = await self._call_api(messages, response_format="json")
                    total_usage += usage

                    # 解析结果
                    file_reviews = self._parse_detailed_file_review(response, diff_file.get_display_path())

                    if file_reviews:
                        all_file_reviews[diff_file.get_display_path()] = file_reviews

                        # 分类问题
                        for review in file_reviews:
                            severity = review.get("severity", "suggestion")
                            description = review.get("description", "")
                            line_number = review.get("line_number")

                            # 构建带位置信息的描述
                            location_desc = f"{diff_file.get_display_path()}"
                            if line_number:
                                location_desc += f":{line_number}"
                            full_desc = f"{location_desc} - {description}"

                            if severity == "critical":
                                all_issues.append(full_desc)
                            elif severity == "warning":
                                all_warnings.append(full_desc)
                            else:
                                all_suggestions.append(full_desc)

                except (AIAuthError, AIQuotaError, AIModelNotFoundError, AIConnectionError) as e:
                    # 这些是致命错误，应该立即停止审查
                    logger.error(f"AI 服务错误，停止审查: {e}")
                    raise
                except Exception as e:
                    # 其他错误只记录日志，继续审查下一个文件
                    logger.error(f"审查文件 {diff_file.get_display_path()} 失败: {e}")
                    continue

            # 构建整体摘要
            summary = self._build_overall_summary(
                mr=mr,
                diff_files=diff_files,
                total_issues=len(all_issues),
                total_warnings=len(all_warnings),
                total_suggestions=len(all_suggestions),
                total_usage=total_usage,
            )

            # 创建结果
            result = AIReviewResult(
                provider="openai",
                model=self.model,
                summary=summary,
                overall_score=self._calculate_score(len(all_issues), len(all_warnings)),
                issues_count=len(all_issues),
                suggestions_count=len(all_warnings) + len(all_suggestions),
                file_reviews=all_file_reviews,
                critical_issues=all_issues,
                warnings=all_warnings,
                suggestions=all_suggestions,
            )

            return result

        # 检查是否已有运行中的事件循环（比如在 FastAPI 中）
        try:
            loop = asyncio.get_running_loop()
            # 已有运行中的循环，使用 nest_asyncio 来支持嵌套
            import nest_asyncio
            nest_asyncio.apply()
            result = loop.run_until_complete(_review_all_files())
            # 不关闭客户端，因为循环不是我们创建的
            return result
        except RuntimeError:
            # 没有运行中的循环，创建新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(_review_all_files())
                return result
            finally:
                # 先关闭客户端，再关闭事件循环
                try:
                    loop.run_until_complete(self.client.close())
                except Exception:
                    pass
                loop.close()

    def _build_detailed_file_review_prompt(
        self,
        file_path: str,
        change_type: str,
        diff_content: str,
        review_rules: List[str],
    ) -> str:
        """构建详细的文件审查提示词"""
        rules_text = "\\n".join(f"- {rule}" for rule in review_rules)

        # 预处理diff内容，添加行号标注
        annotated_diff = self._annotate_diff_with_line_numbers(diff_content)

        prompt = f"""Please review the following code changes:

## File Path
{file_path}

## Change Type
{change_type}

## Review Rules
{rules_text}

## CRITICAL: How to Report Line Numbers

**READ THE LINE NUMBERS FROM THE BRACKETS [OLD:N | NEW:N]**

Each line in the diff shows: [OLD:number | NEW:number] prefix code

**Rules:**
1. ONLY review lines starting with `+` (added)
2. IGNORE lines starting with `-` (removed) or ` ` (space)
3. For `+` lines: Copy the number AFTER `NEW:`
4. line_number must be a plain INTEGER (no quotes, no text, just the number)

**Example:**
[OLD:10 | NEW:10] function foo() {{    <-- IGNORE (context)
[OLD:-  | NEW:11]+  const x = 1;       <-- Report: "line_number": 11
[OLD:-  | NEW:12]+  return x;          <-- Report: "line_number": 12
[OLD:12 | NEW:13] }}                   <-- IGNORE (context)

**Correct output format:**
{{
  "reviews": [
    {{
      "line_number": 11,
      "severity": "warning",
      "description": "variable x is declared but never used"
    }},
    {{
      "line_number": 12,
      "severity": "suggestion",
      "description": "consider using early return pattern"
    }}
  ]
}}

**WRONG formats (DO NOT USE):**
- "line_number": "NEW:11"     <- WRONG! Don't include NEW:
- "line_number": "11"         <- WRONG! Don't use quotes
- "line_number": null         <- WRONG! Always provide a number
- "line_number": "line 11"    <- WRONG! Just the number

## Diff Content to Review
--- diff
{annotated_diff}
---

Review ONLY lines starting with + (added). Output valid JSON with integer line_numbers."""
        return prompt

    def _annotate_diff_with_line_numbers(self, diff_content: str) -> str:
        """
        为diff内容添加行号标注
        格式: [OLD:N | NEW:N] prefix content
        """
        import re

        lines = diff_content.split('\n')
        annotated_lines = []

        # 当前行号追踪
        old_line = None
        new_line = None

        for line in lines:
            # 检查是否是hunk头部
            hunk_match = re.match(r'@@\s+-(\d+),?\d*\s+\+(\d+),?\d*\s+@@', line)
            if hunk_match:
                # 新的hunk开始，重置行号
                # hunk的起始行号是1-based，但还没开始计数
                old_start = int(hunk_match.group(1))
                new_start = int(hunk_match.group(2))
                # hunk头部行不计数，保留原样
                annotated_lines.append(line)
                # 设置下一行的起始行号（减1，因为会在处理时+1）
                old_line = old_start - 1
                new_line = new_start - 1
                continue

            # 根据行前缀处理
            if line.startswith('+') and not line.startswith('+++'):
                # 新增行 - new_line增加
                new_line += 1
                old_display = '-'
                new_display = new_line
            elif line.startswith('-') and not line.startswith('---'):
                # 删除行 - old_line增加
                old_line += 1
                old_display = old_line
                new_display = '-'
            elif line.startswith(' '):
                # 上下文行 - 都增加
                old_line += 1
                new_line += 1
                old_display = old_line
                new_display = new_line
            else:
                # 其他行（文件头、hunk头等）- 不加行号标注
                annotated_lines.append(line)
                continue

            # 格式化行号标注
            annotation = f"[OLD:{old_display} | NEW:{new_display}]"
            annotated_lines.append(f"{annotation} {line}")

        return '\n'.join(annotated_lines)

    def _parse_detailed_file_review(self, response: str, file_path: str) -> List[Dict[str, Any]]:
        """解析详细的文件审查响应"""
        try:
            data = json.loads(response)
            reviews = data.get("reviews", [])
            result = []
            for review in reviews:
                result.append({
                    "line_number": review.get("line_number"),
                    "severity": review.get("severity", "suggestion"),
                    "description": review.get("description", ""),
                })

            return result

        except json.JSONDecodeError as e:
            logger.error(f"解析文件审查响应失败: {e}")
            return []

    def _build_overall_summary(
        self,
        mr: MergeRequestInfo,
        diff_files: List[DiffFile],
        total_issues: int,
        total_warnings: int,
        total_suggestions: int,
        total_usage: TokenUsage = None,
    ) -> str:
        """构建整体审查摘要"""
        summary_parts = [
            f"## Merge Request Review Summary",
            f"",
            f"**Title:** {mr.title}",
            f"**Source Branch:** {mr.source_branch} → **Target Branch:** {mr.target_branch}",
            f"",
            f"### Statistics",
            f"- Files changed: {len(diff_files)}",
            f"- Critical issues: {total_issues}",
            f"- Warnings: {total_warnings}",
            f"- Suggestions: {total_suggestions}",
        ]

        # 添加token使用统计
        if total_usage and total_usage.total_tokens > 0:
            summary_parts.extend([
                f"",
                f"### Token Usage",
                f"- Input tokens: {total_usage.prompt_tokens}",
                f"- Output tokens: {total_usage.completion_tokens}",
                f"- Total tokens: {total_usage.total_tokens}",
            ])

        return "\n".join(summary_parts)

    def _calculate_score(self, issues: int, warnings: int) -> int:
        """计算整体评分 (1-10)"""
        score = 10
        score -= issues * 2  # 每个严重问题扣2分
        score -= warnings * 0.5  # 每个警告扣0.5分
        return max(1, min(10, int(score)))

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
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response, usage = loop.run_until_complete(self._call_api(messages, response_format="json"))
            logger.info(
                f"文件 {diff_file.get_display_path()} 审查完成 - "
                f"Token: {usage.prompt_tokens}输入 + {usage.completion_tokens}输出 = {usage.total_tokens}总计"
            )
            result = self._parse_file_review(response, diff_file)
            return result
        except (AIAuthError, AIQuotaError, AIModelNotFoundError, AIConnectionError) as e:
            # 这些是致命错误，应该抛出
            logger.error(f"AI 服务错误: {e}")
            raise
        except Exception as e:
            # 其他错误返回空结果
            logger.error(f"文件审查失败: {e}")
            return FileReview(file_path=diff_file.get_display_path())
        finally:
            try:
                loop.run_until_complete(self.client.close())
            except Exception:
                pass
            loop.close()

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

        except json.JSONDecodeError as e:
            logger.error(f"解析文件审查响应失败: {e}")
            logger.error(f"原始响应内容: {response[:500]}...")
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
        """调用Ollama API (使用流式输出，实时显示到控制台)"""
        try:
            print("\n\033[90m┌─ AI Response:\033[0m", end="", flush=True)

            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": True,  # 启用流式输出
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens,
                    },
                },
            )
            response.raise_for_status()

            full_content = []
            async for line in response.aiter_lines():
                if line.strip():
                    data = json.loads(line)
                    if "response" in data:
                        content = data["response"]
                        full_content.append(content)
                        print(content, end="", flush=True)
                    if data.get("done", False):
                        break

            print("\033[90m\n└─ End\033[0m\n")
            return "".join(full_content)
        except Exception as e:
            error_str = str(e).lower()
            error_msg = str(e)

            # 根据错误类型抛出相应的异常
            if "connection" in error_str or "timeout" in error_str:
                raise AIConnectionError("连接Ollama服务失败", f"请检查Ollama服务是否运行。URL: {self.base_url}")
            else:
                raise AIException("Ollama API调用失败", error_msg)

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
