"""数据库模块 - 使用SQLAlchemy进行本地数据存储"""

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
from pathlib import Path
from typing import Optional, List, Any, Dict

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    Index,
    and_,
    tuple_,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from contextlib import contextmanager
from passlib.context import CryptContext

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

Base = declarative_base()

# 日志记录器
logger = logging.getLogger(__name__)

# 使用带时区的当前时间函数
def now_utc():
    """获取当前UTC时间"""
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    """哈希密码"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


class User(Base):
    """用户数据模型"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=now_utc)
    is_active = Column(Boolean, default=True)

    # 关联关系
    gitlab_config = relationship("GitLabConfig", back_populates="user", uselist=False, cascade="all, delete-orphan")
    ai_config = relationship("AIConfig", back_populates="user", uselist=False, cascade="all, delete-orphan")
    ai_providers = relationship("AIProvider", back_populates="user", cascade="all, delete-orphan")
    auto_review_config = relationship("AutoReviewConfig", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def set_password(self, password: str):
        """设置密码（哈希存储）"""
        self.hashed_password = hash_password(password)

    def verify_password(self, password: str) -> bool:
        """验证密码"""
        return verify_password(password, self.hashed_password)


class GitLabConfig(Base):
    """GitLab 配置模型"""

    __tablename__ = "gitlab_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    url = Column(String(500), nullable=False)
    token = Column(String(500), nullable=False)
    default_project_id = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)

    # 关联关系
    user = relationship("User", back_populates="gitlab_config")


class AIProvider(Base):
    """AI Provider 配置模型 - 支持多个 provider"""

    __tablename__ = "ai_providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)  # 用户自定义名称
    provider_type = Column(String(50), nullable=False)  # openai, ollama

    # OpenAI 配置
    openai_api_key = Column(String(500), nullable=True)
    openai_base_url = Column(String(500), nullable=True)
    openai_model = Column(String(100), nullable=False, default="gpt-4")
    openai_temperature = Column(Integer, nullable=False, default=30)  # 存储为整数 * 100
    openai_max_tokens = Column(Integer, nullable=False, default=4000)

    # Ollama 配置
    ollama_base_url = Column(String(500), nullable=False, default="http://localhost:11434")
    ollama_model = Column(String(100), nullable=False, default="codellama")

    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)

    # 关联关系
    user = relationship("User", back_populates="ai_providers")


class AIConfig(Base):
    """AI 配置模型 - 全局设置"""

    __tablename__ = "ai_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # 当前激活的 provider
    active_provider_id = Column(Integer, ForeignKey("ai_providers.id"), nullable=True)

    # 审查规则 (JSON 格式存储)
    review_rules = Column(Text, nullable=True)

    # AI 总结提示词
    summary_prompt = Column(Text, nullable=True)

    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)

    # 关联关系
    user = relationship("User", back_populates="ai_config")
    active_provider = relationship("AIProvider", foreign_keys=[active_provider_id])


class AutoReviewConfig(Base):
    """自动审查配置模型"""

    __tablename__ = "auto_review_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # 基础配置
    enabled = Column(Boolean, nullable=False, default=False)
    interval_seconds = Column(Integer, nullable=False, default=120)

    # 筛选条件（JSON格式存储）
    target_creators = Column(Text, nullable=True)  # JSON: ["creator1", "creator2"]
    target_projects = Column(Text, nullable=True)  # JSON: ["project1", "project2"]

    # 自动批准条件（JSON格式存储）
    auto_approve_keywords = Column(Text, nullable=True)  # JSON: ["keyword1", "keyword2"]
    auto_approve_mode = Column(String(20), nullable=False, default="always")  # always, keyword_only, never

    # 审查配置
    add_as_comment = Column(Boolean, nullable=False, default=True)  # 是否将总结添加为MR评论

    # 时间戳
    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)

    # 关联关系
    user = relationship("User", back_populates="auto_review_config")


class MergeRequest(Base):
    """Merge Request数据模型"""

    __tablename__ = "merge_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # GitLab中的MR信息
    gitlab_mr_id = Column(Integer, nullable=False, index=True)
    gitlab_project_id = Column(Integer, nullable=False, index=True)
    iid = Column(Integer, nullable=False)  # 项目内的MR编号
    title = Column(String(500), nullable=False)
    description = Column(Text)
    state = Column(String(50), nullable=False)  # opened, closed, merged
    author_name = Column(String(200))
    author_username = Column(String(200))
    source_branch = Column(String(200))
    target_branch = Column(String(200))
    web_url = Column(String(500))

    # 时间信息
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    merged_at = Column(DateTime, nullable=True)

    # 本地信息
    cached_at = Column(DateTime, default=now_utc)
    is_reviewed = Column(Boolean, default=False)

    # 关联关系
    diff_files = relationship("DiffFile", back_populates="merge_request", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="merge_request", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_project_mr", "gitlab_project_id", "gitlab_mr_id"),
        Index("idx_state", "state"),
    )


