from sqlmodel import insert
from sqlalchemy import text
from datetime import datetime
import asyncio
from app.models.user_model import RoleType, User
from app.models.media_model import Media, MediaType
from app.models.seo_model import Seo
from app.models.payment_model import Tax
from app.models.section_model import Section, SectionType
from app.models.board_model import Board
from app.models.friend_model import Friend
from app.models.subscriber_model import Subscriber
from app.core.config.settings import settings
from app.core.logger import logger_manager
from app.core.database.mysql import mysql_manager

logger = logger_manager.get_logger(__name__)

seo_data = [
    {
        "chinese_title": "开发笔记",
        "english_title": "Dev Notes",
        "chinese_description": "记录开发中的灵感与经验，分享代码实践与问题解决。",
        "english_description": "Notes on coding, ideas, and problem-solving in daily development.",
        "chinese_keywords": "开发笔记, 编程, 技术分享, 代码实践",
        "english_keywords": "Dev Notes, Programming, Coding, Tech Blog",
    },
    {
        "chinese_title": "日常记录",
        "english_title": "Journal",
        "chinese_description": "记录生活与思考的点滴，捕捉日常中的灵感与瞬间。",
        "english_description": "A daily journal of life, reflections, and small inspirations.",
        "chinese_keywords": "日常记录, 生活随笔, 思考, 灵感, 随想",
        "english_keywords": "Daily Journal, Life, Reflection, Inspiration, Thoughts",
    },
    {
        "chinese_title": "奇思妙想",
        "english_title": "Musings",
        "chinese_description": "记录灵感与想法的火花，探索创意与思考的边界。",
        "english_description": "A collection of creative thoughts, ideas, and personal musings.",
        "chinese_keywords": "奇思妙想, 灵感, 想法, 创意, 随想",
        "english_keywords": "Musings, Ideas, Inspiration, Creativity, Thoughts",
    },
    {
        "chinese_title": "项目",
        "english_title": "Projects",
        "chinese_description": "记录我参与的项目，分享项目背后的故事与经验。",
        "english_description": "A collection of projects I have participated in, sharing the stories and experiences behind them.",
        "chinese_keywords": "项目, 分享, 经验, 故事, 参与",
        "english_keywords": "Projects, Sharing, Experience, Story, Participation",
    },
    {
        "chinese_title": "留言",
        "english_title": "Forum",
        "chinese_description": "访客的留言与交流空间，分享想法，留下足迹。",
        "english_description": "A forum for messages, discussions, and sharing thoughts.",
        "chinese_keywords": "留言, 交流, 讨论, 留言板, 社区",
        "english_keywords": "Forum, Message Board, Discussion, Comments, Community",
    },
    {
        "chinese_title": "友链",
        "english_title": "Blogroll",
        "chinese_description": "收录值得一访的博客与网站，连接志同道合的创作者。",
        "english_description": "A blogroll of inspiring sites and creators worth visiting.",
        "chinese_keywords": "友链, 友情链接, 博客推荐, 创作者, 网站收藏",
        "english_keywords": "Blogroll, Links, Bloggers, Creators, Recommended Sites",
    }
]

user_data = [
    {
        "username": "ningli3739",
        "email": "ln729500172@gmail.com",
        "password_hash": "$argon2id$v=19$m=65536,t=2,p=1$GdPaj6Evf6hMCBvPnT58Vw$706Gp5JMyFGy0zXPtUPKhrNrXFUhGNFJGzTPfXIhGw8",
        "role": RoleType.admin,
        "ip_address": "218.107.132.66",
        "longitude": 116.397,
        "latitude": 39.9075,
        "city": "北京",
        "is_active": True,
        "is_verified": True,
        "created_at": datetime.now(),
        "updated_at": None,
    },
    {
        "username": "test123",
        "email": "ln729500172@outlook.com",
        "password_hash": "$argon2id$v=19$m=65536,t=2,p=1$GdPaj6Evf6hMCBvPnT58Vw$706Gp5JMyFGy0zXPtUPKhrNrXFUhGNFJGzTPfXIhGw8",
        "role": RoleType.user,
        "ip_address": "218.107.132.66",
        "longitude": 116.397,
        "latitude": 39.9075,
        "city": "北京",
        "is_active": True,
        "is_verified": True,
        "created_at": datetime.now(),
        "updated_at": None,
    }
]

