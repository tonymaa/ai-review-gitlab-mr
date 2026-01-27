"""自定义异常类 - 用于提供详细的错误信息"""

class GitLabException(Exception):
    """GitLab 相关错误的基类"""

    def __init__(self, message: str, details: str = ""):
        self.message = message
        self.details = details
        super().__init__(self.message)

    def __str__(self):
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class GitLabConnectionError(GitLabException):
    """GitLab 连接错误"""
    pass


class GitLabAuthError(GitLabException):
    """GitLab 认证错误"""
    pass


class GitLabNotFoundError(GitLabException):
    """GitLab 资源未找到错误"""
    pass


class GitLabAPIError(GitLabException):
    """GitLab API 调用错误"""
    pass


class AIException(Exception):
    """AI 相关错误的基类"""

    def __init__(self, message: str, details: str = ""):
        self.message = message
        self.details = details
        super().__init__(self.message)

    def __str__(self):
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class AIConnectionError(AIException):
    """AI 服务连接错误"""
    pass


class AIAuthError(AIException):
    """AI 服务认证错误"""
    pass


class AIQuotaError(AIException):
    """AI 配额不足错误"""
    pass


class AIModelNotFoundError(AIException):
    """AI 模型未找到错误"""
    pass
