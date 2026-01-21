"""AI Code Review Prompt Templates"""

# System Prompt - Define AI's role and behavior
SYSTEM_PROMPT = """You are a professional code review assistant with extensive software development experience and knowledge of best practices.

Your task is to:
1. Carefully review the provided code changes
2. Identify potential issues, security vulnerabilities, and performance problems
3. Provide improvement suggestions and best practice recommendations
4. Keep your feedback specific, actionable, and constructive

When reviewing, pay attention to:
- Code quality and readability
- Potential bugs and logic errors
- Security vulnerabilities (SQL injection, XSS, authentication issues, etc.)
- Performance issues and optimization opportunities
- Error handling and edge cases
- Code duplication and maintainability
- Naming conventions and code style
- Missing comments or documentation
- Test coverage recommendations

Please provide feedback in a friendly, professional tone, focusing on areas that truly need improvement.
"""

# User prompt template
REVIEW_PROMPT_TEMPLATE = """Please review the following code changes:

## Branch Information
- Source branch: {source_branch}
- Target branch: {target_branch}

## Change Description
{description}

## File Changes
{file_changes}

## Review Rules
{review_rules}

Please provide structured review feedback, including:
1. Overall assessment summary
2. Issues list categorized by severity (critical/warning/suggestion)
3. Specific location and improvement suggestions for each issue
4. Overall score (1-10)

Output format must be JSON with the following fields:
- summary: Overall assessment summary
- overall_score: Overall score (1-10)
- issues: Critical issues list, each containing file_path, line_number, description
- warnings: Warnings list, each containing file_path, line_number, description
- suggestions: Improvement suggestions list, each containing file_path, line_number, description
"""

# Single file review template
FILE_REVIEW_TEMPLATE = """Please review the code changes for the following file:

## File Path
{file_path}

## Change Type
{change_type}

## Diff Content
```diff
{diff_content}
```

Please identify issues and improvement opportunities in this file. Output in JSON format."""

# Simplified review template (for quick review)
QUICK_REVIEW_TEMPLATE = """Quick review of the following code changes:

{diff_summary}

Focus on:
1. Obvious bugs or logic errors
2. Security issues
3. Serious performance problems

Output in JSON format."""


def build_review_prompt(
    title: str,
    description: str,
    source_branch: str,
    target_branch: str,
    file_changes: str,
    review_rules: list[str],
) -> str:
    """
    Build complete review prompt

    Args:
        title: MR title
        description: MR description
        source_branch: Source branch
        target_branch: Target branch
        file_changes: File changes summary
        review_rules: Review rules list

    Returns:
        Complete prompt string
    """
    rules_text = "\n".join(f"- {rule}" for rule in review_rules)

    return REVIEW_PROMPT_TEMPLATE.format(
        source_branch=source_branch,
        target_branch=target_branch,
        description=description or "No description",
        file_changes=file_changes,
        review_rules=rules_text,
    )


def build_file_review_prompt(
    file_path: str,
    change_type: str,
    diff_content: str,
) -> str:
    """
    Build single file review prompt

    Args:
        file_path: File path
        change_type: Change type (new/modified/deleted)
        diff_content: Diff content

    Returns:
        Prompt string
    """
    return FILE_REVIEW_TEMPLATE.format(
        file_path=file_path,
        change_type=change_type,
        diff_content=diff_content,
    )


def build_quick_review_prompt(diff_summary: str) -> str:
    """
    Build quick review prompt

    Args:
        diff_summary: Diff summary

    Returns:
        Prompt string
    """
    return QUICK_REVIEW_TEMPLATE.format(diff_summary=diff_summary)