media_data = [
    {
        "uuid": "123e4567-e89b-12d3-a456-426614174000",
        "user_id": 1,
        "type": MediaType.image,
        "is_avatar": True,
        "file_name": "avatar1.jpg",
        "original_filepath_url": f"{settings.domain.DOMAIN_URL}/static/image/default_avatar.jpg",
        "thumbnail_filepath_url": f"{settings.domain.DOMAIN_URL}/static/image/default_avatar.jpg",
        "watermark_filepath_url": f"{settings.domain.DOMAIN_URL}/static/image/default_avatar.jpg",
        "file_size": 1000,
    },
    {
        "uuid": "123e4567-e89b-12d3-a456-426614174001",
        "user_id": 2,
        "type": MediaType.image,
        "is_avatar": True,
        "file_name": "avatar2.jpg",
        "original_filepath_url": f"{settings.domain.DOMAIN_URL}/static/image/default_avatar.jpg",
        "thumbnail_filepath_url": f"{settings.domain.DOMAIN_URL}/static/image/default_avatar.jpg",
        "watermark_filepath_url": f"{settings.domain.DOMAIN_URL}/static/image/default_avatar.jpg",
        "file_size": 1000,
    }
]


tax_data = {
    "tax_name": "GST",
    "tax_rate": 0.15,
}

section_data = [
    {
        "seo_id": None,
        "type": SectionType.blog,
        "slug": "blog",
        "chinese_title": "博客",
        "english_title": "Blog",
        "chinese_description": None,
        "english_description": None,
        "is_active": True,
        "parent_id": None,

    },
    {
        "seo_id": 1,
        "type": SectionType.blog,
        "slug": "dev-notes",
        "chinese_title": "开发笔记",
        "english_title": "Dev Notes",
        "chinese_description": "记录开发中的灵感与经验，分享代码实践与问题解决。",
        "english_description": "Notes on coding, ideas, and problem-solving in daily development.",
        "is_active": True,
        "parent_id": 1,

    },
    {
        "seo_id": 2,
        "type": SectionType.blog,
        "slug": "journal",
        "chinese_title": "日常记录",
        "english_title": "Journal",
        "chinese_description": "记录生活与思考的点滴，捕捉日常中的灵感与瞬间。",
        "english_description": "A daily journal of life, reflections, and small inspirations.",
        "is_active": True,
        "parent_id": 1,

    },
    {
        "seo_id": 3,
        "type": SectionType.blog,
        "slug": "musings",
        "chinese_title": "奇思妙想",
        "english_title": "Musings",
        "chinese_description": "记录灵感与想法的火花，探索创意与思考的边界。",
        "english_description": "A collection of creative thoughts, ideas, and personal musings.",
        "is_active": True,
        "parent_id": 1,
    },
    {
        "seo_id": 4,
        "type": SectionType.project,
        "slug": "projects",
        "chinese_title": "项目",
        "english_title": "Projects",
        "chinese_description": "记录我参与的项目，分享项目背后的故事与经验。",
        "english_description": "A collection of projects I have participated in, sharing the stories and experiences behind them.",
        "is_active": True,
        "parent_id": None,
    },
    {
        "seo_id": 5,
        "type": SectionType.board,
        "slug": "forum",
        "chinese_title": "留言",
        "english_title": "Forum",
        "chinese_description": "访客的留言与交流空间，分享想法，留下足迹。",
        "english_description": "A forum for messages, discussions, and sharing thoughts.",
        "is_active": True,
        "parent_id": None,
    },
    {
        "seo_id": 6,
        "type": SectionType.friend,
        "slug": "blogroll",
        "chinese_title": "友链",
        "english_title": "Blogroll",
        "chinese_description": "收录值得一访的博客与网站，连接志同道合的创作者。",
        "english_description": "A blogroll of inspiring sites and creators worth visiting.",
        "is_active": True,
        "parent_id": None,
    }
]

board_data = [
    {
        "section_id": 6,
        "chinese_title": "留言",
        "english_title": "Forum",
        "chinese_description": "访客的留言与交流空间，分享想法，留下足迹。",
        "english_description": "A forum for messages, discussions, and sharing thoughts.",
    }
]

friend_data = [
    {
        "section_id": 7,
        "chinese_title": "友链",
        "english_title": "Blogroll",
        "chinese_description": "收录值得一访的博客与网站，连接志同道合的创作者。",
        "english_description": "A blogroll of inspiring sites and creators worth visiting.",
    }
]

