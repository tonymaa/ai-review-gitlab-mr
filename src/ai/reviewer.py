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

        # 收集所有文件的审查结果
        all_file_reviews: Dict[str, List[Dict[str, Any]]] = {}
        all_issues: List[str] = []
        all_warnings: List[str] = []
        all_suggestions: List[str] = []

        # 逐个审查每个文件
        for diff_file in diff_files:
            try:
                # 构建单文件审查提示词
                change_type = "New" if diff_file.new_file else "Modified" if not diff_file.deleted_file else "Deleted"
                print(diff_file.diff)
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

                # 调用API
                response = asyncio.run(self._call_api(messages, response_format="json"))
                
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

            except Exception as e:
                logger.error(f"审查文件 {diff_file.get_display_path()} 失败: {e}")
                # 继续审查下一个文件
                continue

        # 构建整体摘要
        summary = self._build_overall_summary(
            mr=mr,
            diff_files=diff_files,
            total_issues=len(all_issues),
            total_warnings=len(all_warnings),
            total_suggestions=len(all_suggestions),
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

    def _build_detailed_file_review_prompt(
        self,
        file_path: str,
        change_type: str,
        diff_content: str,
        review_rules: List[str],
    ) -> str:
        """构建详细的文件审查提示词"""
        rules_text = "\\n".join(f"- {rule}" for rule in review_rules)

        # 使用字符串拼接避免 f-string 中的特殊字符问题
        prompt_parts = [
            "Please review the following code changes:",
            "",
            "## File Path",
            file_path,
            "",
            "## Change Type",
            change_type,
            "",
            "## Review Rules",
            rules_text,
            "",
            "## Line Number Rules (CRITICAL - YOU MUST GET THIS RIGHT)",
            "",
            "The diff hunk header format: @@ -<old_start>,<old_count> +<new_start>,<new_count> @@",
            "",
            "Line prefixes in diff:",
            "- Lines starting with ' ' (space): context/unchanged lines",
            "- Lines starting with '-': deleted lines (exist in OLD file)",
            "- Lines starting with '+': added lines (exist in NEW file)",
            "",
            "### HOW TO CALCULATE LINE NUMBERS:",
            "",
            "STEP 1: Parse the hunk header",
            "Example: @@ -83,16 +83,6 @@",
            "- OLD file starts at line 83, has 16 lines in this hunk",
            "- NEW file starts at line 83, has 6 lines in this hunk",
            "",
            "STEP 2: Count lines from the start number",
            "- For DELETED lines (-): count from the OLD start number",
            "- For ADDED lines (+): count from the NEW start number",
            "- Context lines DON'T affect the count",
            "",
            "STEP 3: Report the line number where the specific issue occurs",
            "",
            "### DETAILED EXAMPLES:",
            "",
            "Example 1 - Single line change:",
            '--- diff',
            "@@ -554,7 +554,7 @@",
            " ReactDOM.render(",
            "   <ReduxProvider>",
            "     <HashRouter>",
            "-      <ConfigProvider locale=enUS>",
            "+      <ConfigProvider locale=enUS errorBoundary={{}} key='111111112'>",
            "         <PreviewPage />",
            '---',
            "Analysis:",
            "- OLD file line 557: <ConfigProvider locale=enUS> (DELETED)",
            "- NEW file line 557: <ConfigProvider with errorBoundary> (ADDED)",
            "- Report issues with the new prop as line 557",
            "",
            "Example 2 - Multi-line deletion:",
            '--- diff',
            "@@ -83,16 +83,6 @@",
            "     config",
            "-      .plugin('icon-preview')",
            "-      .use(HtmlWebpackPlugin, [",
            "-        {{",
            "-          inject: false,",
            "-          templateParameters: {{}},",
            "-          template: require.resolve('./public/icon-preview.html'),",
            "-          filename: 'icon-preview.html',",
            "-        }},",
            "-      ]);",
            '---',
            "Analysis:",
            "- Line 83: config (context)",
            "- Line 84: .plugin('icon-preview') (DELETED) - Report plugin issues as 84",
            "- Line 85: .use(HtmlWebpackPlugin, [) (DELETED) - Report use issues as 85",
            "- Line 86: {{ (DELETED) - Report this line as 86",
            "",
            "Example 3 - Multiple additions:",
            '--- diff',
            "@@ -10,2 +10,4 @@",
            " function foo() {{",
            "-  return 1;",
            "+  const x = 1;",
            "+  return x;",
            " }}",
            '---',
            "Analysis:",
            "- Line 11: return 1; (DELETED from OLD)",
            "- Line 11: const x = 1; (ADDED to NEW) - Report issues as 11",
            "- Line 12: return x; (ADDED to NEW) - Report issues as 12",
            "",
            "### YOUR TASK:",
            "For EACH issue you find:",
            "1. Identify the SPECIFIC line that has the problem",
            "2. Determine if it's a + line (use NEW file number) or - line (use OLD file number)",
            "3. Count from the hunk header to get the exact line number",
            "4. NEVER use null unless you absolutely cannot determine the line",
            "",
            "## Diff Content to Review:",
            '--- diff',
            diff_content,
            '---',
            "",
            "## Output Format (JSON only):",
            "{",
            '  "reviews": [',
            '    {',
            '      "line_number": <exact line number>,',
            '      "severity": <"critical" | "warning" | "suggestion">,',
            '      "description": "<describe the issue and mention which line>"',
            '    }',
            '  ]',
            '}',
            "",
            "Review focus:",
            "1. Bugs and logic errors",
            "2. Security vulnerabilities",
            "3. Performance issues",
            "4. Code quality and maintainability",
            "5. Best practices violations",
            "",
            "REMEMBER: Accurate line numbers are CRITICAL!",
        ]

        return "\\n".join(prompt_parts)

    def _parse_detailed_file_review(self, response: str, file_path: str) -> List[Dict[str, Any]]:
        """解析详细的文件审查响应"""
        try:
            data = json.loads(response)
            reviews = data.get("reviews", [])
            print(reviews)
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