class DiffFile(Base):
    """Diff文件数据模型"""

    __tablename__ = "diff_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mr_id = Column(Integer, ForeignKey("merge_requests.id"), nullable=False)

    # 文件信息
    old_path = Column(String(500))
    new_path = Column(String(500))
    file_hash = Column(String(100))
    is_new_file = Column(Boolean, default=False)
    is_deleted_file = Column(Boolean, default=False)
    is_renamed_file = Column(Boolean, default=False)

    # Diff内容
    diff = Column(Text, nullable=False)
    patch = Column(Text)

    # 统计信息
    additions = Column(Integer, default=0)
    deletions = Column(Integer, default=0)

    # 关联关系
    merge_request = relationship("MergeRequest", back_populates="diff_files")
    line_comments = relationship("LineComment", back_populates="diff_file", cascade="all, delete-orphan")


class LineComment(Base):
    """行评论数据模型"""

    __tablename__ = "line_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    diff_file_id = Column(Integer, ForeignKey("diff_files.id"), nullable=False)

    # 位置信息
    old_line = Column(Integer, nullable=True)
    new_line = Column(Integer, nullable=True)
    line_type = Column(String(20))  # addition, deletion, context

    # 评论内容
    content = Column(Text, nullable=False)
    comment_type = Column(String(50))  # ai_review, user_comment, etc.

    # 元数据
    extra_data = Column(Text)  # JSON格式的额外信息
    created_at = Column(DateTime, default=now_utc)

    # 关联关系
    diff_file = relationship("DiffFile", back_populates="line_comments")