subscriber_data = [
    {
        "email": "ln729500172@gmail.com",
    }
]


def check_table_empty(table_name: str, db) -> tuple[bool, int]:
    """
    检查单个表是否为空

    参数:
        table_name: 表名
        db: 数据库连接

    返回:
        (is_empty, count): (是否为空, 记录数)
        - is_empty=True: 表为空或不存在
        - is_empty=False: 表有数据
        - count: 表中的记录数（如果表不存在则为-1）
    """
    try:
        result = db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        count = result.scalar()
        return (count == 0, count)
    except Exception as e:
        logger.warning(
            f"Table '{table_name}' does not exist or error checking: {e}")
        return (True, -1)  # 表不存在视为空，但不插入数据


async def check_data_exists() -> bool:
    """
    检查数据库中是否已有初始数据

    主要检查关键表（users）是否有数据，因为users表是初始数据的核心。
    如果users表有数据，说明初始数据很可能已经插入。

    返回:
    - True: 数据已存在（users表有数据，或表不存在）
    - False: 数据不存在（users表为空且表存在）
    """
    # 关键表：users表是初始数据的核心标识
    key_table = "users"

    # 其他需要检查的表（用于完整性检查）
    other_tables = [
        "media",
        "seo",
        "taxes",
        "sections",
        "boards",
        "friends",
        "subscribers"
    ]

    try:
        db = mysql_manager.get_sync_db()
        try:
            # 首先检查关键表 users
            try:
                result = db.execute(text(f"SELECT COUNT(*) FROM {key_table}"))
                count = result.scalar()

                if count > 0:
                    logger.info(
                        f"Key table '{key_table}' has {count} records, initial data already exists")
                    return True

                logger.info(
                    f"Key table '{key_table}' is empty, checking other tables...")
            except Exception as e:
                # 如果关键表不存在，说明数据库可能未迁移
                logger.error(
                    f"Key table '{key_table}' does not exist. "
                    f"Please run database migrations first. Error: {e}")
                raise Exception(
                    f"Database table '{key_table}' does not exist. "
                    "Please run database migrations before inserting initial data.")

            # 检查其他表是否存在（但不阻止插入，只用于日志记录）
            missing_tables = []
            for table in other_tables:
                try:
                    result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    if count > 0:
                        logger.info(
                            f"Table '{table}' has {count} records (non-blocking)")
                except Exception as e:
                    missing_tables.append(table)
                    logger.warning(
                        f"Table '{table}' does not exist or error checking: {e}")

            if missing_tables:
                logger.warning(
                    f"Some tables are missing: {missing_tables}. "
                    "This may indicate incomplete database migration.")

            # 关键表为空，允许插入
            logger.info("Key table is empty, ready to insert initial data")
            return False

        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error checking data: {e}")
        # 如果是明确的错误（如表不存在），直接抛出
        if "does not exist" in str(e) or "migrations" in str(e).lower():
            raise
        # 其他错误，为了安全起见，假设数据已存在
        return True


