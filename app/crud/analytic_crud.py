import json
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func
from app.models.user_model import User
from app.models.blog_model import Blog, Blog_Status, Blog_Stats, Blog_Tag
from app.models.project_model import Project, ProjectType
from app.models.payment_model import Payment_Record, PaymentStatus, PaymentType
from app.models.media_model import Media
from app.models.section_model import Section
from app.models.tag_model import Tag
from app.core.logger import logger_manager
from app.crud.project_crud import convert_project_type
from app.core.database.mysql import mysql_manager
from app.core.database.redis import redis_manager


class AnalyticCrud:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = logger_manager.get_logger(__name__)

    def _get_date_range(self, period: str = "month") -> tuple[datetime, datetime]:
        """获取时间范围"""
        now = datetime.now(timezone.utc)
        if period == "day":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "month":
            start = now.replace(day=1, hour=0, minute=0,
                                second=0, microsecond=0)
        elif period == "year":
            start = now.replace(
                month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
        else:
            start = now.replace(day=1, hour=0, minute=0,
                                second=0, microsecond=0)

        return start, now

    async def get_user_location(self) -> List[Dict[str, Any]]:
        """Get all users' location (longitude and latitude)"""
        cache_key = "all_users_location"
        cached_data = await redis_manager.get_async(cache_key)
        if cached_data:
            return json.loads(cached_data)

        statement = select(User.longitude, User.latitude, User.city)
        result = await self.db.execute(statement)
        rows = result.all()

        locations = []
        for row in rows:
            if row.longitude is not None and row.latitude is not None:
                locations.append(
                    {
                        "city": row.city,
                        "longitude": row.longitude,
                        "latitude": row.latitude,
                    }
                )

        await redis_manager.set_async(cache_key, json.dumps(locations))
        return locations

    async def get_blog_statistics(self) -> Dict[str, Any]:
        """获取博客统计数据"""
        cache_key = "analytics_blog_statistics"
        cached_data = await redis_manager.get_async(cache_key)
        if cached_data:
            return json.loads(cached_data)

        # 总博客数
        total_blogs = await self.db.execute(select(func.count(Blog.id)))
        total_blogs = total_blogs.scalar_one()

        # 已发布博客数
        published_blogs = await self.db.execute(
            select(func.count(Blog_Status.id)).where(Blog_Status.is_published)
        )
        published_blogs = published_blogs.scalar_one()

        # 归档博客数
        archived_blogs = await self.db.execute(
            select(func.count(Blog_Status.id)).where(Blog_Status.is_archived)
        )
        archived_blogs = archived_blogs.scalar_one()

        # 精选博客数
        featured_blogs = await self.db.execute(
            select(func.count(Blog_Status.id)).where(Blog_Status.is_featured)
        )
        featured_blogs = featured_blogs.scalar_one()

        # 本月新增博客
        start_date, end_date = self._get_date_range("month")
        new_blogs_this_month = await self.db.execute(
            select(func.count(Blog.id)).where(
                Blog.created_at >= start_date, Blog.created_at <= end_date
            )
        )
        new_blogs_this_month = new_blogs_this_month.scalar_one()

        # 本月更新博客
        updated_blogs_this_month = await self.db.execute(
            select(func.count(Blog.id)).where(
                Blog.updated_at >= start_date, Blog.updated_at <= end_date
            )
        )
        updated_blogs_this_month = updated_blogs_this_month.scalar_one()

        # 总浏览量、点赞、评论、收藏
        stats_totals = await self.db.execute(
            select(
                func.sum(Blog_Stats.views),
                func.sum(Blog_Stats.likes),
                func.sum(Blog_Stats.comments),
                func.sum(Blog_Stats.saves),
            )
        )
        stats_row = stats_totals.first()

        # 各栏目博客分布
        section_distribution = await self.db.execute(
            select(Section.chinese_title, func.count(Blog.id))
            .join(Blog, Blog.section_id == Section.id)
            .group_by(Section.id, Section.chinese_title)
            .order_by(func.count(Blog.id).desc())
        )
        section_dist = [
            {"section": row[0], "count": row[1]} for row in section_distribution.all()
        ]

        result = {
            "total_blogs": total_blogs,
            "published_blogs": published_blogs,
            "archived_blogs": archived_blogs,
            "featured_blogs": featured_blogs,
            "new_blogs_this_month": new_blogs_this_month,
            "updated_blogs_this_month": updated_blogs_this_month,
            "total_views": int(stats_row[0] or 0),
            "total_likes": int(stats_row[1] or 0),
            "total_comments": int(stats_row[2] or 0),
            "total_saves": int(stats_row[3] or 0),
            "section_distribution": section_dist,
        }

        await redis_manager.set_async(cache_key, json.dumps(result), ex=300)
        return result

    async def get_top_ten_blog_performers(self) -> Dict[str, Any]:
        """获取博客热门前十排行"""
        cache_key = "analytics_top_ten_blog_performers"
        cached_data = await redis_manager.get_async(cache_key)
        if cached_data:
            return json.loads(cached_data)

        # 最多浏览
        top_views = await self.db.execute(
            select(Blog.slug, Section.slug,
                   Blog.chinese_title, Blog_Stats.views)
            .join(Blog_Stats, Blog_Stats.blog_id == Blog.id)
            .join(Section, Section.id == Blog.section_id)
            .order_by(Blog_Stats.views.desc())
            .limit(10)
        )
        top_views_list = [
            {
                "blog_slug": row[0],
                "section_slug": row[1],
                "title": row[2],
                "views": row[3],
            }
            for row in top_views.all()
        ]

        # 最多点赞
        top_likes = await self.db.execute(
            select(Blog.slug, Section.slug,
                   Blog.chinese_title, Blog_Stats.likes)
            .join(Blog_Stats, Blog_Stats.blog_id == Blog.id)
            .join(Section, Section.id == Blog.section_id)
            .order_by(Blog_Stats.likes.desc())
            .limit(10)
        )
        top_likes_list = [
            {
                "blog_slug": row[0],
                "section_slug": row[1],
                "title": row[2],
                "likes": row[3],
            }
            for row in top_likes.all()
        ]

        # 最多评论
        top_comments = await self.db.execute(
            select(Blog.slug, Section.slug,
                   Blog.chinese_title, Blog_Stats.comments)
            .join(Blog_Stats, Blog_Stats.blog_id == Blog.id)
            .join(Section, Section.id == Blog.section_id)
            .order_by(Blog_Stats.comments.desc())
            .limit(10)
        )
        top_comments_list = [
            {
                "blog_slug": row[0],
                "section_slug": row[1],
                "title": row[2],
                "comments": row[3],
            }
            for row in top_comments.all()
        ]

        # 最多收藏
        top_saves = await self.db.execute(
            select(Blog.slug, Section.slug,
                   Blog.chinese_title, Blog_Stats.saves)
            .join(Blog_Stats, Blog_Stats.blog_id == Blog.id)
            .join(Section, Section.id == Blog.section_id)
            .order_by(Blog_Stats.saves.desc())
            .limit(10)
        )
        top_saves_list = [
            {
                "blog_slug": row[0],
                "section_slug": row[1],
                "title": row[2],
                "saves": row[3],
            }
            for row in top_saves.all()
        ]

        result = {
            "top_views": top_views_list,
            "top_likes": top_likes_list,
            "top_comments": top_comments_list,
            "top_saves": top_saves_list,
        }

        await redis_manager.set_async(cache_key, json.dumps(result), ex=300)
        return result

    async def get_tag_statistics(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取标签统计（热门标签）"""
        cache_key = f"analytics_tag_statistics_{limit}"
        cached_data = await redis_manager.get_async(cache_key)
        if cached_data:
            return json.loads(cached_data)

        tag_stats = await self.db.execute(
            select(Tag.slug, Tag.chinese_title, func.count(Blog_Tag.id))
            .join(Blog_Tag, Blog_Tag.tag_id == Tag.id)
            .group_by(Tag.id, Tag.slug, Tag.chinese_title)
            .order_by(func.count(Blog_Tag.id).desc())
            .limit(limit)
        )

        result = [
            {
                "tag_slug": row[0],
                "chinese_title": row[1],
                "blog_count": row[2],
            }
            for row in tag_stats.all()
        ]

        await redis_manager.set_async(cache_key, json.dumps(result), ex=300)
        return result

    async def get_project_statistics(self) -> Dict[str, Any]:
        """获取项目统计数据"""
        cache_key = "analytics_project_statistics"
        cached_data = await redis_manager.get_async(cache_key)
        if cached_data:
            return json.loads(cached_data)

        # 总项目数
        total_projects = await self.db.execute(select(func.count(Project.id)))
        total_projects = total_projects.scalar_one()

        # 已发布项目数
        published_projects = await self.db.execute(
            select(func.count(Project.id)).where(Project.is_published)
        )
        published_projects = published_projects.scalar_one()

        # 本月新增项目
        start_date, end_date = self._get_date_range("month")
        new_projects_this_month = await self.db.execute(
            select(func.count(Project.id)).where(
                Project.created_at >= start_date, Project.created_at <= end_date
            )
        )
        new_projects_this_month = new_projects_this_month.scalar_one()

        # 项目类型分布
        type_distribution = await self.db.execute(
            select(Project.type, func.count(Project.id)).group_by(Project.type)
        )
        type_dist = {
            convert_project_type(ProjectType(row[0]).name): row[1]
            for row in type_distribution.all()
        }

        # 各栏目项目分布
        section_distribution = await self.db.execute(
            select(Section.chinese_title, func.count(Project.id))
            .join(Project, Project.section_id == Section.id)
            .where(Project.section_id.isnot(None))
            .group_by(Section.id, Section.chinese_title)
            .order_by(func.count(Project.id).desc())
        )
        section_dist = [
            {"section": row[0], "count": row[1]} for row in section_distribution.all()
        ]

        result = {
            "total_projects": total_projects,
            "published_projects": published_projects,
            "new_projects_this_month": new_projects_this_month,
            "type_distribution": type_dist,
            "section_distribution": section_dist,
        }

        await redis_manager.set_async(cache_key, json.dumps(result), ex=300)
        return result

    async def get_payment_statistics(self) -> Dict[str, Any]:
        """获取支付统计数据"""
        cache_key = "analytics_payment_statistics"
        cached_data = await redis_manager.get_async(cache_key)
        if cached_data:
            return json.loads(cached_data)

        # 总收入（仅成功的支付）
        total_revenue = await self.db.execute(
            select(func.sum(Payment_Record.amount)).where(
                Payment_Record.payment_status == PaymentStatus.success
            )
        )
        total_revenue = float(total_revenue.scalar_one() or 0)

        # 总支付记录数
        total_payments = await self.db.execute(select(func.count(Payment_Record.id)))
        total_payments = total_payments.scalar_one()

        # 成功支付数
        successful_payments = await self.db.execute(
            select(func.count(Payment_Record.id)).where(
                Payment_Record.payment_status == PaymentStatus.success
            )
        )
        successful_payments = successful_payments.scalar_one()

        # 本月收入
        start_date, end_date = self._get_date_range("month")
        monthly_revenue = await self.db.execute(
            select(func.sum(Payment_Record.amount)).where(
                Payment_Record.payment_status == PaymentStatus.success,
                Payment_Record.created_at >= start_date,
                Payment_Record.created_at <= end_date,
            )
        )
        monthly_revenue = float(monthly_revenue.scalar_one() or 0)

        # 本月支付数
        monthly_payments = await self.db.execute(
            select(func.count(Payment_Record.id)).where(
                Payment_Record.created_at >= start_date,
                Payment_Record.created_at <= end_date,
            )
        )
        monthly_payments = monthly_payments.scalar_one()

        # 本年收入
        year_start, _ = self._get_date_range("year")
        yearly_revenue = await self.db.execute(
            select(func.sum(Payment_Record.amount)).where(
                Payment_Record.payment_status == PaymentStatus.success,
                Payment_Record.created_at >= year_start,
                Payment_Record.created_at <= end_date,
            )
        )
        yearly_revenue = float(yearly_revenue.scalar_one() or 0)

        # 支付方式分布
        payment_type_distribution = await self.db.execute(
            select(Payment_Record.payment_type, func.count(Payment_Record.id)).group_by(
                Payment_Record.payment_type
            )
        )
        payment_type_dist = {
            PaymentType(row[0]).name.capitalize(): row[1]
            for row in payment_type_distribution.all()
        }

        # 支付状态分布
        payment_status_distribution = await self.db.execute(
            select(
                Payment_Record.payment_status, func.count(Payment_Record.id)
            ).group_by(Payment_Record.payment_status)
        )
        payment_status_dist = {
            PaymentStatus(row[0]).name: row[1]
            for row in payment_status_distribution.all()
        }

        # 总税费
        total_tax = await self.db.execute(
            select(func.sum(Payment_Record.tax_amount)).where(
                Payment_Record.payment_status == PaymentStatus.success
            )
        )
        total_tax = float(total_tax.scalar_one() or 0)

        result = {
            "total_revenue": total_revenue,
            "total_payments": total_payments,
            "successful_payments": successful_payments,
            "monthly_revenue": monthly_revenue,
            "monthly_payments": monthly_payments,
            "yearly_revenue": yearly_revenue,
            "total_tax": total_tax,
            "payment_type_distribution": payment_type_dist,
            "payment_status_distribution": payment_status_dist,
        }

        await redis_manager.set_async(cache_key, json.dumps(result), ex=300)
        return result

    async def get_top_ten_revenue_projects(self) -> List[Dict[str, Any]]:
        """获取收入最高的前十项目"""
        cache_key = "analytics_top_ten_revenue_projects"
        cached_data = await redis_manager.get_async(cache_key)
        if cached_data:
            return json.loads(cached_data)

        top_projects = await self.db.execute(
            select(
                Project.slug,
                Project.chinese_title,
                func.sum(Payment_Record.amount).label("total_revenue"),
                func.count(Payment_Record.id).label("payment_count"),
            )
            .join(Payment_Record, Payment_Record.project_id == Project.id)
            .where(Payment_Record.payment_status == PaymentStatus.success)
            .group_by(Project.id, Project.slug, Project.chinese_title)
            .order_by(func.sum(Payment_Record.amount).desc())
            .limit(10)
        )

        result = [
            {
                "project_slug": row[0],
                "title": row[1],
                "total_revenue": float(row[2]),
                "payment_count": row[3],
            }
            for row in top_projects.all()
        ]

        await redis_manager.set_async(cache_key, json.dumps(result), ex=300)
        return result

    async def get_media_statistics(self) -> Dict[str, Any]:
        """获取媒体文件统计"""
        cache_key = "analytics_media_statistics"
        cached_data = await redis_manager.get_async(cache_key)
        if cached_data:
            return json.loads(cached_data)

        # 总文件数
        total_media = await self.db.execute(select(func.count(Media.id)))
        total_media = total_media.scalar_one()

        # 头像数量
        avatar_count = await self.db.execute(
            select(func.count(Media.id)).where(Media.is_avatar)
        )
        avatar_count = avatar_count.scalar_one()

        # 本月新增文件
        start_date, end_date = self._get_date_range("month")
        new_media_this_month = await self.db.execute(
            select(func.count(Media.id)).where(
                Media.created_at >= start_date, Media.created_at <= end_date
            )
        )
        new_media_this_month = new_media_this_month.scalar_one()

        result = {
            "total_media": total_media,
            "avatar_count": avatar_count,
            "new_media_this_month": new_media_this_month,
        }

        await redis_manager.set_async(cache_key, json.dumps(result), ex=300)
        return result

    async def get_growth_trends(self, days: int = 30) -> Dict[str, Any]:
        """获取增长趋势数据（最近N天）"""
        cache_key = f"analytics_growth_trends_{days}"
        cached_data = await redis_manager.get_async(cache_key)
        if cached_data:
            return json.loads(cached_data)

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        # 用户增长趋势
        user_growth = await self.db.execute(
            select(
                func.date(User.created_at).label("date"),
                func.count(User.id).label("count"),
            )
            .where(User.created_at >= start_date)
            .group_by(func.date(User.created_at))
            .order_by(func.date(User.created_at))
        )
        user_trend = [
            {"date": row[0].isoformat(), "count": row[1]} for row in user_growth.all()
        ]

        # 博客增长趋势
        blog_growth = await self.db.execute(
            select(
                func.date(Blog.created_at).label("date"),
                func.count(Blog.id).label("count"),
            )
            .where(Blog.created_at >= start_date)
            .group_by(func.date(Blog.created_at))
            .order_by(func.date(Blog.created_at))
        )
        blog_trend = [
            {"date": row[0].isoformat(), "count": row[1]} for row in blog_growth.all()
        ]

        # 收入趋势
        revenue_growth = await self.db.execute(
            select(
                func.date(Payment_Record.created_at).label("date"),
                func.sum(Payment_Record.amount).label("revenue"),
            )
            .where(
                Payment_Record.created_at >= start_date,
                Payment_Record.payment_status == PaymentStatus.success,
            )
            .group_by(func.date(Payment_Record.created_at))
            .order_by(func.date(Payment_Record.created_at))
        )
        revenue_trend = [
            {"date": row[0].isoformat(), "revenue": float(row[1])}
            for row in revenue_growth.all()
        ]

        result = {
            "user_growth": user_trend,
            "blog_growth": blog_trend,
            "revenue_growth": revenue_trend,
        }

        await redis_manager.set_async(cache_key, json.dumps(result), ex=300)
        return result

    async def get_user_statistics(self) -> Dict[str, Any]:
        """获取用户统计数据"""
        cache_key = "analytics_user_statistics"
        cached_data = await redis_manager.get_async(cache_key)
        if cached_data:
            return json.loads(cached_data)

        # 总用户数
        total_users = await self.db.execute(select(func.count(User.id)))
        total_users = total_users.scalar_one()

        # 活跃用户数（is_active 为 True 且未删除的用户）
        active_users = await self.db.execute(
            select(func.count(User.id)).where(
                User.is_active == True, User.is_deleted == False
            )
        )
        active_users = active_users.scalar_one()

        # 本月新增用户
        start_date, end_date = self._get_date_range("month")
        new_users_this_month = await self.db.execute(
            select(func.count(User.id)).where(
                User.created_at >= start_date, User.created_at <= end_date
            )
        )
        new_users_this_month = new_users_this_month.scalar_one()

        result = {
            "total_users": total_users,
            "active_users": active_users,
            "new_users_this_month": new_users_this_month,
        }

        await redis_manager.set_async(cache_key, json.dumps(result), ex=300)
        return result

    async def get_overview_statistics(self) -> Dict[str, Any]:
        """获取总览统计数据（汇总所有关键指标）"""
        cache_key = "analytics_overview_statistics"
        cached_data = await redis_manager.get_async(cache_key)
        if cached_data:
            return json.loads(cached_data)

        # 并发获取各项统计
        user_stats = await self.get_user_statistics()
        blog_stats = await self.get_blog_statistics()
        project_stats = await self.get_project_statistics()
        payment_stats = await self.get_payment_statistics()
        media_stats = await self.get_media_statistics()

        result = {
            "users": {
                "total": user_stats["total_users"],
            },
            "blogs": {
                "total": blog_stats["total_blogs"],
            },
            "projects": {
                "total": project_stats["total_projects"],
            },
            "payments": {
                "total_revenue": payment_stats["total_revenue"],
            },
            "media": {
                "total": media_stats["total_media"],
            },
        }

        await redis_manager.set_async(cache_key, json.dumps(result), ex=300)
        return result


def get_analytic_crud(db: AsyncSession = Depends(mysql_manager.get_db)) -> AnalyticCrud:
    return AnalyticCrud(db)