class Review(Base):
    """审查记录数据模型"""

    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mr_id = Column(Integer, ForeignKey("merge_requests.id"), nullable=False)

    # 审查信息
    review_type = Column(String(50), nullable=False)  # ai_review, manual_review
    provider = Column(String(50))  # openai, ollama, etc.
    model = Column(String(100))

    # 审查结果
    summary = Column(Text)
    overall_score = Column(Integer)  # 1-10分
    issues_count = Column(Integer, default=0)
    suggestions_count = Column(Integer, default=0)

    # 详细结果 (JSON格式)
    details = Column(Text)

    # 时间信息
    created_at = Column(DateTime, default=now_utc)

    # 关联关系
    merge_request = relationship("MergeRequest", back_populates="reviews")


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, db_path: str):
        """
        初始化数据库管理器

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        # 确保数据库目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 创建数据库引擎
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            echo=False,
            connect_args={"check_same_thread": False},
        )

        # 创建会话工厂
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        # 创建表
        self._create_tables()

        # 运行迁移
        self._run_migrations()

    def _create_tables(self):
        """创建数据库表"""
        Base.metadata.create_all(bind=self.engine)

    def _run_migrations(self):
        """运行数据库迁移"""
        from sqlalchemy import inspect, text
        inspector = inspect(self.engine)

        # 检查并创建 ai_providers 表（如果不存在）
        if 'ai_providers' not in inspector.get_table_names():
            try:
                AIProvider.__table__.create(self.engine, checkfirst=True)
                logger.info("已创建 ai_providers 表")
            except Exception as e:
                logger.warning(f"创建 ai_providers 表失败: {e}")

        # 检查 ai_configs 表是否存在 summary_prompt 列
        if 'ai_configs' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('ai_configs')]
            if 'summary_prompt' not in columns:
                try:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE ai_configs ADD COLUMN summary_prompt TEXT"))
                        conn.commit()
                    logger.info("已添加 summary_prompt 列到 ai_configs 表")
                except Exception as e:
                    logger.warning(f"添加 summary_prompt 列失败: {e}")

            # 添加 active_provider_id 列
            if 'active_provider_id' not in columns:
                try:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE ai_configs ADD COLUMN active_provider_id INTEGER REFERENCES ai_providers(id)"))
                        conn.commit()
                    logger.info("已添加 active_provider_id 列到 ai_configs 表")
                except Exception as e:
                    logger.warning(f"添加 active_provider_id 列失败: {e}")

            # 迁移旧数据：将现有的 provider 配置迁移到 ai_providers 表
            self._migrate_legacy_ai_config()

        # 检查并创建 auto_review_configs 表（如果不存在）
        if 'auto_review_configs' not in inspector.get_table_names():
            try:
                AutoReviewConfig.__table__.create(self.engine, checkfirst=True)
                logger.info("已创建 auto_review_configs 表")
            except Exception as e:
                logger.warning(f"创建 auto_review_configs 表失败: {e}")
        else:
            # 删除旧的 review_type 列（如果存在）
            ar_columns = [col['name'] for col in inspector.get_columns('auto_review_configs')]
            if 'review_type' in ar_columns:
                try:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE auto_review_configs DROP COLUMN review_type"))
                        conn.commit()
                    logger.info("已删除 auto_review_configs 表的 review_type 列")
                except Exception as e:
                    logger.warning(f"删除 review_type 列失败: {e}")

    def _migrate_legacy_ai_config(self):
        """迁移旧的 AI 配置到新的 ai_providers 表"""
        from sqlalchemy import inspect, text
        inspector = inspect(self.engine)

        # 检查 ai_configs 表是否还有旧的列
        if 'ai_configs' not in inspector.get_table_names():
            return

        columns = [col['name'] for col in inspector.get_columns('ai_configs')]
        if 'provider' not in columns:
            return  # 已经迁移完成

        try:
            with self.engine.connect() as conn:
                # 查找需要迁移的配置
                result = conn.execute(text("""
                    SELECT id, user_id, provider,
                           openai_api_key, openai_base_url, openai_model, openai_temperature, openai_max_tokens,
                           ollama_base_url, ollama_model
                    FROM ai_configs
                    WHERE provider IS NOT NULL AND provider != ''
                """))

                for row in result:
                    ai_config_id, user_id, provider_type = row[0], row[1], row[2]
                    openai_api_key = row[3]
                    openai_base_url = row[4]
                    openai_model = row[5] or 'gpt-4'
                    openai_temperature = row[6] or 30
                    openai_max_tokens = row[7] or 4000
                    ollama_base_url = row[8] or 'http://localhost:11434'
                    ollama_model = row[9] or 'codellama'

                    # 检查是否已经迁移过
                    existing = conn.execute(text("""
                        SELECT id FROM ai_providers WHERE user_id = :user_id
                    """), {"user_id": user_id}).fetchone()

                    if existing:
                        continue

                    # 创建 AIProvider 记录
                    provider_name = f"Default {provider_type.capitalize()}"

                    conn.execute(text("""
                        INSERT INTO ai_providers (user_id, name, provider_type,
                            openai_api_key, openai_base_url, openai_model, openai_temperature, openai_max_tokens,
                            ollama_base_url, ollama_model, created_at, updated_at)
                        VALUES (:user_id, :name, :provider_type,
                            :openai_api_key, :openai_base_url, :openai_model, :openai_temperature, :openai_max_tokens,
                            :ollama_base_url, :ollama_model, datetime('now'), datetime('now'))
                    """), {
                        "user_id": user_id,
                        "name": provider_name,
                        "provider_type": provider_type,
                        "openai_api_key": openai_api_key,
                        "openai_base_url": openai_base_url,
                        "openai_model": openai_model,
                        "openai_temperature": openai_temperature,
                        "openai_max_tokens": openai_max_tokens,
                        "ollama_base_url": ollama_base_url,
                        "ollama_model": ollama_model,
                    })

                    # 获取新创建的 provider id
                    provider_row = conn.execute(text("""
                        SELECT id FROM ai_providers WHERE user_id = :user_id ORDER BY id DESC LIMIT 1
                    """), {"user_id": user_id}).fetchone()

                    if provider_row:
                        # 更新 ai_configs 的 active_provider_id
                        conn.execute(text("""
                            UPDATE ai_configs SET active_provider_id = :provider_id WHERE id = :ai_config_id
                        """), {"provider_id": provider_row[0], "ai_config_id": ai_config_id})

                conn.commit()
                logger.info("已迁移旧的 AI 配置到 ai_providers 表")

                # 删除旧列（SQLite 3.35.0+ 支持）
                old_columns = ['provider', 'openai_api_key', 'openai_base_url', 'openai_model',
                               'openai_temperature', 'openai_max_tokens', 'ollama_base_url', 'ollama_model']
                for col in old_columns:
                    try:
                        conn.execute(text(f"ALTER TABLE ai_configs DROP COLUMN {col}"))
                        logger.info(f"已删除 ai_configs 表的 {col} 列")
                    except Exception as col_err:
                        logger.debug(f"删除列 {col} 失败（可能不支持或列不存在）: {col_err}")
                conn.commit()
        except Exception as e:
            logger.warning(f"迁移 AI 配置失败: {e}")

    @contextmanager
    def get_session(self) -> Session:
        """获取数据库会话（上下文管理器）"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # MergeRequest 相关操作
    def save_merge_request(self, mr_data: dict) -> MergeRequest:
        """保存或更新Merge Request"""
        with self.get_session() as session:
            # 查找是否已存在
            existing = (
                session.query(MergeRequest)
                .filter(
                    MergeRequest.gitlab_project_id == mr_data["gitlab_project_id"],
                    MergeRequest.gitlab_mr_id == mr_data["gitlab_mr_id"],
                )
                .first()
            )

            if existing:
                # 更新现有记录
                for key, value in mr_data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                existing.cached_at = datetime.now()
                session.merge(existing)
                return existing
            else:
                # 创建新记录
                mr = MergeRequest(**mr_data)
                session.add(mr)
                session.flush()
                session.refresh(mr)
                return mr

    def get_merge_request(
        self, project_id: int, mr_id: int
    ) -> Optional[MergeRequest]:
        """获取指定的Merge Request"""
        with self.get_session() as session:
            return (
                session.query(MergeRequest)
                .filter(
                    MergeRequest.gitlab_project_id == project_id,
                    MergeRequest.gitlab_mr_id == mr_id,
                )
                .first()
            )

    def list_merge_requests(
        self,
        project_id: Optional[int] = None,
        state: Optional[str] = None,
        limit: int = 100,
    ) -> List[MergeRequest]:
        """列出Merge Requests"""
        with self.get_session() as session:
            query = session.query(MergeRequest)

            if project_id:
                query = query.filter(MergeRequest.gitlab_project_id == project_id)
            if state:
                query = query.filter(MergeRequest.state == state)

            return query.order_by(MergeRequest.updated_at.desc()).limit(limit).all()

    # DiffFile 相关操作
    def save_diff_file(self, mr_id: int, diff_data: dict) -> DiffFile:
        """保存或更新Diff文件"""
        with self.get_session() as session:
            # 查找MR
            mr = (
                session.query(MergeRequest)
                .filter(MergeRequest.id == mr_id)
                .first()
            )

            if not mr:
                raise ValueError(f"Merge Request with id {mr_id} not found")

            # 查找是否已存在相同路径的diff
            existing = (
                session.query(DiffFile)
                .filter(
                    DiffFile.mr_id == mr_id,
                    DiffFile.new_path == diff_data.get("new_path", ""),
                )
                .first()
            )

            if existing:
                for key, value in diff_data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                session.merge(existing)
                return existing
            else:
                diff_file = DiffFile(mr_id=mr_id, **diff_data)
                session.add(diff_file)
                session.flush()
                session.refresh(diff_file)
                return diff_file

    def get_diff_files(self, mr_id: int) -> List[DiffFile]:
        """获取MR的所有Diff文件"""
        with self.get_session() as session:
            return (
                session.query(DiffFile)
                .filter(DiffFile.mr_id == mr_id)
                .order_by(DiffFile.new_path)
                .all()
            )

    # LineComment 相关操作
    def save_line_comment(
        self, diff_file_id: int, comment_data: dict
    ) -> LineComment:
        """保存行评论"""
        with self.get_session() as session:
            comment = LineComment(diff_file_id=diff_file_id, **comment_data)
            session.add(comment)
            session.flush()
            session.refresh(comment)
            return comment

    def get_line_comments(self, diff_file_id: int) -> List[LineComment]:
        """获取Diff文件的所有行评论"""
        with self.get_session() as session:
            return (
                session.query(LineComment)
                .filter(LineComment.diff_file_id == diff_file_id)
                .order_by(LineComment.old_line, LineComment.new_line)
                .all()
            )

    # Review 相关操作
    def save_review(self, mr_id: int, review_data: dict) -> Review:
        """保存审查记录"""
        with self.get_session() as session:
            # 查找MR
            mr = (
                session.query(MergeRequest)
                .filter(MergeRequest.id == mr_id)
                .first()
            )

            if not mr:
                raise ValueError(f"Merge Request with id {mr_id} not found")

            review = Review(mr_id=mr_id, **review_data)
            session.add(review)
            session.flush()
            session.refresh(review)

            # 标记MR已审查
            mr.is_reviewed = True
            session.merge(mr)

            return review

    def get_reviews(self, mr_id: int) -> List[Review]:
        """获取MR的所有审查记录"""
        with self.get_session() as session:
            return (
                session.query(Review)
                .filter(Review.mr_id == mr_id)
                .order_by(Review.created_at.desc())
                .all()
            )

    # 清理操作
    def clear_old_cache(self, days: int = 30) -> int:
        """清理旧的缓存数据"""
        from datetime import timedelta

        cutoff_date = now_utc() - timedelta(days=days)

        with self.get_session() as session:
            deleted = (
                session.query(MergeRequest)
                .filter(MergeRequest.cached_at < cutoff_date)
                .delete()
            )
            return deleted

    # User 相关操作
    def create_user(self, username: str, password: str) -> dict:
        """创建新用户，返回用户数据字典"""
        with self.get_session() as session:
            # 检查用户名是否已存在
            existing = (
                session.query(User)
                .filter(User.username == username)
                .first()
            )
            if existing:
                raise ValueError(f"用户名 '{username}' 已存在")

            # 创建新用户
            user = User(username=username)
            user.set_password(password)
            session.add(user)
            session.flush()

            # 获取用户ID后重新查询，确保返回的对象是新的且包含所有字段
            user_id = user.id

        # 在会话外重新查询用户数据，避免返回已分离的对象
        return self.get_user_data(user_id)

    def get_user_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        with self.get_session() as session:
            return (
                session.query(User)
                .filter(User.username == username)
                .first()
            )

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """根据ID获取用户"""
        with self.get_session() as session:
            return session.query(User).filter(User.id == user_id).first()

    def verify_user(self, username: str, password: str) -> Optional[dict]:
        """验证用户凭据，返回用户数据"""
        with self.get_session() as session:
            user = session.query(User).filter(User.username == username).first()
            if user and user.verify_password(password):
                # 在会话内访问所有需要的属性
                return {
                    "id": user.id,
                    "username": user.username,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "is_active": user.is_active,
                }
        return None

    def list_users(self, limit: int = 100) -> List[User]:
        """列出所有用户"""
        with self.get_session() as session:
            return session.query(User).order_by(User.created_at.desc()).limit(limit).all()

    def get_user_data(self, user_id: int) -> Optional[dict]:
        """获取用户数据（字典格式）"""
        with self.get_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if user is None:
                return None
            # 访问所有需要的属性，确保在会话内加载
            return {
                "id": user.id,
                "username": user.username,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "is_active": user.is_active,
            }

    # ==================== GitLab 配置相关操作 ====================

    def upsert_gitlab_config(
        self,
        user_id: int,
        url: str,
        token: str,
        default_project_id: Optional[str] = None,
    ) -> GitLabConfig:
        """创建或更新 GitLab 配置"""
        with self.get_session() as session:
            # 查找是否已存在
            existing = (
                session.query(GitLabConfig)
                .filter(GitLabConfig.user_id == user_id)
                .first()
            )

            if existing:
                # 更新现有配置
                existing.url = url
                existing.token = token
                existing.default_project_id = default_project_id
                existing.updated_at = now_utc()
                session.merge(existing)
                session.flush()
                session.refresh(existing)
                return existing
            else:
                # 创建新配置
                config = GitLabConfig(
                    user_id=user_id,
                    url=url,
                    token=token,
                    default_project_id=default_project_id,
                )
                session.add(config)
                session.flush()
                session.refresh(config)
                return config

    def get_gitlab_config(self, user_id: int) -> Optional[dict]:
        """获取用户的 GitLab 配置（字典格式）"""
        with self.get_session() as session:
            config = (
                session.query(GitLabConfig)
                .filter(GitLabConfig.user_id == user_id)
                .first()
            )
            if config is None:
                return None
            return {
                "id": config.id,
                "user_id": config.user_id,
                "url": config.url,
                "token": config.token,
                "default_project_id": config.default_project_id,
                "created_at": config.created_at.isoformat() if config.created_at else None,
                "updated_at": config.updated_at.isoformat() if config.updated_at else None,
            }

    def delete_gitlab_config(self, user_id: int) -> bool:
        """删除用户的 GitLab 配置"""
        with self.get_session() as session:
            deleted = (
                session.query(GitLabConfig)
                .filter(GitLabConfig.user_id == user_id)
                .delete()
            )
            return deleted > 0

    # ==================== AI 配置相关操作 ====================

    def upsert_ai_config(
        self,
        user_id: int,
        active_provider_id: Optional[int] = None,
        review_rules: Optional[List[str]] = None,
        summary_prompt: Optional[str] = None,
    ) -> AIConfig:
        """创建或更新 AI 全局配置（不含 provider 配置）"""
        with self.get_session() as session:
            # 查找是否已存在
            existing = (
                session.query(AIConfig)
                .filter(AIConfig.user_id == user_id)
                .first()
            )

            # 将审查规则转换为 JSON
            rules_json = json.dumps(review_rules) if review_rules else None

            if existing:
                # 更新现有配置
                if active_provider_id is not None:
                    existing.active_provider_id = active_provider_id
                existing.review_rules = rules_json
                if summary_prompt is not None:
                    existing.summary_prompt = summary_prompt
                existing.updated_at = now_utc()
                session.merge(existing)
                session.flush()
                session.refresh(existing)
                return existing
            else:
                # 创建新配置
                config = AIConfig(
                    user_id=user_id,
                    active_provider_id=active_provider_id,
                    review_rules=rules_json,
                    summary_prompt=summary_prompt,
                )
                session.add(config)
                session.flush()
                session.refresh(config)
                return config

    def get_ai_config(self, user_id: int) -> Optional[dict]:
        """获取用户的 AI 配置（字典格式）"""
        with self.get_session() as session:
            config = (
                session.query(AIConfig)
                .filter(AIConfig.user_id == user_id)
                .first()
            )
            if config is None:
                return None

            # 解析审查规则
            review_rules = None
            if config.review_rules:
                try:
                    review_rules = json.loads(config.review_rules)
                except:
                    review_rules = []

            return {
                "id": config.id,
                "user_id": config.user_id,
                "active_provider_id": config.active_provider_id,
                "review_rules": review_rules or [],
                "summary_prompt": config.summary_prompt,
                "created_at": config.created_at.isoformat() if config.created_at else None,
                "updated_at": config.updated_at.isoformat() if config.updated_at else None,
            }

    def delete_ai_config(self, user_id: int) -> bool:
        """删除用户的 AI 配置"""
        with self.get_session() as session:
            deleted = (
                session.query(AIConfig)
                .filter(AIConfig.user_id == user_id)
                .delete()
            )
            return deleted > 0

    # ==================== AI Provider 相关操作 ====================

    def create_ai_provider(
        self,
        user_id: int,
        name: str,
        provider_type: str,
        openai_api_key: Optional[str] = None,
        openai_base_url: Optional[str] = None,
        openai_model: str = "gpt-4",
        openai_temperature: float = 0.3,
        openai_max_tokens: int = 4000,
        ollama_base_url: str = "http://localhost:11434",
        ollama_model: str = "codellama",
    ) -> int:
        """创建新的 AI Provider，返回 provider ID"""
        with self.get_session() as session:
            # 将温度转换为整数存储（乘以100）
            temp_int = int(openai_temperature * 100)

            provider = AIProvider(
                user_id=user_id,
                name=name,
                provider_type=provider_type,
                openai_api_key=openai_api_key,
                openai_base_url=openai_base_url,
                openai_model=openai_model,
                openai_temperature=temp_int,
                openai_max_tokens=openai_max_tokens,
                ollama_base_url=ollama_base_url,
                ollama_model=ollama_model,
            )
            session.add(provider)
            session.flush()
            session.refresh(provider)
            # 在 session 内获取 ID
            provider_id = provider.id
            return provider_id

    def get_ai_provider(self, provider_id: int, user_id: int) -> Optional[dict]:
        """获取指定的 AI Provider"""
        with self.get_session() as session:
            provider = (
                session.query(AIProvider)
                .filter(AIProvider.id == provider_id, AIProvider.user_id == user_id)
                .first()
            )
            if provider is None:
                return None

            return {
                "id": provider.id,
                "user_id": provider.user_id,
                "name": provider.name,
                "provider_type": provider.provider_type,
                "openai_api_key": provider.openai_api_key,
                "openai_base_url": provider.openai_base_url,
                "openai_model": provider.openai_model,
                "openai_temperature": provider.openai_temperature / 100.0,
                "openai_max_tokens": provider.openai_max_tokens,
                "ollama_base_url": provider.ollama_base_url,
                "ollama_model": provider.ollama_model,
                "created_at": provider.created_at.isoformat() if provider.created_at else None,
                "updated_at": provider.updated_at.isoformat() if provider.updated_at else None,
            }

    def list_ai_providers(self, user_id: int) -> List[dict]:
        """获取用户的所有 AI Providers"""
        with self.get_session() as session:
            providers = (
                session.query(AIProvider)
                .filter(AIProvider.user_id == user_id)
                .order_by(AIProvider.created_at.asc())
                .all()
            )

            return [
                {
                    "id": p.id,
                    "user_id": p.user_id,
                    "name": p.name,
                    "provider_type": p.provider_type,
                    "openai_api_key": p.openai_api_key,
                    "openai_base_url": p.openai_base_url,
                    "openai_model": p.openai_model,
                    "openai_temperature": p.openai_temperature / 100.0,
                    "openai_max_tokens": p.openai_max_tokens,
                    "ollama_base_url": p.ollama_base_url,
                    "ollama_model": p.ollama_model,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                }
                for p in providers
            ]

    def update_ai_provider(
        self,
        provider_id: int,
        user_id: int,
        name: Optional[str] = None,
        provider_type: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        openai_base_url: Optional[str] = None,
        openai_model: Optional[str] = None,
        openai_temperature: Optional[float] = None,
        openai_max_tokens: Optional[int] = None,
        ollama_base_url: Optional[str] = None,
        ollama_model: Optional[str] = None,
    ) -> Optional[AIProvider]:
        """更新 AI Provider"""
        with self.get_session() as session:
            provider = (
                session.query(AIProvider)
                .filter(AIProvider.id == provider_id, AIProvider.user_id == user_id)
                .first()
            )
            if provider is None:
                return None

            if name is not None:
                provider.name = name
            if provider_type is not None:
                provider.provider_type = provider_type
            if openai_api_key is not None:
                provider.openai_api_key = openai_api_key
            if openai_base_url is not None:
                provider.openai_base_url = openai_base_url
            if openai_model is not None:
                provider.openai_model = openai_model
            if openai_temperature is not None:
                provider.openai_temperature = int(openai_temperature * 100)
            if openai_max_tokens is not None:
                provider.openai_max_tokens = openai_max_tokens
            if ollama_base_url is not None:
                provider.ollama_base_url = ollama_base_url
            if ollama_model is not None:
                provider.ollama_model = ollama_model

            provider.updated_at = now_utc()
            session.merge(provider)
            session.flush()
            session.refresh(provider)
            return provider

    def delete_ai_provider(self, provider_id: int, user_id: int) -> bool:
        """删除 AI Provider"""
        with self.get_session() as session:
            # 检查是否是当前激活的 provider
            ai_config = (
                session.query(AIConfig)
                .filter(AIConfig.user_id == user_id)
                .first()
            )
            if ai_config and ai_config.active_provider_id == provider_id:
                # 清除激活状态
                ai_config.active_provider_id = None
                session.merge(ai_config)

            deleted = (
                session.query(AIProvider)
                .filter(AIProvider.id == provider_id, AIProvider.user_id == user_id)
                .delete()
            )
            return deleted > 0

    def set_active_ai_provider(self, provider_id: int, user_id: int) -> bool:
        """设置激活的 AI Provider"""
        with self.get_session() as session:
            # 验证 provider 存在且属于该用户
            provider = (
                session.query(AIProvider)
                .filter(AIProvider.id == provider_id, AIProvider.user_id == user_id)
                .first()
            )
            if provider is None:
                return False

            # 获取或创建 AIConfig
            ai_config = (
                session.query(AIConfig)
                .filter(AIConfig.user_id == user_id)
                .first()
            )

            if ai_config:
                ai_config.active_provider_id = provider_id
                ai_config.updated_at = now_utc()
                session.merge(ai_config)
            else:
                ai_config = AIConfig(
                    user_id=user_id,
                    active_provider_id=provider_id,
                )
                session.add(ai_config)

            return True

    def get_active_ai_provider(self, user_id: int) -> Optional[dict]:
        """获取用户当前激活的 AI Provider"""
        with self.get_session() as session:
            # 获取 AIConfig
            ai_config = (
                session.query(AIConfig)
                .filter(AIConfig.user_id == user_id)
                .first()
            )

            if ai_config is None or ai_config.active_provider_id is None:
                return None

            # 获取激活的 provider
            provider = (
                session.query(AIProvider)
                .filter(AIProvider.id == ai_config.active_provider_id)
                .first()
            )

            if provider is None:
                return None

            return {
                "id": provider.id,
                "user_id": provider.user_id,
                "name": provider.name,
                "provider_type": provider.provider_type,
                "openai_api_key": provider.openai_api_key,
                "openai_base_url": provider.openai_base_url,
                "openai_model": provider.openai_model,
                "openai_temperature": provider.openai_temperature / 100.0,
                "openai_max_tokens": provider.openai_max_tokens,
                "ollama_base_url": provider.ollama_base_url,
                "ollama_model": provider.ollama_model,
                "created_at": provider.created_at.isoformat() if provider.created_at else None,
                "updated_at": provider.updated_at.isoformat() if provider.updated_at else None,
            }

    # ==================== Auto Review 配置相关操作 ====================

    def upsert_auto_review_config(
        self,
        user_id: int,
        enabled: bool = False,
        interval_seconds: int = 120,
        target_creators: Optional[List[str]] = None,
        target_projects: Optional[List[str]] = None,
        auto_approve_keywords: Optional[List[str]] = None,
        auto_approve_mode: str = "always",
        add_as_comment: bool = True,
    ) -> AutoReviewConfig:
        """创建或更新自动审查配置"""
        with self.get_session() as session:
            # 查找是否已存在
            existing = (
                session.query(AutoReviewConfig)
                .filter(AutoReviewConfig.user_id == user_id)
                .first()
            )

            # 将列表转换为 JSON
            creators_json = json.dumps(target_creators) if target_creators else None
            projects_json = json.dumps(target_projects) if target_projects else None
            keywords_json = json.dumps(auto_approve_keywords) if auto_approve_keywords else None

            if existing:
                # 更新现有配置
                existing.enabled = enabled
                existing.interval_seconds = interval_seconds
                existing.target_creators = creators_json
                existing.target_projects = projects_json
                existing.auto_approve_keywords = keywords_json
                existing.auto_approve_mode = auto_approve_mode
                existing.add_as_comment = add_as_comment
                existing.updated_at = now_utc()
                session.merge(existing)
                session.flush()
                session.refresh(existing)
                return existing
            else:
                # 创建新配置
                config = AutoReviewConfig(
                    user_id=user_id,
                    enabled=enabled,
                    interval_seconds=interval_seconds,
                    target_creators=creators_json,
                    target_projects=projects_json,
                    auto_approve_keywords=keywords_json,
                    auto_approve_mode=auto_approve_mode,
                    add_as_comment=add_as_comment,
                )
                session.add(config)
                session.flush()
                session.refresh(config)
                return config

    def get_auto_review_config(self, user_id: int) -> Optional[dict]:
        """获取用户的自动审查配置（字典格式）"""
        with self.get_session() as session:
            config = (
                session.query(AutoReviewConfig)
                .filter(AutoReviewConfig.user_id == user_id)
                .first()
            )
            if config is None:
                return None

            # 解析 JSON 字段
            target_creators = []
            if config.target_creators:
                try:
                    target_creators = json.loads(config.target_creators)
                except:
                    pass

            target_projects = []
            if config.target_projects:
                try:
                    target_projects = json.loads(config.target_projects)
                except:
                    pass

            auto_approve_keywords = []
            if config.auto_approve_keywords:
                try:
                    auto_approve_keywords = json.loads(config.auto_approve_keywords)
                except:
                    pass

            return {
                "id": config.id,
                "user_id": config.user_id,
                "enabled": config.enabled,
                "interval_seconds": config.interval_seconds,
                "target_creators": target_creators,
                "target_projects": target_projects,
                "auto_approve_keywords": auto_approve_keywords,
                "auto_approve_mode": config.auto_approve_mode,
                "add_as_comment": config.add_as_comment,
                "created_at": config.created_at.isoformat() if config.created_at else None,
                "updated_at": config.updated_at.isoformat() if config.updated_at else None,
            }

    def delete_auto_review_config(self, user_id: int) -> bool:
        """删除用户的自动审查配置"""
        with self.get_session() as session:
            deleted = (
                session.query(AutoReviewConfig)
                .filter(AutoReviewConfig.user_id == user_id)
                .delete()
            )
            return deleted > 0

    def list_enabled_auto_review_configs(self) -> List[dict]:
        """列出所有启用的自动审查配置（用于调度器启动）"""
        with self.get_session() as session:
            configs = (
                session.query(AutoReviewConfig)
                .filter(AutoReviewConfig.enabled == True)
                .all()
            )

            result = []
            for config in configs:
                result.append({
                    "user_id": config.user_id,
                    "interval_seconds": config.interval_seconds,
                })
            return result

    # ==================== Auto Review 处理记录相关操作 ====================

    def upsert_processed_mr(
        self,
        user_id: int,
        project_id: int,
        mr_iid: int,
        summary: Optional[str] = None,
        web_url: Optional[str] = None,
        title: Optional[str] = None,
    ) -> None:
        """记录已处理的 MR"""
        with self.get_session() as session:
            existing = (
                session.query(ProcessedMR)
                .filter(
                    ProcessedMR.user_id == user_id,
                    ProcessedMR.project_id == project_id,
                    ProcessedMR.mr_iid == mr_iid,
                )
                .first()
            )

            if existing:
                existing.processed_at = now_utc()
                existing.summary = summary
                existing.web_url = web_url
                existing.title = title
                session.merge(existing)
            else:
                record = ProcessedMR(
                    user_id=user_id,
                    project_id=project_id,
                    mr_iid=mr_iid,
                    summary=summary,
                    web_url=web_url,
                    title=title,
                )
                session.add(record)

    def is_mr_processed(self, user_id: int, project_id: int, mr_iid: int) -> bool:
        """检查 MR 是否已处理"""
        with self.get_session() as session:
            existing = (
                session.query(ProcessedMR)
                .filter(
                    ProcessedMR.user_id == user_id,
                    ProcessedMR.project_id == project_id,
                    ProcessedMR.mr_iid == mr_iid,
                )
                .first()
            )
            return existing is not None

    def get_processed_mr_count(self, user_id: int) -> int:
        """获取用户已处理的 MR 数量"""
        with self.get_session() as session:
            count = (
                session.query(ProcessedMR)
                .filter(ProcessedMR.user_id == user_id)
                .count()
            )
            return count

    def list_processed_mrs(self, user_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """获取用户已处理的 MR 列表"""
        with self.get_session() as session:
            processed_records = (
                session.query(ProcessedMR)
                .filter(ProcessedMR.user_id == user_id)
                .order_by(ProcessedMR.processed_at.desc())
                .limit(limit)
                .all()
            )

            logger.info(f"用户 {user_id} 有 {len(processed_records)} 条已处理 MR 记录")

            result = []
            for record in processed_records:
                result.append({
                    "id": record.id,
                    "project_id": record.project_id,
                    "mr_iid": record.mr_iid,
                    "summary": record.summary,
                    "processed_at": record.processed_at.isoformat() if record.processed_at else None,
                    "web_url": record.web_url,
                    "title": record.title,
                })
            return result

    def delete_processed_mr(self, user_id: int, record_id: int) -> bool:
        """删除指定的已处理 MR 记录"""
        with self.get_session() as session:
            deleted = (
                session.query(ProcessedMR)
                .filter(
                    ProcessedMR.id == record_id,
                    ProcessedMR.user_id == user_id,
                )
                .delete()
            )
            session.commit()
            return deleted > 0

    def clear_processed_mrs(self, user_id: int) -> int:
        """清空用户的所有已处理 MR 记录"""
        with self.get_session() as session:
            deleted = (
                session.query(ProcessedMR)
                .filter(ProcessedMR.user_id == user_id)
                .delete()
            )
            session.commit()
            return deleted


class ProcessedMR(Base):
    """已处理的 MR 记录"""
    __tablename__ = "processed_mrs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(Integer, nullable=False, index=True)
    mr_iid = Column(Integer, nullable=False, index=True)
    summary = Column(Text, nullable=True)  # AI 总结内容
    processed_at = Column(DateTime, default=now_utc, index=True)
    web_url = Column(String(500), nullable=True)  # MR 在 GitLab 中的链接
    title = Column(String(500), nullable=True)  # MR 标题

    __table_args__ = (
        Index("idx_user_project_mr", "user_id", "project_id", "mr_iid", unique=True),
    )
