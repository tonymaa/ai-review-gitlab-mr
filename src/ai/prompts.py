"""AI审查提示词模板"""

# 系统提示词 - 定义AI的角色和行为
SYSTEM_PROMPT = """你是一个专业的代码审查助手，具有深厚的软件开发经验和最佳实践知识。

你的任务是：
1. 仔细审查提供的代码变更
2. 识别潜在的问题、安全漏洞和性能问题
3. 提供改进建议和最佳实践建议
4. 保持建议的具体性、可操作性和建设性

审查时请注意以下方面：
- 代码质量和可读性
- 潜在的bug和逻辑错误
- 安全漏洞（SQL注入、XSS、认证问题等）
- 性能问题和优化机会
- 错误处理和边界条件
- 代码重复和可维护性
- 命名规范和代码风格
- 缺失的注释或文档
- 测试覆盖度建议

请以友好、专业的语气提供反馈，重点关注真正需要改进的地方。
"""

# 用户提示词模板
REVIEW_PROMPT_TEMPLATE = """请审查以下代码变更：

## 分支信息
- 源分支: {source_branch}
- 目标分支: {target_branch}

## 变更描述
{description}

## 文件变更
{file_changes}

## 审查规则
{review_rules}

请提供结构化的审查反馈，包括：
1. 整体评估摘要
2. 按严重程度分类的问题列表（严重/警告/建议）
3. 针对每个问题的具体位置和改进建议
4. 整体评分（1-10分）

输出格式要求使用JSON，包含以下字段：
- summary: 整体评估摘要
- overall_score: 整体评分(1-10)
- issues: 严重问题列表，每项包含 file_path, line_number, description
- warnings: 警告列表，每项包含 file_path, line_number, description
- suggestions: 改进建议列表，每项包含 file_path, line_number, description
"""

# 单个文件审查模板
FILE_REVIEW_TEMPLATE = """请审查以下文件的代码变更：

## 文件路径
{file_path}

## 变更类型
{change_type}

## Diff内容
```diff
{diff_content}
```

请识别此文件中的问题和改进机会。输出JSON格式。"""

# 简化的审查模板（用于快速审查）
QUICK_REVIEW_TEMPLATE = """快速审查以下代码变更：

{diff_summary}

重点关注：
1. 明显的bug或逻辑错误
2. 安全问题
3. 严重的性能问题

输出JSON格式。"""


def build_review_prompt(
    title: str,
    description: str,
    source_branch: str,
    target_branch: str,
    file_changes: str,
    review_rules: list[str],
) -> str:
    """
    构建完整的审查提示词

    Args:
        title: MR标题
        description: MR描述
        source_branch: 源分支
        target_branch: 目标分支
        file_changes: 文件变更摘要
        review_rules: 审查规则列表

    Returns:
        完整的提示词字符串
    """
    rules_text = "\n".join(f"- {rule}" for rule in review_rules)

    return REVIEW_PROMPT_TEMPLATE.format(
        source_branch=source_branch,
        target_branch=target_branch,
        description=description or "无描述",
        file_changes=file_changes,
        review_rules=rules_text,
    )


def build_file_review_prompt(
    file_path: str,
    change_type: str,
    diff_content: str,
) -> str:
    """
    构建单文件审查提示词

    Args:
        file_path: 文件路径
        change_type: 变更类型（新增/修改/删除）
        diff_content: Diff内容

    Returns:
        提示词字符串
    """
    return FILE_REVIEW_TEMPLATE.format(
        file_path=file_path,
        change_type=change_type,
        diff_content=diff_content,
    )


def build_quick_review_prompt(diff_summary: str) -> str:
    """
    构建快速审查提示词

    Args:
        diff_summary: Diff摘要

    Returns:
        提示词字符串
    """
    return QUICK_REVIEW_TEMPLATE.format(diff_summary=diff_summary)
