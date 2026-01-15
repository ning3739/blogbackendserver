from sqlmodel import SQLModel
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from app.core.config.settings import settings

sqlalchemy_url = settings.database.DATABASE_URL

# Convert async MySQL URL to sync for Alembic
if sqlalchemy_url.startswith("mysql+aiomysql://"):
    sqlalchemy_url = sqlalchemy_url.replace("mysql+aiomysql://", "mysql+pymysql://")
elif sqlalchemy_url.startswith("mysql://"):
    # If it's a generic mysql:// URL, explicitly use pymysql
    sqlalchemy_url = sqlalchemy_url.replace("mysql://", "mysql+pymysql://")

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# 覆盖 alembic.ini 中的 sqlalchemy.url
config.set_main_option("sqlalchemy.url", sqlalchemy_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support

# 导入所有模型以确保它们被注册到 SQLModel.metadata
from app.models.user_model import User  # noqa: F401
from app.models.media_model import Media  # noqa: F401
from app.models.seo_model import Seo  # noqa: F401
from app.models.tag_model import Tag  # noqa: F401
from app.models.payment_model import Tax, PaymentRecord  # noqa: F401
from app.models.section_model import Section  # noqa: F401
from app.models.board_model import Board, BoardComment  # noqa: F401
from app.models.friend_model import Friend, FriendList  # noqa: F401
from app.models.subscriber_model import Subscriber  # noqa: F401
from app.models.blog_model import Blog, BlogTag, BlogComment, BlogStats, BlogStatus, BlogSummary, BlogTTS, SavedBlog  # noqa: F401
from app.models.project_model import Project, ProjectAttachment, ProjectMonetization  # noqa: F401
from app.models.auth_model import RefreshToken, Code, Social_Account  # noqa: F401

target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