async def insert_initial_data():
    """插入初始数据 - 按表检查，只插入空表的数据"""
    # Initialize database connection first
    await mysql_manager.initialize()
    db = mysql_manager.get_sync_db()

    try:
        inserted_tables = []
        skipped_tables = []

        # 插入 User 数据
        is_empty, count = check_table_empty("users", db)
        if is_empty and count != -1:  # 表存在且为空
            for user in user_data:
                db.execute(insert(User).values(user))
            db.commit()
            db.flush()
            inserted_tables.append("users")
            logger.info("✅ Inserted User data")
        elif count == -1:
            logger.warning(
                "⏭️  Table 'users' does not exist, skipping User data")
            skipped_tables.append("users (table not found)")
        else:
            logger.info(
                f"⏭️  Table 'users' has {count} records, skipping User data")
            skipped_tables.append(f"users ({count} records)")

        # 插入 Media 数据
        is_empty, count = check_table_empty("media", db)
        if is_empty and count != -1:
            for media in media_data:
                db.execute(insert(Media).values(media))
            db.commit()
            db.flush()
            inserted_tables.append("media")
            logger.info("✅ Inserted Media data")
        elif count == -1:
            logger.warning(
                "⏭️  Table 'media' does not exist, skipping Media data")
            skipped_tables.append("media (table not found)")
        else:
            logger.info(
                f"⏭️  Table 'media' has {count} records, skipping Media data")
            skipped_tables.append(f"media ({count} records)")

        # 插入 SEO 数据
        is_empty, count = check_table_empty("seo", db)
        if is_empty and count != -1:
            for seo in seo_data:
                db.execute(insert(Seo).values(seo))
            db.commit()
            db.flush()
            inserted_tables.append("seo")
            logger.info("✅ Inserted SEO data")
        elif count == -1:
            logger.warning("⏭️  Table 'seo' does not exist, skipping SEO data")
            skipped_tables.append("seo (table not found)")
        else:
            logger.info(
                f"⏭️  Table 'seo' has {count} records, skipping SEO data")
            skipped_tables.append(f"seo ({count} records)")

        # 插入 Tax 数据
        is_empty, count = check_table_empty("taxes", db)
        if is_empty and count != -1:
            db.execute(insert(Tax).values(tax_data))
            db.commit()
            inserted_tables.append("taxes")
            logger.info("✅ Inserted Tax data")
        elif count == -1:
            logger.warning(
                "⏭️  Table 'taxes' does not exist, skipping Tax data")
            skipped_tables.append("taxes (table not found)")
        else:
            logger.info(
                f"⏭️  Table 'taxes' has {count} records, skipping Tax data")
            skipped_tables.append(f"taxes ({count} records)")

        # 插入 Section 数据
        is_empty, count = check_table_empty("sections", db)
        if is_empty and count != -1:
            for section in section_data:
                db.execute(insert(Section).values(section))
            db.commit()
            db.flush()
            inserted_tables.append("sections")
            logger.info("✅ Inserted Section data")
        elif count == -1:
            logger.warning(
                "⏭️  Table 'sections' does not exist, skipping Section data")
            skipped_tables.append("sections (table not found)")
        else:
            logger.info(
                f"⏭️  Table 'sections' has {count} records, skipping Section data")
            skipped_tables.append(f"sections ({count} records)")

        # 插入 Board 数据
        is_empty, count = check_table_empty("boards", db)
        if is_empty and count != -1:
            for board in board_data:
                db.execute(insert(Board).values(board))
            db.commit()
            db.flush()
            inserted_tables.append("boards")
            logger.info("✅ Inserted Board data")
        elif count == -1:
            logger.warning(
                "⏭️  Table 'boards' does not exist, skipping Board data")
            skipped_tables.append("boards (table not found)")
        else:
            logger.info(
                f"⏭️  Table 'boards' has {count} records, skipping Board data")
            skipped_tables.append(f"boards ({count} records)")

        # 插入 Friend 数据
        is_empty, count = check_table_empty("friends", db)
        if is_empty and count != -1:
            for friend in friend_data:
                db.execute(insert(Friend).values(friend))
            db.commit()
            db.flush()
            inserted_tables.append("friends")
            logger.info("✅ Inserted Friend data")
        elif count == -1:
            logger.warning(
                "⏭️  Table 'friends' does not exist, skipping Friend data")
            skipped_tables.append("friends (table not found)")
        else:
            logger.info(
                f"⏭️  Table 'friends' has {count} records, skipping Friend data")
            skipped_tables.append(f"friends ({count} records)")

        # 插入 Subscriber 数据
        is_empty, count = check_table_empty("subscribers", db)
        if is_empty and count != -1:
            for subscriber in subscriber_data:
                db.execute(insert(Subscriber).values(subscriber))
            db.commit()
            inserted_tables.append("subscribers")
            logger.info("✅ Inserted Subscriber data")
        elif count == -1:
            logger.warning(
                "⏭️  Table 'subscribers' does not exist, skipping Subscriber data")
            skipped_tables.append("subscribers (table not found)")
        else:
            logger.info(
                f"⏭️  Table 'subscribers' has {count} records, skipping Subscriber data")
            skipped_tables.append(f"subscribers ({count} records)")

        # 总结
        if inserted_tables:
            logger.info(
                f"✅ Successfully inserted data into: {', '.join(inserted_tables)}")
        if skipped_tables:
            logger.info(f"⏭️  Skipped tables: {', '.join(skipped_tables)}")

        if not inserted_tables and not skipped_tables:
            logger.warning("⚠️  No data was inserted or skipped")

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to insert initial data: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(insert_initial_data())
