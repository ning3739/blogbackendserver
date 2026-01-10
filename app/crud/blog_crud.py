import json
import hashlib
from slugify import slugify
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import select, insert, update, func, delete
from app.models.blog_model import (
    Blog,
    Blog_Tag,
    Blog_TTS,
    Blog_Status,
    Blog_Stats,
    Blog_Summary,
    Blog_Comment,
    Saved_Blog,
)
from app.models.tag_model import Tag
from app.models.seo_model import Seo
from app.models.media_model import Media
from app.core.database.mysql import mysql_manager
from app.core.database.redis import redis_manager
from app.core.logger import logger_manager
from app.models.user_model import User, RoleType
from app.utils.keyset_pagination import paginator_desc
from app.utils.offset_pagination import offset_paginator
from app.utils.agent import agent_utils

from app.utils.client_info import client_info_utils
from app.core.i18n.i18n import get_message, Language

from app.tasks import (
    large_content_translation_task,
    generate_content_audio_task,
    summary_blog_content,
)
from app.schemas.common import LargeContentTranslationType
from celery import chain


class BlogCrud:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = logger_manager.get_logger(__name__)

    def _get_content_hash(self, content: dict) -> str:
        import json

        # 将dict转换为JSON字符串后计算hash
        content_str = json.dumps(content, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(content_str.encode("utf-8")).hexdigest()

    async def get_blog_by_id(self, blog_id: int) -> Optional[Blog]:
        statement = select(Blog).where(Blog.id == blog_id)
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def get_blog_by_slug(self, slug: str) -> Optional[Blog]:
        statement = (
            select(Blog)
            .options(
                joinedload(Blog.cover),
                selectinload(Blog.blog_tags).selectinload(Blog_Tag.tag),
            )
            .where(Blog.slug == slug)
        )
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def _get_real_time_blog_stats(
        self,
        blog_ids: List[int],
    ) -> Dict[int, Dict[str, Any]]:
        result = await self.db.execute(
            select(Blog_Stats).where(Blog_Stats.blog_id.in_(blog_ids))
        )
        stats_list = result.scalars().all()

        # 只返回需要的统计字段，去掉 id 和 blog_id
        return {
            stats.blog_id: {
                "views": stats.views,
                "likes": stats.likes,
                "comments": stats.comments,
                "saves": stats.saves,
            }
            for stats in stats_list
        }

    async def _get_blog_comment_by_id(
        self, comment_id: int, include_deleted: bool = False
    ) -> Optional[Blog_Comment]:
        """获取博客评论，可选择是否包含已删除的评论"""
        statement = select(Blog_Comment).where(Blog_Comment.id == comment_id)
        if not include_deleted:
            statement = statement.where(Blog_Comment.is_deleted == False)
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def _change_blog_comment_count(
        self,
        blog_id: int,
        comment_type: str,
        language: Language,
    ) -> bool:
        blog_stats = await self.db.execute(
            select(Blog_Stats).where(Blog_Stats.blog_id == blog_id)
        )
        blog_stats = blog_stats.scalar_one_or_none()
        if not blog_stats:
            raise HTTPException(
                status_code=404,
                detail=get_message("blog.common.blogNotFound", language),
            )

        if comment_type == "create":
            await self.db.execute(
                update(Blog_Stats)
                .where(Blog_Stats.blog_id == blog_id)
                .values(comments=Blog_Stats.comments + 1)
            )
        elif comment_type == "delete" and blog_stats.comments > 0:
            await self.db.execute(
                update(Blog_Stats)
                .where(Blog_Stats.blog_id == blog_id)
                .values(comments=Blog_Stats.comments - 1)
            )
        await self.db.commit()
        return True

    async def _build_blog_comment_tree(
        self,
        comments: List[Blog_Comment],
        parent_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        tree = []
        for comment in comments:
            if comment.parent_id == parent_id:
                children = await self._build_blog_comment_tree(comments, comment.id)

                comment_dict = {
                    "comment_id": comment.id,
                    "user_id": comment.user_id,
                    "username": comment.user.username if comment.user else None,
                    "avatar_url": comment.user.avatar.thumbnail_filepath_url
                    or comment.user.avatar.original_filepath_url
                    if comment.user and comment.user.avatar
                    else None,
                    "user_role": comment.user.role.name,
                    "city": comment.user.city,
                    "parent_id": comment.parent_id,
                    "comment": comment.comment,
                    "created_at": comment.created_at.isoformat()
                    if comment.created_at
                    else None,
                    "updated_at": comment.updated_at.isoformat()
                    if comment.updated_at
                    else None,
                }
                if children:
                    comment_dict["children"] = children
                tree.append(comment_dict)
        return tree

    async def get_blog_lists(
        self,
        language: Language,
        section_id: int,
        page: int = 1,
        size: int = 20,
        published_only: bool = True,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """获取博客列表，使用传统分页工具 page_paginator。

        返回 (items, pagination_metadata)，并在缓存中存储标准响应结构。
        统计数据和变现信息每次都实时获取，不会被缓存。
        """
        # 验证分页参数
        try:
            page, size = offset_paginator.validate_pagination_params(
                page, size)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=get_message("common.invalidRequest", language),
            )

        cache_key = f"blog_lists:{section_id}:lang={language}:page={page}:size={size}:published_only={published_only}"
        cache_data = await redis_manager.get_async(cache_key)

        if cache_data:
            # 命中缓存：获取缓存的博客基础数据
            payload = json.loads(cache_data)
            cached_items = payload.get("items", [])
            pagination_metadata = payload.get("pagination", {})

            # 实时获取统计数据和变现信息并添加到缓存数据中
            if cached_items:
                blog_ids = [item["blog_id"] for item in cached_items]
                stats = await self._get_real_time_blog_stats(blog_ids)

                # 为每个博客项添加实时统计数据和变现信息（不修改缓存）
                items_with_stats = []
                for item in cached_items:
                    blog_id = item["blog_id"]
                    item_with_stats = item.copy()  # 创建副本，不修改缓存数据
                    item_with_stats["blog_stats"] = stats.get(blog_id, {})

                    items_with_stats.append(item_with_stats)

                return items_with_stats, pagination_metadata

            return cached_items, pagination_metadata

        # 未命中缓存：构建 JOIN 查询与计数查询
        if published_only is True:
            base_stmt = (
                select(Blog)
                .join(Blog_Status, Blog_Status.blog_id == Blog.id)
                .options(
                    joinedload(Blog.cover),
                    selectinload(Blog.blog_tags).selectinload(Blog_Tag.tag),
                )
                .where(
                    Blog.section_id == section_id,
                    Blog_Status.is_published,
                )
            )
        else:
            base_stmt = (
                select(Blog)
                .options(
                    joinedload(Blog.cover),
                    selectinload(Blog.blog_tags).selectinload(Blog_Tag.tag),
                )
                .where(Blog.section_id == section_id)
            )

        count_stmt = select(func.count(Blog.id)).where(
            Blog.section_id == section_id,
        )

        rows, pagination_metadata = await offset_paginator.get_paginated_join_result(
            db=self.db,
            base_stmt=base_stmt,
            count_stmt=count_stmt,
            page=page,
            size=size,
            order_by=[Blog.created_at.desc(), Blog.id.desc()],
        )

        # 计算本月的博客数量
        if published_only is False:
            now = datetime.now(timezone.utc)
            month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
            if now.month == 12:
                next_month_start = datetime(
                    now.year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                next_month_start = datetime(
                    now.year, now.month + 1, 1, tzinfo=timezone.utc
                )

            count_this_month = await self.db.execute(
                select(func.count(Blog.id)).where(
                    Blog.created_at.between(month_start, next_month_start)
                )
            )
            count_this_month = count_this_month.scalar_one_or_none()

            # 计算更新的博客数量
            count_updated = await self.db.execute(
                select(func.count(Blog.id)).where(
                    Blog.updated_at.between(month_start, next_month_start)
                )
            )
            count_updated = count_updated.scalar_one_or_none()
            pagination_metadata["new_items_this_month"] = count_this_month
            pagination_metadata["updated_items_this_month"] = count_updated

        # rows 为 JOIN 结果，当前 select 仅选择 Blog，因此每行第一个元素为 Blog 实例
        blogs: List[Blog] = [row[0] for row in rows]

        items: List[Dict[str, Any]] = [
            {
                "blog_id": blog.id,
                "blog_slug": blog.slug,
                "cover_url": blog.cover.watermark_filepath_url if blog.cover else None,
                "created_at": blog.created_at.isoformat(),
                "updated_at": blog.updated_at.isoformat() if blog.updated_at else None,
            }
            for blog in blogs
        ]

        if published_only is True:
            for i, blog in enumerate(blogs):
                items[i].update(
                    {
                        "blog_title": blog.chinese_title
                        if language == Language.ZH_CN
                        else blog.english_title,
                        "blog_description": blog.chinese_description
                        if language == Language.ZH_CN
                        else blog.english_description,
                        "blog_tags": [
                            {
                                "tag_id": tag.id,
                                "tag_title": tag.tag.chinese_title
                                if language == Language.ZH_CN
                                else tag.tag.english_title,
                            }
                            for tag in blog.blog_tags
                        ],
                    }
                )

        else:
            for i, blog in enumerate(blogs):
                items[i].update(
                    {
                        "blog_title": blog.chinese_title,
                        "blog_description": blog.chinese_description,
                        "section_slug": blog.section.slug,
                        "is_published": blog.blog_status.is_published,
                        "is_archived": blog.blog_status.is_archived,
                        "is_featured": blog.blog_status.is_featured,
                        "blog_tags": [
                            {
                                "tag_id": tag.id,
                                "tag_title": tag.tag.chinese_title,
                            }
                            for tag in blog.blog_tags
                        ],
                    }
                )

        # 缓存结果（不包含统计数据）
        cache_payload = offset_paginator.create_response_data(
            items, pagination_metadata
        )
        await redis_manager.set_async(cache_key, json.dumps(cache_payload))

        # 实时获取统计数据和变现信息并添加到返回数据中
        if items:
            blog_ids = [item["blog_id"] for item in items]
            stats = await self._get_real_time_blog_stats(blog_ids)

            # 为每个博客项添加实时统计数据和变现信息
            for item in items:
                blog_id = item["blog_id"]
                item["blog_stats"] = stats.get(blog_id, {})

        return items, pagination_metadata

    async def get_blog_lists_by_tag_slug(
        self,
        tag_slug: str,
        language: Language,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """根据标签slug获取博客列表，使用传统分页工具 offset_paginator。

        Args:
            tag_slug: 标签的slug
            language: 语言设置，用于错误消息
            page: 页码
            size: 每页数量

        Returns:
            (items, pagination_metadata) - 博客列表和分页元数据

        Raises:
            HTTPException: 当标签不存在时抛出404错误
        """
        # 验证分页参数
        try:
            page, size = offset_paginator.validate_pagination_params(
                page, size)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=get_message("common.invalidRequest", language),
            )

        # 首先验证标签是否存在
        tag_statement = select(Tag).where(Tag.slug == tag_slug)
        tag_result = await self.db.execute(tag_statement)
        tag = tag_result.scalar_one_or_none()

        if not tag:
            raise HTTPException(
                status_code=404,
                detail=get_message("tag.common.tagNotFound", language),
            )

        # 缓存键
        cache_key = (
            f"blog_lists_by_tag_slug:{tag_slug}:lang={language}:page={page}:size={size}"
        )
        cache_data = await redis_manager.get_async(cache_key)

        if cache_data:
            # 命中缓存：获取缓存的博客基础数据
            payload = json.loads(cache_data)
            cached_items = payload.get("items", [])
            pagination_metadata = payload.get("pagination", {})
            return cached_items, pagination_metadata

        # 未命中缓存：构建 JOIN 查询与计数查询
        base_stmt = (
            select(Blog)
            .join(Blog_Tag, Blog_Tag.blog_id == Blog.id)
            .join(Blog_Status, Blog_Status.blog_id == Blog.id)
            .options(
                joinedload(Blog.section),
            )
            .where(
                Blog_Tag.tag_id == tag.id,
                Blog_Status.is_published,
            )
        )

        count_stmt = (
            select(func.count(Blog.id))
            .join(Blog_Tag, Blog_Tag.blog_id == Blog.id)
            .join(Blog_Status, Blog_Status.blog_id == Blog.id)
            .where(
                Blog_Tag.tag_id == tag.id,
                Blog_Status.is_published,
            )
        )

        rows, pagination_metadata = await offset_paginator.get_paginated_join_result(
            db=self.db,
            base_stmt=base_stmt,
            count_stmt=count_stmt,
            page=page,
            size=size,
            order_by=[Blog.created_at.desc(), Blog.id.desc()],
        )

        # rows 为 JOIN 结果，当前 select 仅选择 Blog，因此每行第一个元素为 Blog 实例
        blogs: List[Blog] = [row[0] for row in rows]

        items: List[Dict[str, Any]] = [
            {
                "blog_id": blog.id,
                "blog_slug": blog.slug,
                "section_slug": blog.section.slug if blog.section else None,
                "blog_title": blog.chinese_title
                if language == Language.ZH_CN
                else blog.english_title,
                "blog_description": blog.chinese_description
                if language == Language.ZH_CN
                else blog.english_description,
                "created_at": blog.created_at.isoformat(),
                "updated_at": blog.updated_at.isoformat() if blog.updated_at else None,
            }
            for blog in blogs
        ]

        # 缓存结果
        cache_payload = offset_paginator.create_response_data(
            items, pagination_metadata
        )
        await redis_manager.set_async(cache_key, json.dumps(cache_payload))

        return items, pagination_metadata

    async def get_archived_blog_lists(
        self,
        language: Language,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """获取归档的博客列表，使用 cursor pagination

        Args:
            language: 语言设置
            cursor: 可选的分页游标
            limit: 每页数量

        Returns:
            包含归档博客列表和分页信息的字典
        """
        # 缓存键
        cache_key = f"blog_archived_lists:lang={language}:limit={limit}:cursor={cursor}"
        cache_data = await redis_manager.get_async(cache_key)

        if cache_data:
            return json.loads(cache_data)

        # 构建查询：获取已归档的博客
        base_stmt = (
            select(Blog)
            .join(Blog_Status, Blog_Status.blog_id == Blog.id)
            .options(
                joinedload(Blog.section),
            )
            .where(Blog_Status.is_archived)
        )

        # 应用 keyset pagination 过滤
        if cursor:
            base_stmt = paginator_desc.apply_filters(
                base_stmt,
                Blog.created_at,
                Blog.id,
                cursor,
            )

        # 应用排序
        base_stmt = base_stmt.order_by(
            *paginator_desc.order_by(Blog.created_at, Blog.id)
        )

        # 限制数量（多取一条用于判断是否有下一页）
        base_stmt = base_stmt.limit(limit + 1)

        # 执行查询
        result = await self.db.execute(base_stmt)
        blogs = result.scalars().all()

        # 检查是否有更多记录
        has_next = len(blogs) > limit
        if has_next:
            blogs = blogs[:-1]

        # 格式化响应数据
        items: List[Dict[str, Any]] = []
        for blog in blogs:
            items.append(
                {
                    "blog_id": blog.id,
                    "blog_slug": blog.slug,
                    "section_slug": blog.section.slug if blog.section else None,
                    "blog_title": blog.chinese_title
                    if language == Language.ZH_CN
                    else blog.english_title,
                    "blog_description": blog.chinese_description
                    if language == Language.ZH_CN
                    else blog.english_description,
                    "created_at": blog.created_at.isoformat()
                    if blog.created_at
                    else None,
                    "updated_at": blog.updated_at.isoformat()
                    if blog.updated_at
                    else None,
                }
            )

        # 生成下一页的 cursor
        next_cursor = None
        if has_next and blogs:
            last_blog = blogs[-1]
            next_cursor = paginator_desc.encode_cursor(
                last_blog.created_at, last_blog.id
            )

        # 使用 keyset paginator 的 create_response_data 方法
        response = paginator_desc.create_response_data(
            items=items,
            limit=limit,
            has_next=has_next,
            next_cursor=next_cursor,
            items_key="blogs",
        )

        # 缓存结果
        await redis_manager.set_async(cache_key, json.dumps(response))

        return response

    async def get_blog_details_seo(
        self,
        blog_slug: str,
        language: Language,
    ) -> Optional[Dict]:
        seo_cache_key = f"blog_details_seo:{blog_slug}"
        cache_data = await redis_manager.get_async(seo_cache_key)
        if cache_data:
            return json.loads(cache_data)

        blog = await self.get_blog_by_slug(blog_slug)
        if not blog:
            raise HTTPException(
                status_code=404,
                detail=get_message("blog.common.blogNotFound", language),
            )

        # 使用 LEFT JOIN 查询博客和 SEO 信息
        statement = (
            select(Blog, Seo)
            .outerjoin(Seo, Blog.seo_id == Seo.id)
            .where(Blog.id == blog.id)
        )
        result = await self.db.execute(statement)
        row = result.first()

        if not row:
            raise HTTPException(
                status_code=404,
                detail=get_message("blog.common.blogNotFound", language),
            )

        _, blog_seo = row

        # 如果博客没有关联的 SEO 信息，返回 404 错误
        if not blog_seo or blog_seo.id is None:
            raise HTTPException(
                status_code=404,
                detail=get_message("blog.common.blogNotFound", language),
            )

        response = {
            "title": {
                "zh": blog_seo.chinese_title,
                "en": blog_seo.english_title,
            },
            "description": {
                "zh": blog_seo.chinese_description,
                "en": blog_seo.english_description,
            },
            "keywords": {
                "zh": blog_seo.chinese_keywords,
                "en": blog_seo.english_keywords,
            },
        }

        await redis_manager.set_async(seo_cache_key, json.dumps(response))

        return response

    async def get_blog_details(
        self,
        request: Request,
        blog_slug: str,
        language: Language,
        is_editor: bool = False,
        user_id: Optional[int] = None,
    ) -> Optional[Dict]:
        details_cache_key = f"blog_details:{blog_slug}:lang={language}:is_editor={is_editor}:user_id={user_id}"
        hash_cache_key = (
            f"blog_details_hash:{blog_slug}:is_editor={is_editor}:user_id={user_id}"
        )
        cache_data = await redis_manager.get_async(details_cache_key)
        current_ip = client_info_utils.get_client_ip(request)
        user_agent = client_info_utils.get_user_agent(request)

        blog = await self.get_blog_by_slug(blog_slug)
        if not blog:
            raise HTTPException(
                status_code=404,
                detail=get_message("blog.common.blogNotFound", language),
            )

        # 计算哈希值
        hash_key = hashlib.sha256(
            f"{current_ip}:{user_agent}:{is_editor}".encode()
        ).hexdigest()

        # 命中缓存：统一使用 Redis 缓存进行 hash 比对
        if cache_data:
            should_increment_view = False
            cached_last_hash = await redis_manager.get_async(hash_cache_key)
            if not cached_last_hash or cached_last_hash != hash_key:
                should_increment_view = True

            if should_increment_view:
                await self.db.execute(
                    update(Blog_Stats)
                    .where(Blog_Stats.blog_id == blog.id)
                    .values(views=Blog_Stats.views + 1)
                )
                await self.db.commit()
                # 更新缓存中的 hash 值
                await redis_manager.set_async(hash_cache_key, hash_key)

            return json.loads(cache_data)

        # 未命中缓存：查询数据库构建详情，并处理浏览量逻辑
        # 首先检查用户是否保存了该博客
        is_saved = False
        if user_id is not None:
            saved_blog_result = await self.db.execute(
                select(Saved_Blog).where(
                    Saved_Blog.blog_id == blog.id, Saved_Blog.user_id == user_id
                )
            )
            is_saved = saved_blog_result.scalar_one_or_none() is not None

        # 统一使用 Redis 缓存进行 hash 比对
        should_increment_view = False
        cached_last_hash = await redis_manager.get_async(hash_cache_key)
        if not cached_last_hash or cached_last_hash != hash_key:
            should_increment_view = True

        if should_increment_view:
            await self.db.execute(
                update(Blog_Stats)
                .where(Blog_Stats.blog_id == blog.id)
                .values(views=Blog_Stats.views + 1)
            )
            await self.db.commit()
            # 更新缓存中的 hash 值
            await redis_manager.set_async(hash_cache_key, hash_key)

        if is_editor:
            response = {
                "seo_id": blog.seo_id if blog.seo_id else None,
                "blog_id": blog.id,
                "cover_id": blog.cover_id,
                "section_id": blog.section_id,
                "chinese_title": blog.chinese_title,
                "chinese_description": blog.chinese_description,
                "cover_url": blog.cover.watermark_filepath_url if blog.cover else None,
                "chinese_content": blog.chinese_content,
                "blog_tags": [
                    {"tag_id": tag.tag_id, "chinese_title": tag.tag.chinese_title}
                    for tag in blog.blog_tags
                ],
                "created_at": blog.created_at.isoformat(),
                "updated_at": blog.updated_at.isoformat() if blog.updated_at else None,
            }
        else:
            response = {
                "blog_id": blog.id,
                "blog_name": blog.chinese_title
                if language == Language.ZH_CN
                else blog.english_title
                if blog.english_title
                else None,
                "blog_description": blog.chinese_description
                if language == Language.ZH_CN
                else blog.english_description
                if blog.english_description
                else None,
                "cover_url": blog.cover.watermark_filepath_url if blog.cover else None,
                "blog_content": blog.chinese_content
                if language == Language.ZH_CN
                else blog.english_content
                if blog.english_content
                else None,
                "is_saved": is_saved,
                "blog_tags": [
                    {
                        "tag_id": tag.id,
                        "tag_slug": tag.tag.slug,
                        "tag_title": tag.tag.chinese_title
                        if language == Language.ZH_CN
                        else tag.tag.english_title,
                    }
                    for tag in blog.blog_tags
                ],
                "created_at": blog.created_at.isoformat(),
                "updated_at": blog.updated_at.isoformat() if blog.updated_at else None,
            }

        # 更新缓存
        await redis_manager.set_async(details_cache_key, json.dumps(response))

        return response

    async def get_blog_tts(
        self,
        blog_id: int,
        language: str,
    ) -> Optional[Dict]:
        cache_key = f"blog_tts:{blog_id}:lang={language}"
        cache_data = await redis_manager.get_async(cache_key)

        if cache_data:
            return json.loads(cache_data)

            # 先查询 Blog_TTS 获取 TTS ID
        tts_statement = select(Blog_TTS).where(Blog_TTS.blog_id == blog_id)
        tts_result = await self.db.execute(tts_statement)
        blog_tts = tts_result.scalar_one_or_none()

        if not blog_tts:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    "blog.getBlogTTS.blogTtsNotFound", language),
            )

        # 根据语言选择对应的 TTS ID
        tts_id = (
            blog_tts.chinese_tts_id
            if language == Language.ZH_CN
            else blog_tts.english_tts_id
        )

        if not tts_id:
            response = {
                "blog_id": blog_id,
                "tts": None,
            }
        else:
            # 通过 TTS ID 查询 Media 获取 URL
            media_statement = select(Media.original_filepath_url).where(
                Media.id == tts_id
            )
            media_result = await self.db.execute(media_statement)
            tts_url = media_result.scalar_one_or_none()

            response = {
                "blog_id": blog_id,
                "tts": tts_url if tts_url else None,
            }

        # 更新缓存
        await redis_manager.set_async(cache_key, json.dumps(response))

        return response

    async def create_blog(
        self,
        user_id: int,
        section_id: int,
        seo_id: int,
        chinese_title: str,
        chinese_description: str,
        chinese_content: dict,
        cover_id: int,
        blog_tags: List[int] = [],
    ) -> str:
        # 翻译
        english_title = await agent_utils.translate(text=chinese_title)
        english_description = await agent_utils.translate(text=chinese_description)

        # 生成slug并限制长度
        slug = slugify(english_title, max_length=200)  # 限制在200字符以内，留一些缓冲

        # 计算博客内容hash值
        content_hash = self._get_content_hash(chinese_content)

        # 创建博客
        result = await self.db.execute(
            insert(Blog).values(
                user_id=user_id,
                section_id=section_id,
                seo_id=seo_id,
                slug=slug,
                chinese_title=chinese_title,
                english_title=english_title,
                chinese_description=chinese_description,
                english_description=english_description,
                chinese_content=chinese_content,
                content_hash=content_hash,
                cover_id=cover_id,
            )
        )

        # 获取插入后的博客ID
        blog_id = result.inserted_primary_key[0]

        # 创建博客状态
        await self.db.execute(
            insert(Blog_Status).values(
                user_id=user_id,
                blog_id=blog_id,
                is_published=False,
                is_archived=False,
                is_featured=False,
            )
        )

        # 创建博客统计
        await self.db.execute(
            insert(Blog_Stats).values(
                blog_id=blog_id,
                views=0,
                likes=0,
                comments=0,
                saves=0,
            )
        )

        # 创建博客标签
        if blog_tags:
            for tag_id in blog_tags:
                await self.db.execute(
                    insert(Blog_Tag).values(
                        blog_id=blog_id,
                        tag_id=tag_id,
                    )
                )

        await self.db.commit()

        # 使用celery Task 任务链：翻译博客内容 -> 生成博客摘要
        # 任务链确保任务按顺序执行，翻译完成后才执行摘要生成
        task_chain = chain(
            large_content_translation_task.s(
                content=chinese_content,
                content_type=LargeContentTranslationType.BLOG,
                content_id=blog_id,
            ),
            summary_blog_content.si(blog_id=blog_id),
            generate_content_audio_task.si(blog_id=blog_id),
        )
        task_chain.apply_async()

        # 更新缓存
        await redis_manager.delete_pattern_async(f"blog_lists:{section_id}:*")

        return slug

    async def update_blog(
        self,
        language: Language,
        user_id: int,
        blog_slug: str,
        seo_id: int,
        chinese_title: str,
        chinese_description: str,
        chinese_content: dict,
        cover_id: int,
        blog_tags: List[int] = [],
    ) -> Optional[str]:
        blog = await self.get_blog_by_slug(blog_slug)
        if not blog or blog.user_id != user_id:
            raise HTTPException(
                status_code=404,
                detail=get_message("blog.common.blogNotFound", language),
            )

        # 查看博客内容是否发生变化
        blog_title_changed = blog.chinese_title != chinese_title
        blog_description_changed = blog.chinese_description != chinese_description

        # 计算新的内容hash
        new_content_hash = self._get_content_hash(chinese_content)
        blog_content_changed = blog.content_hash != new_content_hash

        if blog_title_changed:
            english_title = await agent_utils.translate(text=chinese_title)
            # 生成slug并限制长度
            slug = slugify(
                english_title, max_length=200
            )  # 限制在200字符以内，留一些缓冲
        else:
            english_title = blog.english_title
            slug = blog.slug

        if blog_description_changed:
            english_description = await agent_utils.translate(text=chinese_description)
        else:
            english_description = blog.english_description

        # 更新博客内容
        await self.db.execute(
            update(Blog)
            .where(Blog.id == blog.id)
            .values(
                seo_id=seo_id,
                cover_id=cover_id,
                slug=slug,
                chinese_title=chinese_title,
                english_title=english_title,
                chinese_description=chinese_description,
                english_description=english_description,
                chinese_content=chinese_content,
                content_hash=new_content_hash,  # 更新内容hash
            )
        )

        # 更新博客标签：先删除旧标签，再插入新标签
        if blog_tags:
            # 删除该博客的所有旧标签
            await self.db.execute(delete(Blog_Tag).where(Blog_Tag.blog_id == blog.id))

            # 插入新标签
            for tag_id in blog_tags:
                await self.db.execute(
                    insert(Blog_Tag).values(
                        blog_id=blog.id,
                        tag_id=tag_id,
                    )
                )

        await self.db.commit()

        # 检查是否English_content 有变化
        if blog_content_changed:
            self.logger.info(
                f"Content changed detected, starting task chain for blog ID {blog.id}"
            )
            # TODO 使用celery Task 任务链： 翻译博客内容 -> 生成博客摘要 -> 生成目录 -> 生成中英TTS删除旧的TTS并上传新的TTS到s3 bucket
            task_chain = chain(
                large_content_translation_task.s(
                    content=chinese_content,
                    content_type=LargeContentTranslationType.BLOG,
                    content_id=blog.id,
                ),
                summary_blog_content.si(blog_id=blog.id),
                generate_content_audio_task.si(blog_id=blog.id),
            )
            task_chain.apply_async()
            self.logger.info(
                f"Task chain started successfully for blog ID {blog.id}")
        else:
            self.logger.info(
                f"No content change detected for blog ID {blog.id}, skipping task chain"
            )

        # 更新缓存
        await redis_manager.delete_pattern_async("blog_lists:*")
        await redis_manager.delete_async(f"blog_tts:{blog.id}")
        await redis_manager.delete_pattern_async(
            f"blog_details:{blog.slug}:lang={language}:*"
        )
        await redis_manager.delete_async(f"blog_details_seo:{blog.slug}")
        await redis_manager.delete_async(f"blog_summary:{blog.id}:lang={language}")
        await redis_manager.delete_pattern_async(
            f"blog_archived_lists:lang={language}:*"
        )
        await redis_manager.delete_async(f"get_recent_populor_blog:lang={language}")
        await redis_manager.delete_pattern_async("user_saved_blogs:*")
        await redis_manager.delete_async(f"blog_navigation:{blog.id}:lang={language}")

        return slug

    async def get_blog_summary(
        self,
        blog_id: int,
        language: Language,
    ) -> Optional[Dict]:
        cache_key = f"blog_summary:{blog_id}:lang={language}"
        cache_data = await redis_manager.get_async(cache_key)

        if cache_data:
            return json.loads(cache_data)

        statement = select(Blog_Summary).where(Blog_Summary.blog_id == blog_id)
        result = await self.db.execute(statement)
        blog_summary = result.scalar_one_or_none()
        if not blog_summary:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    "blog.getBlogSummary.blogSummaryNotFound", language),
            )

        response = {
            "summary": blog_summary.chinese_summary
            if language == Language.ZH_CN
            else blog_summary.english_summary
            if blog_summary.english_summary
            else None,
        }
        await redis_manager.set_async(cache_key, json.dumps(response))
        return response

    async def get_blog_comment_lists(
        self,
        blog_id: int,
        language: Language,
        limit: int = 20,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        cache_key = f"blog_comment_lists:{blog_id}:{limit}:{cursor}"
        cache_data = await redis_manager.get_async(cache_key)
        if cache_data:
            return json.loads(cache_data)

        # 先获取父评论（parent_id 为 None 的评论）
        parent_statement = (
            select(Blog_Comment)
            .options(selectinload(Blog_Comment.user).selectinload(User.avatar))
            .where(
                Blog_Comment.blog_id == blog_id,
                Blog_Comment.is_deleted == False,
                Blog_Comment.parent_id.is_(None),
            )
        )

        # 应用 keyset pagination 过滤到父评论
        if cursor:
            parent_statement = paginator_desc.apply_filters(
                parent_statement,
                Blog_Comment.created_at,
                Blog_Comment.id,
                cursor,
            )

        # 应用排序到父评论
        parent_statement = parent_statement.order_by(
            *paginator_desc.order_by(Blog_Comment.created_at, Blog_Comment.id)
        )

        # 限制父评论数量
        parent_statement = parent_statement.limit(limit + 1)

        # 获取父评论
        parent_result = await self.db.execute(parent_statement)
        parent_comments = parent_result.scalars().all()

        # 检查是否有更多父评论

        has_next = len(parent_comments) > limit
        if has_next:
            parent_comments = parent_comments[:-1]

        if not parent_comments:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    "blog.getBlogCommentLists.commentNotFound", language
                ),
            )

        # 获取所有父评论的子评论和孙评论，确保评论树完整（支持三级嵌套）
        all_comments = list(parent_comments)
        parent_ids = [c.id for c in parent_comments]

        # 第一级：获取所有子评论（parent_id 指向父评论）
        children_statement = (
            select(Blog_Comment)
            .options(selectinload(Blog_Comment.user).selectinload(User.avatar))
            .where(
                Blog_Comment.blog_id == blog_id,
                Blog_Comment.is_deleted == False,
                Blog_Comment.parent_id.in_(parent_ids),
            )
        )

        children_result = await self.db.execute(children_statement)
        children_comments = children_result.scalars().all()
        all_comments.extend(children_comments)

        # 第二级：获取所有孙评论（parent_id 指向子评论）
        if children_comments:
            children_ids = [c.id for c in children_comments]
            grandchildren_statement = (
                select(Blog_Comment)
                .options(selectinload(Blog_Comment.user).selectinload(User.avatar))
                .where(
                    Blog_Comment.blog_id == blog_id,
                    Blog_Comment.is_deleted == False,
                    Blog_Comment.parent_id.in_(children_ids),
                )
            )

            grandchildren_result = await self.db.execute(grandchildren_statement)
            grandchildren_comments = grandchildren_result.scalars().all()
            all_comments.extend(grandchildren_comments)

            self.logger.info(
                f"Retrieved {len(parent_comments)} parent comments, {len(children_comments)} child comments, and {len(grandchildren_comments)} grandchild comments"
            )
        else:
            self.logger.info(
                f"Retrieved {len(parent_comments)} parent comments and {len(children_comments)} child comments"
            )

        # 构建评论树
        comment_tree = await self._build_blog_comment_tree(all_comments)

        # 生成下一页的 cursor（基于父评论）
        next_cursor = None
        if has_next and parent_comments:
            last_parent_comment = parent_comments[-1]
            next_cursor = paginator_desc.encode_cursor(
                last_parent_comment.created_at, last_parent_comment.id
            )

        # 使用 keyset paginator 的 create_response_data 方法
        response = paginator_desc.create_response_data(
            items=comment_tree,
            limit=limit,
            has_next=has_next,
            next_cursor=next_cursor,
            items_key="comments",
        )

        # cache the result
        await redis_manager.set_async(cache_key, json.dumps(response))

        return response

    async def create_blog_comment(
        self,
        user_id: int,
        blog_id: int,
        comment: str,
        language: Language,
        parent_id: Optional[int] = None,
    ) -> bool:
        blog = await self.get_blog_by_id(blog_id)
        if not blog:
            raise HTTPException(
                status_code=404,
                detail=get_message("blog.common.blogNotFound", language),
            )

        # 检查是否parent_id是否存在
        if parent_id:
            parent_comment = await self._get_blog_comment_by_id(
                comment_id=parent_id, include_deleted=False
            )
            if not parent_comment:
                raise HTTPException(
                    status_code=404,
                    detail=get_message(
                        "blog.getBlogCommentLists.commentNotFound", language
                    ),
                )

        # 创建评论
        await self.db.execute(
            insert(Blog_Comment).values(
                user_id=user_id,
                blog_id=blog_id,
                comment=comment,
                parent_id=parent_id,
            )
        )

        await self.db.commit()

        # 改变博客评论数
        await self._change_blog_comment_count(
            blog_id=blog_id, comment_type="create", language=language
        )

        # 更新缓存
        await redis_manager.delete_pattern_async(f"blog_comment_lists:{blog_id}:*")

        return True

    async def update_blog_comment(
        self,
        user_id: int,
        comment_id: int,
        comment: str,
        language: Language,
    ) -> bool:
        comment_obj = await self._get_blog_comment_by_id(
            comment_id=comment_id, include_deleted=False
        )
        if not comment_obj or comment_obj.user_id != user_id:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    "blog.getBlogCommentLists.commentNotFound", language
                ),
            )

        # 更新评论
        await self.db.execute(
            update(Blog_Comment)
            .where(Blog_Comment.id == comment_id)
            .values(comment=comment)
        )
        await self.db.commit()

        # 更新缓存
        await redis_manager.delete_pattern_async(
            f"blog_comment_lists:{comment_obj.blog_id}:*"
        )

        return True

    async def delete_blog_comment(
        self,
        user_id: int,
        role: RoleType,
        comment_id: int,
        language: Language,
    ) -> bool:
        comment_obj = await self._get_blog_comment_by_id(
            comment_id=comment_id, include_deleted=False
        )

        if not comment_obj:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    "blog.getBlogCommentLists.commentNotFound", language
                ),
            )

        # 允许作者或管理员删除，其余情况返回404（与博客评论删除逻辑一致）
        if comment_obj.user_id != user_id and role != RoleType.admin:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    "blog.getBlogCommentLists.commentNotFound", language
                ),
            )

        # 软删除评论（设置is_deleted为True）
        await self.db.execute(
            update(Blog_Comment)
            .where(Blog_Comment.id == comment_id)
            .values(is_deleted=True)
        )
        await self.db.commit()

        # 改变博客评论数
        await self._change_blog_comment_count(
            blog_id=comment_obj.blog_id, comment_type="delete", language=language
        )

        # 更新缓存
        await redis_manager.delete_pattern_async(
            f"blog_comment_lists:{comment_obj.blog_id}:*"
        )

        return True

    async def save_blog_button(
        self,
        user_id: int,
        blog_id: int,
        language: Language,
    ) -> bool:
        # 检查是否有blog
        blog = await self.get_blog_by_id(blog_id)
        if not blog:
            raise HTTPException(
                status_code=404,
                detail=get_message("blog.common.blogNotFound", language),
            )

        # 检查是否已经保存
        saved_blog_result = await self.db.execute(
            select(Saved_Blog).where(
                Saved_Blog.user_id == user_id, Saved_Blog.blog_id == blog_id
            )
        )
        saved_blog = saved_blog_result.scalar_one_or_none()

        # 删除缓存
        await redis_manager.delete_pattern_async(f"user_saved_blogs:{user_id}:*")

        if saved_blog:
            # 删除保存
            await self.db.execute(
                delete(Saved_Blog).where(
                    Saved_Blog.user_id == user_id, Saved_Blog.blog_id == blog_id
                )
            )
            # 减少博客的保存数
            await self.db.execute(
                update(Blog_Stats)
                .where(Blog_Stats.blog_id == blog_id)
                .values(saves=Blog_Stats.saves - 1)
            )
            await self.db.commit()

            return False
        else:
            # 创建保存
            await self.db.execute(
                insert(Saved_Blog).values(
                    user_id=user_id,
                    blog_id=blog_id,
                )
            )
            # 增加博客的保存数
            await self.db.execute(
                update(Blog_Stats)
                .where(Blog_Stats.blog_id == blog_id)
                .values(saves=Blog_Stats.saves + 1)
            )
            await self.db.commit()

            return True

    async def like_blog_button(
        self, blog_id: int, language: Language, ip_address: str
    ) -> bool:
        cache_key = f"blog_like_button:{blog_id}:ip={ip_address}"
        cache_data = await redis_manager.get_async(cache_key)
        if cache_data:
            # 用户已经点赞过，那么取消点赞
            await self.db.execute(
                update(Blog_Stats)
                .where(Blog_Stats.blog_id == blog_id)
                .values(likes=Blog_Stats.likes - 1)
            )
            await self.db.commit()
            await redis_manager.delete_async(cache_key)
            return False

        blog = await self.get_blog_by_id(blog_id)
        if not blog:
            raise HTTPException(
                status_code=404,
                detail=get_message("blog.common.blogNotFound", language),
            )

        # 增加点赞数
        await self.db.execute(
            update(Blog_Stats)
            .where(Blog_Stats.blog_id == blog_id)
            .values(likes=Blog_Stats.likes + 1)
        )
        await self.db.commit()

        # 设置缓存，防止重复点赞（缓存24小时）
        await redis_manager.set_async(cache_key, "1", ex=86400)

        return True

    async def update_blog_status(
        self,
        blog_id: int,
        language: Language,
        is_published: Optional[bool] = None,
        is_archived: Optional[bool] = None,
        is_featured: Optional[bool] = None,
    ) -> bool:
        # 验证只能有一个状态被更新
        status_params = [is_published, is_archived, is_featured]
        non_none_count = sum(1 for param in status_params if param is not None)

        if non_none_count != 1:
            raise HTTPException(
                status_code=400,
                detail=get_message(
                    "blog.updateBlogStatus.invalidStatusUpdate", language
                ),
            )

        blog = await self.get_blog_by_id(blog_id=blog_id)
        if not blog:
            raise HTTPException(
                status_code=404,
                detail=get_message("blog.common.blogNotFound", language),
            )

        # 构建更新值字典，只包含非None的字段
        update_values = {}
        if is_published is not None:
            update_values["is_published"] = is_published
        if is_archived is not None:
            update_values["is_archived"] = is_archived
        if is_featured is not None:
            update_values["is_featured"] = is_featured

        await self.db.execute(
            update(Blog_Status)
            .where(Blog_Status.blog_id == blog.id)
            .values(**update_values)
        )
        await self.db.commit()

        # 更新缓存
        await redis_manager.delete_pattern_async("blog_lists:*")
        # 清理导航缓存
        await redis_manager.delete_pattern_async("blog_navigation:*")

        return True

    async def get_blog_navigation(
        self, blog_id: int, language: Language
    ) -> Optional[Dict]:
        """获取博客的上一篇和下一篇导航信息

        Args:
            blog_slug: 当前博客的slug
            language: 语言设置，影响标题显示

        Returns:
            包含previous和next字段的字典，每个字段包含blog_id、blog_slug、blog_title、created_at
            如果不存在上一篇或下一篇，对应字段为None

        Raises:
            HTTPException: 当博客不存在时
        """
        cache_key = f"blog_navigation:{blog_id}:lang={language}"
        cache_data = await redis_manager.get_async(cache_key)

        if cache_data:
            return json.loads(cache_data)

        # 获取当前博客
        blog = await self.get_blog_by_id(blog_id)
        if not blog:
            raise HTTPException(
                status_code=404,
                detail=get_message("blog.common.blogNotFound", language),
            )

        # 从博客获取section_id
        section_id = blog.section_id
        current_created_at = blog.created_at
        current_id = blog.id

        # 获取上一篇博客（创建时间更早的博客）
        # 使用复合排序：先按created_at降序，再按id降序，确保排序的一致性
        prev_statement = (
            select(Blog)
            .join(Blog_Status, Blog_Status.blog_id == Blog.id)
            .where(
                Blog.section_id == section_id,
                Blog_Status.is_published,
                # 使用复合条件：时间更早，或者时间相同但ID更小
                (Blog.created_at < current_created_at)
                | ((Blog.created_at == current_created_at) & (Blog.id < current_id)),
            )
            .order_by(Blog.created_at.desc(), Blog.id.desc())
            .limit(1)
        )
        prev_result = await self.db.execute(prev_statement)
        prev_blog = prev_result.scalar_one_or_none()

        # 获取下一篇博客（创建时间更晚的博客）
        # 使用复合排序：先按created_at升序，再按id升序，确保排序的一致性
        next_statement = (
            select(Blog)
            .join(Blog_Status, Blog_Status.blog_id == Blog.id)
            .where(
                Blog.section_id == section_id,
                Blog_Status.is_published,
                # 使用复合条件：时间更晚，或者时间相同但ID更大
                (Blog.created_at > current_created_at)
                | ((Blog.created_at == current_created_at) & (Blog.id > current_id)),
            )
            .order_by(Blog.created_at.asc(), Blog.id.asc())
            .limit(1)
        )
        next_result = await self.db.execute(next_statement)
        next_blog = next_result.scalar_one_or_none()

        # 构建响应数据
        response = {"previous": None, "next": None}

        # 处理上一篇博客
        if prev_blog:
            response["previous"] = {
                "section_slug": prev_blog.section.slug,
                "blog_slug": prev_blog.slug,
                "blog_title": prev_blog.chinese_title
                if language == Language.ZH_CN
                else prev_blog.english_title,
            }

        # 处理下一篇博客
        if next_blog:
            response["next"] = {
                "section_slug": next_blog.section.slug,
                "blog_slug": next_blog.slug,
                "blog_title": next_blog.chinese_title
                if language == Language.ZH_CN
                else next_blog.english_title,
            }

        # 缓存结果（设置较短的缓存时间，因为导航信息相对稳定）
        await redis_manager.set_async(cache_key, json.dumps(response))

        return response

    async def get_blog_stats(self, blog_id: int, language: Language) -> Optional[Dict]:
        stats = await self.db.execute(
            select(Blog_Stats).where(Blog_Stats.blog_id == blog_id)
        )
        stats = stats.scalar_one_or_none()

        if not stats:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    "blog.getBlogStats.blogStatsNotFound", language),
            )

        response = {
            "views": stats.views,
            "likes": stats.likes,
            "comments": stats.comments,
            "saves": stats.saves,
        }

        return response

    async def delete_blog(self, blog_id: int, language: Language) -> bool:
        # 首先检查博客是否存在
        blog = await self.db.get(Blog, blog_id)
        if not blog:
            raise HTTPException(
                status_code=404,
                detail=get_message("blog.common.blogNotFound", language),
            )

        try:
            # 删除博客（级联删除相关数据）
            await self.db.execute(delete(Blog).where(Blog.id == blog_id))
            await self.db.commit()

            # 更新缓存 - 使用try-except包装，避免缓存错误影响删除结果
            try:
                await redis_manager.delete_pattern_async("blog_lists:*")
                await redis_manager.delete_pattern_async("blog_details:*")
                await redis_manager.delete_pattern_async("blog_details_seo:*")
                # 清理导航缓存
                await redis_manager.delete_pattern_async("blog_navigation:*")
            except Exception as cache_error:
                # 记录缓存清理错误，但不影响删除结果
                self.logger.warning(
                    f"Warning: Failed to clear cache after blog deletion: {cache_error}"
                )

            return True
        except Exception as e:
            # 如果删除失败，回滚事务
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"delete blog failed: {str(e)}",
            )

    async def get_saved_blog_lists(
        self,
        user_id: int,
        language: Language,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        获取用户收藏的博客 - 使用传统分页方式

        Returns:
            Tuple of (items, pagination_metadata)
        """
        # 验证分页参数
        try:
            page, size = offset_paginator.validate_pagination_params(
                page, size)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=get_message("common.invalidRequest", language),
            )

        # 缓存键
        cache_key = f"user_saved_blogs:{user_id}:page={page}:size={size}"
        cache_data = await redis_manager.get_async(cache_key)
        if cache_data:
            payload = json.loads(cache_data)
            return payload.get("items", []), payload.get("pagination", {})

        base_stmt = (
            select(Saved_Blog, Blog)
            .join(Blog, Saved_Blog.blog_id == Blog.id)
            .where(Saved_Blog.user_id == user_id)
        )

        # 构建计数查询语句
        count_stmt = select(func.count(Saved_Blog.id)).where(
            Saved_Blog.user_id == user_id
        )

        # 使用分页工具获取JOIN查询结果
        items, pagination_metadata = await offset_paginator.get_paginated_join_result(
            db=self.db,
            base_stmt=base_stmt,
            count_stmt=count_stmt,
            page=page,
            size=size,
            order_by=[Saved_Blog.created_at.desc(), Saved_Blog.id.desc()],
            language=language,
        )

        # 计算本月收藏的博客数量
        now = datetime.now(timezone.utc)
        month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        if now.month == 12:
            next_month_start = datetime(
                now.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            next_month_start = datetime(
                now.year, now.month + 1, 1, tzinfo=timezone.utc)

        count_this_month = await self.db.execute(
            select(func.count(Saved_Blog.id)).where(
                Saved_Blog.created_at.between(month_start, next_month_start),
                Saved_Blog.user_id == user_id,
            )
        )
        count_this_month = count_this_month.scalar_one_or_none()
        pagination_metadata["new_items_this_month"] = count_this_month

        # 格式化响应数据
        formatted_items: List[Dict[str, Any]] = []
        for saved_blog, blog in items:
            self.logger.info(
                f"Processing saved_blog: {saved_blog}, blog: {blog}")
            formatted_items.append(
                {
                    "cover_url": blog.cover.thumbnail_filepath_url
                    if blog.cover
                    else None,
                    "section_slug": blog.section.slug,
                    "blog_id": blog.id,
                    "blog_slug": blog.slug,
                    "blog_title": blog.chinese_title
                    if language == Language.ZH_CN
                    else blog.english_title,
                    "saved_at": saved_blog.created_at.isoformat()
                    if saved_blog.created_at
                    else None,
                }
            )

        self.logger.info(f"Formatted items count: {len(formatted_items)}")

        # 缓存结果
        cache_data = offset_paginator.create_response_data(
            formatted_items, pagination_metadata
        )
        await redis_manager.set_async(cache_key, json.dumps(cache_data))

        return formatted_items, pagination_metadata

    async def get_recent_populor_blog(self, language: Language) -> List[Dict[str, Any]]:
        """
        获取最近受欢迎阅读量 留言点赞收藏加起来数量最多的排名前3的博客
        """

        # 缓存键
        cache_key = f"get_recent_populor_blog:lang={language}"
        cache_data = await redis_manager.get_async(cache_key)
        if cache_data:
            return json.loads(cache_data)

        # 查询博客统计数据，计算总热度（views + likes + comments + saves）
        # 只获取已发布的博客
        statement = (
            select(Blog, Blog_Stats)
            .join(Blog_Stats, Blog_Stats.blog_id == Blog.id)
            .join(Blog_Status, Blog_Status.blog_id == Blog.id)
            .options(
                joinedload(Blog.cover),
                selectinload(Blog.blog_tags).selectinload(Blog_Tag.tag),
            )
            .where(Blog_Status.is_published)
            .order_by(
                (
                    Blog_Stats.views
                    + Blog_Stats.likes
                    + Blog_Stats.comments
                    + Blog_Stats.saves
                ).desc()
            )
            .limit(9)
        )

        result = await self.db.execute(statement)
        rows = result.all()

        # 格式化响应数据
        items: List[Dict[str, Any]] = []
        for blog, stats in rows:
            items.append(
                {
                    "blog_id": blog.id,
                    "section_slug": blog.section.slug,
                    "blog_slug": blog.slug,
                    "blog_title": blog.chinese_title
                    if language == Language.ZH_CN
                    else blog.english_title,
                    "blog_description": blog.chinese_description
                    if language == Language.ZH_CN
                    else blog.english_description,
                    "cover_url": blog.cover.thumbnail_filepath_url
                    if blog.cover
                    else None,
                    "blog_tags": [
                        {
                            "tag_id": tag.id,
                            "tag_title": tag.tag.chinese_title
                            if language == Language.ZH_CN
                            else tag.tag.english_title,
                        }
                        for tag in blog.blog_tags
                    ],
                    "blog_stats": {
                        "views": stats.views,
                        "likes": stats.likes,
                        "comments": stats.comments,
                        "saves": stats.saves,
                    },
                    "created_at": blog.created_at.isoformat()
                    if blog.created_at
                    else None,
                }
            )

        # 缓存结果（缓存1小时）
        await redis_manager.set_async(cache_key, json.dumps(items), ex=3600)

        return items


def get_blog_crud(db: AsyncSession = Depends(mysql_manager.get_db)) -> BlogCrud:
    return BlogCrud(db)
