"""数据库模块 - 使用SQLAlchemy进行本地数据存储"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Any

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
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from contextlib import contextmanager
from passlib.context import CryptContext

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

Base = declarative_base()

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

    def set_password(self, password: str):
        """设置密码（哈希存储）"""
        self.hashed_password = hash_password(password)

    def verify_password(self, password: str) -> bool:
        """验证密码"""
        return verify_password(password, self.hashed_password)


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

    def _create_tables(self):
        """创建数据库表"""
        Base.metadata.create_all(bind=self.engine)

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
