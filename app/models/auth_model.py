from enum import IntEnum
from datetime import datetime
from typing import Optional
from sqlalchemy import text, ForeignKey
from sqlalchemy.dialects.mysql import TIMESTAMP
from sqlmodel import (
    Column,
    Field,
    Index,
    SQLModel,
    desc,
)


class CodeType(IntEnum):
    verified = 1
    reset = 2


class SocialProvider(IntEnum):
    google = 1
    github = 2


class RefreshToken(SQLModel, table=True):
    """用户刷新令牌表 - 仅存储 refresh token"""

    __tablename__ = "refresh_tokens"

    __table_args__ = (
        # 单列索引
        Index("idx_refresh_tokens_user_id", "user_id"),
        Index("idx_refresh_tokens_is_active", "is_active"),
        Index("idx_refresh_tokens_jti", "jti"),
        Index("idx_refresh_tokens_expired_at", "expired_at"),
        # 复合索引 - 用于高效查询
        Index(
            "idx_refresh_tokens_get_user_tokens", "user_id", "expired_at", "is_active"
        ),  # auth_crud.py: _get_user_tokens
        Index(
            "idx_refresh_tokens_revoke_user_tokens", "user_id", "is_active"
        ),  # auth_crud.py: _revoke_user_tokens
        Index(
            "idx_refresh_tokens_generate_access_token",
            "user_id",
            "jti",
            "is_active",
            "expired_at",
        ),  # auth_crud.py: generate_access_token
        # 排序索引
        Index("idx_refresh_tokens_created_at_desc", desc("created_at")),
        Index("idx_refresh_tokens_expired_at_desc", desc("expired_at")),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    jti: str = Field(nullable=False, max_length=64, unique=True)
    token: str = Field(nullable=False, max_length=1024)
    is_active: bool = Field(default=True, nullable=True)
    created_at: datetime = Field(
        nullable=False,
        sa_type=TIMESTAMP,
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")},
    )
    expired_at: datetime = Field(
        nullable=False,
        sa_type=TIMESTAMP,
    )

    def __repr__(self):
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, is_active={self.is_active})>"


class Code(SQLModel, table=True):
    """验证码表 - 存储邮箱验证码和重置密码码"""

    __tablename__ = "codes"

    __table_args__ = (
        # 单列索引
        Index("idx_codes_user_id", "user_id"),
        Index("idx_codes_type", "type"),
        Index("idx_codes_is_used", "is_used"),
        # 复合索引
        Index(
            "idx_codes_get_valid_code", "user_id", "type", "expires_at", "is_used"
        ),  # auth_crud.py: _get_valid_code
        Index(
            "idx_codes_validate_code",
            "user_id",
            "code",
            "type",
            "expires_at",
            "is_used",
        ),  # auth_crud.py: _validate_code
        # 排序索引
        Index("idx_codes_created_at_desc", desc("created_at")),
        Index("idx_codes_expires_at_desc", desc("expires_at")),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    type: CodeType = Field(nullable=False)
    code: str = Field(nullable=False, max_length=10, unique=True)  # 优化长度
    is_used: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(
        nullable=False,
        sa_type=TIMESTAMP,
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")},
    )
    expires_at: datetime = Field(
        nullable=False,
        sa_type=TIMESTAMP,
    )

    def __repr__(self):
        return f"<Code(id={self.id}, user_id={self.user_id}, type={self.type.name}, is_used={self.is_used})>"


class Social_Account(SQLModel, table=True):
    """社交账户表 - 存储用户的第三方登录账户信息"""

    __tablename__ = "social_accounts"

    __table_args__ = (
        # 单列索引
        Index("idx_social_accounts_user_id", "user_id"),
        Index("idx_social_accounts_provider", "provider"),
        Index("idx_social_accounts_provider_user_id", "provider_user_id"),
        # 复合索引
        Index(
            "idx_social_accounts_get_social_account",
            "user_id",
            "provider",
            "provider_user_id",
        ),  # auth_crud.py: get_social_account
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    provider: SocialProvider = Field(nullable=False)
    provider_user_id: str = Field(
        nullable=False, max_length=100, unique=True
    )  # 优化长度
    created_at: datetime = Field(
        nullable=False,
        sa_type=TIMESTAMP,
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")},
    )

    def __repr__(self):
        return f"<Social_Account(id={self.id}, user_id={self.user_id}, provider={self.provider.name}, provider_user_id={self.provider_user_id})>"
