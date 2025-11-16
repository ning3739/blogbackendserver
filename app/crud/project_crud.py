import json
import hashlib
from slugify import slugify
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException, Depends, logger
from sqlalchemy import exists, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlmodel import select, insert, update, delete
from app.models.project_model import (
    ProjectType,
    Project,
    Project_Attachment,
    Project_Monetization,
)
from app.core.i18n.i18n import Language, get_message
from app.models.payment_model import Payment_Record, Tax
from app.core.database.mysql import mysql_manager
from app.core.database.redis import redis_manager
from app.core.logger import logger_manager
from app.utils.offset_pagination import offset_paginator
from app.utils.agent import agent_utils
from app.tasks.large_content_translation_task import large_content_translation_task
from app.schemas.common import LargeContentTranslationType


def convert_project_type(type_name: str) -> str:
    """将项目类型转换为中文"""
    if type_name == "web":
        return "网页应用"
    elif type_name == "mobile":
        return "移动应用"
    elif type_name == "desktop":
        return "桌面应用"
    elif type_name == "other":
        return "其他应用"
    else:
        return type_name


class ProjectCrud:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = logger_manager.get_logger(__name__)

    async def _get_tax(self) -> Optional[int]:
        statement = select(Tax.id).where(
            Tax.tax_name == "GST",
            Tax.is_active == True
        )
        result = await self.db.execute(statement)
        tax_id = result.scalar_one_or_none()
        if tax_id:
            self.logger.info(f"Found active GST tax with id: {tax_id}")
        else:
            self.logger.warning("No active GST tax found in database")
        return tax_id

    async def _get_project_by_id(self, project_id: int) -> Optional[Project]:
        statement = (
            select(Project)
            .options(
                joinedload(Project.cover),
                joinedload(Project.project_attachments),
                joinedload(Project.project_monetization).joinedload(
                    Project_Monetization.tax
                ),
                joinedload(Project.seo),
            )
            .where(Project.id == project_id)
        )
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def get_project_by_slug(self, slug: str) -> Optional[Project]:
        statement = select(Project).options(
            joinedload(Project.cover),
            joinedload(Project.project_attachments),
            joinedload(Project.project_monetization).joinedload(
                Project_Monetization.tax
            ),
        ).where(Project.slug == slug)
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def _get_project_by_chinese_title(self, chinese_title: str) -> bool:
        statement = select(exists(select(Project.id)).where(
            Project.chinese_title == chinese_title))
        result = await self.db.execute(statement)
        return bool(result.scalar_one())

    async def get_project_lists(
        self, language: Language, page: int = 1, size: int = 20, published_only: bool = True
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Get project lists with traditional pagination

        Args:
            language: Language for the response
            page: Page number
            size: Number of items per page
            published_only: If True, only return published projects. If False, return all projects.
        """
        # Validate pagination parameters
        try:
            page, size = offset_paginator.validate_pagination_params(
                page, size)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=get_message("common.invalidRequest", language),
            )

        # Cache key
        cache_key = f"project_lists:lang={language}:page={page}:size={size}:published_only={published_only}"
        cache_data = await redis_manager.get_async(cache_key)
        if cache_data:
            payload = json.loads(cache_data)
            return payload.get("items", []), payload.get("pagination", {})

        # Set filters based on published_only parameter
        filters = {"is_published": True} if published_only else {}

        items, pagination_metadata = await offset_paginator.get_paginated_result(
            db=self.db,
            model_class=Project,
            page=page,
            size=size,
            order_by=[Project.created_at.desc(), Project.id.desc()],
            filters=filters,
            join_options=[joinedload(Project.cover)],
            language=language,
        )
        # 计算本月的项目数量
        if published_only is False:
            current_month = datetime.now(timezone.utc).month
            current_year = datetime.now(timezone.utc).year
            count_this_month = await self.db.execute(
                select(func.count(Project.id)).where(Project.created_at.between(datetime(
                    current_year, current_month, 1), datetime(current_year, current_month + 1, 1)))
            )
            count_this_month = count_this_month.scalar_one_or_none()

            # 计算更新的项目数量
            count_updated = await self.db.execute(
                select(func.count(Project.id)).where(Project.updated_at.between(datetime(
                    current_year, current_month, 1), datetime(current_year, current_month + 1, 1)))
            )
            count_updated = count_updated.scalar_one_or_none()

            pagination_metadata["new_items_this_month"] = count_this_month
            pagination_metadata["updated_items_this_month"] = count_updated

        response_items = [
            {
                "project_id": project.id,
                "project_slug": project.slug,

                "cover_url": project.cover.thumbnail_filepath_url
                if project.cover
                else None,
                "created_at": project.created_at.isoformat(),
                "updated_at": project.updated_at.isoformat()
                if project.updated_at
                else None,
            }
            for project in items
        ]

        if published_only is True:
            for i, project in enumerate(items):
                response_items[i].update({
                    "project_type": convert_project_type(project.type.name) if language == Language.ZH_CN else project.type.name.capitalize(),
                    "project_name": project.chinese_title.capitalize()
                    if language == Language.ZH_CN
                    else project.english_title.capitalize(),
                    "project_description": project.chinese_description.capitalize()
                    if language == Language.ZH_CN
                    else project.english_description.capitalize(),
                })

        else:
            for i, project in enumerate(items):
                response_items[i].update({
                    "project_type": convert_project_type(project.type.name),
                    "is_published": project.is_published,
                    "project_name": project.chinese_title,
                    "project_description": project.chinese_description,
                })

        # Cache result
        cache_data = offset_paginator.create_response_data(
            response_items, pagination_metadata
        )
        await redis_manager.set_async(cache_key, json.dumps(cache_data))

        return response_items, pagination_metadata

    async def create_project(
        self,
        language: Language,
        project_type: ProjectType,
        section_id: int,
        seo_id: Optional[int],
        cover_id: int,
        chinese_title: str,
        chinese_description: str,
        chinese_content: dict,
        attachment_id: Optional[int],
        price: float = 0.0,
    ) -> str:
        if await self._get_project_by_chinese_title(chinese_title):
            raise HTTPException(
                status_code=400,
                detail=get_message(
                    key="project.common.projectAlreadyExists", lang=language
                ),
            )

        english_title = await agent_utils.translate(text=chinese_title)
        english_description = await agent_utils.translate(text=chinese_description)

        # 生成slug并限制长度
        slug = slugify(english_title, max_length=250)  # 限制在250字符以内，留一些缓冲

        import json
        content_str = json.dumps(
            chinese_content, sort_keys=True, ensure_ascii=False)
        content_hash = hashlib.sha256(content_str.encode()).hexdigest()

        result = await self.db.execute(
            insert(Project).values(
                type=project_type,
                section_id=section_id,
                seo_id=seo_id,
                cover_id=cover_id,
                is_published=False,  # 默认不发布项目
                chinese_title=chinese_title,
                english_title=english_title,
                slug=slug,
                chinese_description=chinese_description,
                english_description=english_description,
                chinese_content=chinese_content,
                content_hash=content_hash,
            )
        )
        await self.db.commit()

        # 获取新创建的项目ID
        new_project_id = result.inserted_primary_key[0]

        if attachment_id:
            await self.db.execute(
                insert(Project_Attachment).values(
                    project_id=new_project_id,
                    attachment_id=attachment_id,
                )
            )

        tax_result = await self._get_tax()
        tax_id = tax_result if tax_result else None

        await self.db.execute(
            insert(Project_Monetization).values(
                project_id=new_project_id,
                price=price,
                tax_id=tax_id,
            )
        )

        await self.db.commit()

        # project celery task 来处理English content 的处理
        large_content_translation_task.delay(
            content=chinese_content, content_type=LargeContentTranslationType.PROJECT, content_id=new_project_id)

        # 清理缓存
        await redis_manager.delete_pattern_async("project_lists:*")

        return slug

    async def update_project(
        self,
        language: Language,
        project_slug: str,
        project_type: ProjectType,
        seo_id: Optional[int],
        cover_id: int,
        chinese_title: str,
        chinese_description: str,
        chinese_content: dict,
        attachment_id: Optional[int],
        price: float = 0.0,
    ) -> str:
        # check if project exists
        existing_project = await self.get_project_by_slug(project_slug)
        if not existing_project:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    key="project.common.projectNotFound", lang=language),
            )

        if chinese_title and chinese_title != existing_project.chinese_title:
            english_title = await agent_utils.translate(text=chinese_title)
            # 生成slug并限制长度
            slug = slugify(english_title, max_length=250)  # 限制在250字符以内，留一些缓冲
        else:
            english_title = existing_project.english_title
            slug = existing_project.slug

        if chinese_description and chinese_description != existing_project.chinese_description:
            english_description = await agent_utils.translate(text=chinese_description)
        else:
            english_description = existing_project.english_description

        # 计算content_hash
        import json
        content_str = json.dumps(
            chinese_content, sort_keys=True, ensure_ascii=False)
        content_hash = hashlib.sha256(content_str.encode()).hexdigest()

        # update project
        result = await self.db.execute(
            update(Project)
            .where(Project.id == existing_project.id)
            .values(
                type=project_type,
                seo_id=seo_id,
                cover_id=cover_id,
                is_published=True,  # 确保更新时也设置发布状态
                chinese_title=chinese_title,
                english_title=english_title,
                slug=slug,
                chinese_description=chinese_description,
                english_description=english_description,
                chinese_content=chinese_content,
                content_hash=content_hash,
            )
        )
        await self.db.commit()

        if attachment_id:
            # 检查是否已存在附件记录
            existing_attachment = await self.db.execute(
                select(Project_Attachment).where(
                    Project_Attachment.project_id == existing_project.id
                )
            )
            existing_attachment = existing_attachment.scalar_one_or_none()

            if existing_attachment:
                # 更新现有附件
                await self.db.execute(
                    update(Project_Attachment)
                    .where(Project_Attachment.project_id == existing_project.id)
                    .values(attachment_id=attachment_id)
                )
            else:
                # 创建新附件记录
                await self.db.execute(
                    insert(Project_Attachment).values(
                        project_id=existing_project.id,
                        attachment_id=attachment_id,
                    )
                )

        # 获取tax_id
        tax_result = await self._get_tax()
        tax_id = tax_result if tax_result else None

        await self.db.execute(
            update(Project_Monetization)
            .where(Project_Monetization.project_id == existing_project.id)
            .values(price=price, tax_id=tax_id)
        )
        await self.db.commit()

        # project celery task 来处理English content 的处理
        if existing_project.content_hash != content_hash:
            large_content_translation_task.delay(
                content=chinese_content, content_type=LargeContentTranslationType.PROJECT, content_id=existing_project.id)

        # 清理缓存
        await redis_manager.delete_pattern_async("project_lists:*")
        await redis_manager.delete_pattern_async("project_details:*")
        await redis_manager.delete_pattern_async("project_seo:*")

        return slug

    async def publish_Or_Unpublish_project(
        self, language: Language, project_id: int, is_publish: bool = True
    ) -> bool:
        project = await self._get_project_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    key="project.common.projectNotFound", lang=language),
            )

        await self.db.execute(
            update(Project)
            .where(Project.id == project.id)
            .values(is_published=is_publish)
        )
        await self.db.commit()

        # 清理缓存
        await redis_manager.delete_pattern_async("project_lists:*")
        await redis_manager.delete_pattern_async(f"project_details:lang={language}:project_id={project_id}:*")

        return True

    async def get_project_details(
        self, language: Language, project_slug: str, user_id: Optional[int] = None, is_editor: Optional[bool] = False
    ) -> Dict[str, Any]:
        cache_key = (
            f"project_details:lang={language}:project_slug={project_slug}:user_id={user_id}:is_editor={is_editor}"
        )
        cache_result = await redis_manager.get_async(cache_key)
        if cache_result:
            return json.loads(cache_result)

        project = await self.get_project_by_slug(project_slug)
        if not project:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    key="project.common.projectNotFound", lang=language),
            )

        payment_status = None
        if user_id:
            payment_record = await self.db.execute(
                select(Payment_Record)
                .where(
                    Payment_Record.project_id == project.id,
                    Payment_Record.user_id == user_id,
                )
                .order_by(Payment_Record.created_at.desc())
                .limit(1)
            )
            payment_record = payment_record.scalar_one_or_none()
            payment_status = payment_record.payment_status if payment_record else None

        # 获取税费信息
        tax_rate = (
            project.project_monetization.tax.tax_rate
            if project.project_monetization.tax
            else 0.0
        )

        # 调试信息
        self.logger.debug(
            f"Project {project.id} tax info: "
            f"tax_id={project.project_monetization.tax_id if project.project_monetization else None}, "
            f"tax={project.project_monetization.tax.tax_name if project.project_monetization and project.project_monetization.tax else None}, "
            f"tax_rate={tax_rate}"
        )
        project_price = (
            project.project_monetization.price if project.project_monetization else 0.0
        )
        tax_amount = tax_rate * project_price
        final_amount = tax_amount + project_price

        if is_editor is True:
            response = {
                "project_id": project.id,
                "project_type": project.type.value,  # 添加原始type值用于编辑
                "section_id": project.section_id,  # 添加section_id用于编辑
                "seo_id": project.seo_id,  # 添加seo_id用于编辑
                "cover_id": project.cover_id,  # 添加cover_id用于编辑
                "cover_url": project.cover.thumbnail_filepath_url
                if project.cover
                else None,
                "chinese_title": project.chinese_title,  # 添加原始中文标题
                "chinese_description": project.chinese_description,  # 添加原始中文描述
                "chinese_content": project.chinese_content,  # 添加原始中文内容
                "project_price": project.project_monetization.price
                if project.project_monetization
                else 0.0,
                "attachment_id": project.project_attachments.attachment_id,
                "attachment_url": project.project_attachments.attachment.original_filepath_url
                if project.project_attachments.attachment
                else None,
            }
        else:
            response = {
                "project_id": project.id,
                "project_slug": project.slug,
                "cover_url": project.cover.thumbnail_filepath_url
                if project.cover
                else None,
                "project_name": project.chinese_title.capitalize()
                if language == Language.ZH_CN
                else project.english_title.capitalize(),
                "project_description": project.chinese_description.capitalize()
                if language == Language.ZH_CN
                else project.english_description.capitalize(),
                "project_content": project.chinese_content
                if language == Language.ZH_CN
                else project.english_content,
                "project_price": project.project_monetization.price
                if project.project_monetization
                else 0.0,
                "tax_name": project.project_monetization.tax.tax_name
                if project.project_monetization.tax
                else None,
                "tax_rate": tax_rate,
                "tax_amount": tax_amount,
                "final_amount": final_amount,
                "attachment_id": project.project_attachments.attachment_id,
                "created_at": project.created_at.isoformat(),
                "updated_at": project.updated_at.isoformat()
                if project.updated_at
                else None,
            }

        if payment_status:
            response["payment_status"] = payment_status.name

        # 缓存数据
        await redis_manager.set_async(cache_key, json.dumps(response))

        return response

    async def get_project_details_seo(
        self, language: Language, project_slug: int
    ) -> Dict[str, Any]:
        cache_key = f"project_seo:lang={language}:project_slug={project_slug}"
        cache_result = await redis_manager.get_async(cache_key)
        if cache_result:
            return json.loads(cache_result)

        project = await self.get_project_by_slug(project_slug)
        if not project:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    key="project.common.projectNotFound", lang=language),
            )

        if not project.seo:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    key="seo.common.seoNotFound", lang=language),
            )

        response = {
            "title": {
                "zh": project.seo.chinese_title.capitalize(),
                "en": project.seo.english_title.capitalize(),
            },
            "description": {
                "zh": project.seo.chinese_description.capitalize(),
                "en": project.seo.english_description.capitalize(),
            },
            "keywords": {
                "zh": project.seo.chinese_keywords.capitalize(),
                "en": project.seo.english_keywords.capitalize(),
            },
        }

        # 缓存数据
        await redis_manager.set_async(cache_key, json.dumps(response))

        return response

    async def delete_project(self, language: Language, project_id: int) -> bool:
        project = await self._get_project_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    key="project.common.projectNotFound", lang=language),
            )

        if project.project_monetization.price > 0:
            raise HTTPException(
                status_code=400,
                detail=get_message(
                    key="project.common.projectHasMonetization", lang=language
                ),
            )

        await self.db.execute(delete(Project).where(Project.id == project_id))
        await self.db.commit()

        # 清理缓存
        await redis_manager.delete_pattern_async("project_lists:*")

        return True


def get_project_crud(db: AsyncSession = Depends(mysql_manager.get_db)) -> ProjectCrud:
    return ProjectCrud(db)
