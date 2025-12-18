import os
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any, Union, List, Tuple, Optional
import anyio
from fastapi import Depends, HTTPException, status, UploadFile
from app.models.media_model import MediaType
from app.core.config.settings import settings
from app.core.i18n.i18n import Language, get_message
from app.core.logger import logger_manager
from app.utils.s3_bucket import create_s3_bucket
from app.crud.media_crud import MediaCrud, get_media_crud
from app.tasks.thumbnail_task import (
    generate_image_thumbnail_task,
    generate_video_thumbnail_task,
)
from app.tasks.watermark_task import (
    generate_image_watermark_task,
    generate_video_watermark_task,
)


class MediaService:
    """媒体文件上传服务"""

    def __init__(self, media_crud: MediaCrud):
        self.media_crud = media_crud
        self.logger = logger_manager.get_logger(__name__)

    @property
    def media_type_map(self):
        """延迟加载媒体类型映射配置"""
        return {
            MediaType.image: {
                "name": "image",
                "original_path": settings.files.S3_IMAGE_ORIGINAL_PATH,
                "thumbnail_path": settings.files.S3_IMAGE_THUMBNAIL_PATH,
                "watermark_path": settings.files.S3_IMAGE_WATERMARK_PATH,
                "extensions": settings.files.S3_IMAGE_EXTENSIONS,
            },
            MediaType.video: {
                "name": "video",
                "original_path": settings.files.S3_VIDEO_ORIGINAL_PATH,
                "thumbnail_path": settings.files.S3_VIDEO_THUMBNAIL_PATH,
                "watermark_path": settings.files.S3_VIDEO_WATERMARK_PATH,
                "extensions": settings.files.S3_VIDEO_EXTENSIONS,
            },
            MediaType.audio: {
                "name": "audio",
                "original_path": settings.files.S3_AUDIO_ORIGINAL_PATH,
                "thumbnail_path": None,
                "watermark_path": None,
                "extensions": settings.files.S3_AUDIO_EXTENSIONS,
            },
            MediaType.document: {
                "name": "document",
                "original_path": settings.files.S3_DOCUMENT_ORIGINAL_PATH,
                "thumbnail_path": None,
                "watermark_path": None,
                "extensions": settings.files.S3_DOCUMENT_EXTENSIONS,
            },
            MediaType.other: {
                "name": "other",
                "original_path": settings.files.S3_OTHER_ORIGINAL_PATH,
                "thumbnail_path": None,
                "watermark_path": None,
                "extensions": settings.files.S3_OTHER_EXTENSIONS,
            },
        }

    def _get_media_type(self, file_path: Union[str, Path]) -> MediaType:
        """根据文件扩展名判断媒体类型"""
        file_ext = Path(file_path).suffix.lower().lstrip(".")

        if file_ext in settings.files.S3_IMAGE_EXTENSIONS:
            return MediaType.image
        elif file_ext in settings.files.S3_VIDEO_EXTENSIONS:
            return MediaType.video
        elif file_ext in settings.files.S3_AUDIO_EXTENSIONS:
            return MediaType.audio
        elif file_ext in settings.files.S3_DOCUMENT_EXTENSIONS:
            return MediaType.document
        else:
            return MediaType.other

    async def process_upload_files(self, files: List[UploadFile]) -> List[str]:
        """
        处理上传文件，验证扩展名并保存到临时文件

        Args:
            files: 上传的文件列表

        Returns:
            List[str]: 临时文件路径列表

        Raises:
            HTTPException: 当文件验证失败时
        """
        temp_paths: list[str] = []
        CHUNK_SIZE = 1024 * 1024  # 1MB chunks，减少内存占用

        try:
            for file in files:
                if not file.filename:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail="存在空文件名"
                    )

                # 扩展名校验
                ext = Path(file.filename).suffix.lower().lstrip(".")
                allowed_exts = set(
                    settings.files.S3_IMAGE_EXTENSIONS
                    + settings.files.S3_VIDEO_EXTENSIONS
                    + settings.files.S3_AUDIO_EXTENSIONS
                    + settings.files.S3_DOCUMENT_EXTENSIONS
                    + settings.files.S3_OTHER_EXTENSIONS
                )
                if ext not in allowed_exts:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"不允许的文件扩展名: .{ext}",
                    )

                # 创建临时文件并分块写入（异步写盘，避免阻塞事件循环）
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=Path(file.filename).suffix
                ) as temp_file:
                    temp_paths.append(temp_file.name)
                    async with await anyio.open_file(temp_file.name, "wb") as afp:
                        while True:
                            chunk = await file.read(CHUNK_SIZE)
                            if not chunk:
                                break
                            await afp.write(chunk)

            return temp_paths

        except HTTPException:
            # 清理已创建的临时文件
            for path in temp_paths:
                try:
                    os.unlink(path)
                except Exception:
                    pass
            raise
        except Exception as e:
            # 清理已创建的临时文件
            for path in temp_paths:
                try:
                    os.unlink(path)
                except Exception:
                    pass
            self.logger.error(f"文件处理失败: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="文件处理失败"
            )

    def _schedule_media_processing(
        self,
        media_uuid: str,
        s3_key: str,
        media_type: MediaType,
        width: Optional[int] = 360,
        height: Optional[int] = -1,
    ):
        """
        调度媒体处理任务（缩略图和水印）

        Args:
            media_uuid: 媒体文件UUID
            s3_key: S3文件键
            media_type: 媒体类型
        """
        try:
            # 获取媒体类型信息
            type_info = self.media_type_map.get(media_type)
            if not type_info:
                self.logger.warning(f"未知的媒体类型: {media_type}")
                return

            # 调度任务
            if media_type == MediaType.image:
                # 调度图片处理任务
                self.logger.info(f"调度图片处理任务: {media_uuid}")

                # 调用图片缩略图生成任务
                generate_image_thumbnail_task.delay(
                    input_paths=s3_key,  # 这里传递S3键，任务内部会处理
                    output_dir=type_info["thumbnail_path"],
                    width=width,
                    height=height,
                )

                # 调用图片水印生成任务
                generate_image_watermark_task.delay(
                    input_paths=s3_key,  # 这里传递S3键，任务内部会处理
                    output_dir=type_info["watermark_path"],
                    text=settings.app.APP_NAME,  # 可以根据需要自定义水印文字
                    font_size=36,
                    font_color="white",
                    opacity=0.8,
                )

            elif media_type == MediaType.video:
                # 调度视频处理任务
                self.logger.info(f"调度视频处理任务: {media_uuid}")

                # 调用视频缩略图生成任务
                generate_video_thumbnail_task.delay(
                    input_paths=s3_key,  # 这里传递S3键，任务内部会处理
                    output_dir=type_info["thumbnail_path"],
                    width=width,
                    height=height,
                    duration=10,
                )

                # 调用视频水印生成任务
                generate_video_watermark_task.delay(
                    input_paths=s3_key,  # 这里传递S3键，任务内部会处理
                    output_dir=type_info["watermark_path"],
                    text=settings.app.APP_NAME,  # 可以根据需要自定义水印文字
                    font_size=36,
                    font_color="white",
                    opacity=0.8,
                    start_time=0.0,
                    duration=None,
                )

        except Exception as e:
            self.logger.error(f"调度媒体处理任务失败: {str(e)}")

    async def upload_single_media_to_s3(
        self,
        local_file_path: Union[str, Path],
        user_id: int,
        is_avatar: bool,
        language: Language,
    ) -> Dict[str, Any]:
        """
        单文件上传实现（供统一入口复用）
        """
        local_file_path = Path(local_file_path)

        # 验证文件存在
        if not local_file_path.exists():
            raise FileNotFoundError(f"文件不存在: {local_file_path}")

        # 获取文件大小
        file_size = Path(local_file_path).stat().st_size

        # 判断媒体类型（严格校验已在路由层完成，这里仅识别类型）
        media_type = self._get_media_type(local_file_path)

        # 根据文件路径和媒体类型生成S3文件键
        # 原始文件保留原始扩展名；派生文件（缩略图/水印）统一规范：
        # - 图片：.webp
        # - 视频：.webm
        stem = local_file_path.stem
        if media_type == MediaType.image:
            original_s3_key = (
                f"{settings.files.S3_IMAGE_ORIGINAL_PATH}/{local_file_path.name}"
            )
            thumbnail_s3_key = (
                f"{settings.files.S3_IMAGE_THUMBNAIL_PATH}/{stem}_thumbnail.webp"
            )
            watermark_s3_key = (
                f"{settings.files.S3_IMAGE_WATERMARK_PATH}/{stem}_watermark.webp"
            )
        elif media_type == MediaType.video:
            original_s3_key = (
                f"{settings.files.S3_VIDEO_ORIGINAL_PATH}/{local_file_path.name}"
            )
            thumbnail_s3_key = (
                f"{settings.files.S3_VIDEO_THUMBNAIL_PATH}/{stem}_thumbnail.mp4"
            )
            watermark_s3_key = (
                f"{settings.files.S3_VIDEO_WATERMARK_PATH}/{stem}_watermark.mp4"
            )
        elif media_type == MediaType.audio:
            original_s3_key = (
                f"{settings.files.S3_AUDIO_ORIGINAL_PATH}/{local_file_path.name}"
            )
            thumbnail_s3_key = None
            watermark_s3_key = None
        elif media_type == MediaType.document:
            original_s3_key = (
                f"{settings.files.S3_DOCUMENT_ORIGINAL_PATH}/{local_file_path.name}"
            )
            thumbnail_s3_key = None
            watermark_s3_key = None
        elif media_type == MediaType.other:
            original_s3_key = (
                f"{settings.files.S3_OTHER_ORIGINAL_PATH}/{local_file_path.name}"
            )
            thumbnail_s3_key = None
            watermark_s3_key = None
        else:
            raise ValueError(f"不支持的媒体类型: {media_type}")

        # 生成唯一UUID
        media_uuid = str(uuid.uuid4())

        # 获取文件扩展名和文件名
        original_filename = local_file_path.name

        # 根据媒体类型决定ACL设置
        acl_setting = None
        if media_type == MediaType.audio or is_avatar == True:
            acl_setting = "public-read"  # 音频文件设为公开访问

        # 上传原始文件到S3
        self.logger.info(f"开始上传文件到S3: {local_file_path} -> {original_s3_key}")

        # 上传文件并构建URL（复用S3连接优化性能）
        with create_s3_bucket(verify_bucket=False) as s3_bucket:
            # 上传文件，传递ACL设置
            upload_success = s3_bucket.upload_files(
                file_paths=str(local_file_path),
                s3_keys=original_s3_key,
                acl=acl_setting,  # 根据媒体类型设置ACL
                verify=False,  # 跳过上传后校验以减少额外往返
            )

            if not upload_success:
                raise Exception(f"文件上传到S3失败: {original_s3_key}")

            # 根据ACL设置决定URL类型
            if acl_setting == "public-read":
                # 公开文件使用直接URL
                original_filepath_url = s3_bucket.get_file_url(original_s3_key)
            else:
                # 私有文件使用预签名URL
                original_filepath_url = s3_bucket.generate_presigned_url(
                    original_s3_key)

            if thumbnail_s3_key:
                thumbnail_filepath_url = s3_bucket.get_file_url(
                    thumbnail_s3_key)
            else:
                thumbnail_filepath_url = None

            if watermark_s3_key:
                watermark_filepath_url = s3_bucket.get_file_url(
                    watermark_s3_key)
            else:
                watermark_filepath_url = None

        # 准备数据库记录数据
        media_data = {
            "uuid": media_uuid,
            "user_id": user_id,
            "type": media_type,
            "is_avatar": is_avatar,
            "file_name": original_filename,
            "language": language,
            "original_filepath_url": original_filepath_url,
            "thumbnail_filepath_url": thumbnail_filepath_url,
            "watermark_filepath_url": watermark_filepath_url,
            "file_size": file_size,
        }

        # 保存到数据库（使用依赖注入的 CRUD）
        await self.media_crud.upload_media_to_s3(**media_data)

        # 对于图片和视频，异步处理缩略图和水印
        if media_type in [MediaType.image, MediaType.video]:
            self._schedule_media_processing(
                media_uuid, original_s3_key, media_type)

        self.logger.info(f"媒体文件上传成功: {media_uuid}, 类型: {media_type.name}")

        # 构建响应结果，只在有实际URL时才包含缩略图和水印字段
        response = {
            "media_uuid": media_uuid,
            "media_type": media_type.name,
            "file_name": original_filename,
            "original_filepath_url": original_filepath_url,
            "file_size": file_size,
        }

        # 只在有实际URL时才添加缩略图和水印字段
        if thumbnail_filepath_url:
            response["thumbnail_filepath_url"] = thumbnail_filepath_url
        if watermark_filepath_url:
            response["watermark_filepath_url"] = watermark_filepath_url

        return response

    async def upload_multiple_media_to_s3(
        self,
        local_file_paths: List[Union[str, Path]],
        user_id: int,
        is_avatar: bool,
        language: Language,
    ) -> Dict[str, Any]:
        """
        多文件上传实现（供统一入口复用）

        Args:
            local_file_paths: 本地文件路径列表
            user_id: 用户ID
            is_avatar: 是否为头像

        Returns:
            Dict[str, Any]: 包含上传结果的字典
        """
        items: List[Dict[str, Any]] = []
        success_count = 0

        # 先构建目标键与元信息，同时确定ACL设置
        build_cache = []
        acl_list = []
        for p in local_file_paths:
            lp = Path(p)
            mt = self._get_media_type(lp)

            # 根据媒体类型决定ACL设置
            acl_setting = "public-read" if mt == MediaType.audio else None
            acl_list.append(acl_setting)

            if mt == MediaType.image:
                original_s3_key = f"{settings.files.S3_IMAGE_ORIGINAL_PATH}/{lp.name}"
            elif mt == MediaType.video:
                original_s3_key = f"{settings.files.S3_VIDEO_ORIGINAL_PATH}/{lp.name}"
            elif mt == MediaType.audio:
                original_s3_key = f"{settings.files.S3_AUDIO_ORIGINAL_PATH}/{lp.name}"
            elif mt == MediaType.document:
                original_s3_key = (
                    f"{settings.files.S3_DOCUMENT_ORIGINAL_PATH}/{lp.name}"
                )
            else:
                original_s3_key = f"{settings.files.S3_OTHER_ORIGINAL_PATH}/{lp.name}"
            build_cache.append((lp, mt, original_s3_key))

        # 批量并发上传，传递ACL设置
        with create_s3_bucket(verify_bucket=False) as s3_bucket:
            paths = [str(lp) for (lp, _, __) in build_cache]
            keys = [osk for (_, __, osk) in build_cache]
            results = s3_bucket.upload_files(
                file_paths=paths,
                s3_keys=keys,
                metadata_list=None,
                content_types=None,
                acl=acl_list,  # 传递ACL设置列表
                max_workers=2,  # 针对2GB RAM服务器优化，降低并发
                verify=False,  # 关闭逐个 head 校验，提速
            )

        # 逐文件写库与后续任务调度（使用 s3_bucket.get_file_url 替代硬编码 base_url）
        with create_s3_bucket(verify_bucket=False) as s3_bucket:
            for i, (lp, mt, original_s3_key) in enumerate(build_cache):
                ok = (
                    results.get(original_s3_key, False)
                    if isinstance(results, dict)
                    else bool(results)
                )
                if not ok:
                    item = {
                        "success": False,
                        "error": "upload_failed",
                        "message": "文件上传失败",
                        "file_name": lp.name,
                    }
                    items.append(item)
                    continue

                media_uuid = str(uuid.uuid4())
                file_size = lp.stat().st_size
                original_filename = lp.name

                # 根据ACL设置决定URL类型
                if acl_list[i] == "public-read":
                    # 公开文件使用直接URL
                    original_url = s3_bucket.get_file_url(
                        original_s3_key) if original_s3_key else None
                else:
                    # 私有文件使用预签名URL
                    original_url = s3_bucket.generate_presigned_url(
                        original_s3_key) if original_s3_key else None

                if mt == MediaType.image:
                    stem = lp.stem
                    thumb_key = f"{settings.files.S3_IMAGE_THUMBNAIL_PATH}/{stem}_thumbnail.webp"
                    wm_key = f"{settings.files.S3_IMAGE_WATERMARK_PATH}/{stem}_watermark.webp"
                    thumbnail_url = (
                        s3_bucket.get_file_url(
                            thumb_key) if thumb_key else None
                    )
                    watermark_url = s3_bucket.get_file_url(
                        wm_key) if wm_key else None
                elif mt == MediaType.video:
                    stem = lp.stem
                    thumb_key = f"{settings.files.S3_VIDEO_THUMBNAIL_PATH}/{stem}_thumbnail.mp4"
                    wm_key = f"{settings.files.S3_VIDEO_WATERMARK_PATH}/{stem}_watermark.mp4"
                    thumbnail_url = (
                        s3_bucket.get_file_url(
                            thumb_key) if thumb_key else None
                    )
                    watermark_url = s3_bucket.get_file_url(
                        wm_key) if wm_key else None
                else:
                    thumb_key = None
                    wm_key = None
                    thumbnail_url = None
                    watermark_url = None

                await self.media_crud.upload_media_to_s3(
                    uuid=media_uuid,
                    user_id=user_id,
                    type=mt,
                    is_avatar=is_avatar,
                    file_name=original_filename,
                    language=language,
                    original_filepath_url=original_url,
                    thumbnail_filepath_url=thumbnail_url,
                    watermark_filepath_url=watermark_url,
                    file_size=file_size,
                )

                if mt in [MediaType.image, MediaType.video]:
                    self._schedule_media_processing(
                        media_uuid, original_s3_key, mt)

                # 构建响应项，只在有实际URL时才包含缩略图和水印字段
                response_item = {
                    "media_uuid": media_uuid,
                    "file_name": original_filename,
                    "media_type": mt.name,
                    "original_filepath_url": original_url,
                    "file_size": file_size,
                }

                # 只在有实际URL时才添加缩略图和水印字段
                if thumbnail_url:
                    response_item["thumbnail_filepath_url"] = thumbnail_url
                if watermark_url:
                    response_item["watermark_filepath_url"] = watermark_url

                items.append(response_item)

                success_count += 1

        total = len(local_file_paths)
        failed = total - success_count
        return {
            "total": total,
            "succeeded": success_count,
            "failed": failed,
            "items": items,
        }

    async def get_media_lists(
        self,
        user_id: int,
        page: int,
        size: int,
        language: Language,
        media_type: Optional[MediaType] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        # 从 CRUD 获取原始数据
        items, pagination_metadata = await self.media_crud.get_media_lists(
            user_id=user_id,
            page=page,
            size=size,
            language=language,
            media_type=media_type,
        )

        # 在 service 层处理预签名 URL（使用单个 S3 连接优化性能）
        response_items = []
        with create_s3_bucket(verify_bucket=False) as s3_bucket:
            for item in items:
                response_item = item.copy()

                # 根据媒体类型决定是否需要预签名
                media_type_str = item.get("media_type")  # 从CRUD层获取的是字符串格式
                if media_type_str == "audio":
                    # 音频文件使用直接URL（因为上传时设为公开）
                    response_item["original_filepath_url"] = item["original_filepath_url"]
                else:
                    # 其他文件类型使用预签名URL
                    original_key = s3_bucket.extract_s3_key(
                        item["original_filepath_url"])
                    response_item["original_filepath_url"] = (
                        s3_bucket.generate_presigned_url(original_key)
                        if original_key
                        else None
                    )

                response_items.append(response_item)

        return response_items, pagination_metadata

    async def download_media_from_s3(
        self,
        media_id: int,
        language: Language,
    ) -> str:
        """
        从S3下载媒体文件到本地临时目录
        简化参数，只使用media_id和user_id，提升性能
        """
        # 获取媒体信息和原始文件URL
        media_info = await self.media_crud.get_media(media_id=media_id)
        if not media_info:
            raise HTTPException(
                status_code=404,
                detail=get_message("media.common.mediaNotFound", language),
            )

        original_filepath_url = media_info.original_filepath_url
        original_filename = media_info.file_name

        # 生成本地文件路径，使用数据库中的原始文件名
        local_file_path = f"/tmp/{original_filename}"

        # 下载文件
        with create_s3_bucket() as s3_bucket:
            s3_bucket.download_file(
                s3_key=s3_bucket.extract_s3_key(original_filepath_url),
                local_file_path=local_file_path,
            )

        return local_file_path

    async def delete_media_from_s3(
        self,
        media_ids: Union[int, List[int]],
        user_id: int,
        language: Language,
    ) -> Dict[str, Any]:
        """
        删除媒体文件，支持单个或多个文件删除
        同时删除数据库记录和S3中的文件

        简化参数，移除UUID以提升性能

        Args:
            media_ids: 媒体ID，可以是单个ID或ID列表
            user_id: 用户ID

        Returns:
            Dict[str, Any]: 删除结果
        """
        try:
            # 统一转换为列表格式
            if isinstance(media_ids, int):
                media_ids = [media_ids]

            # 获取要删除的媒体信息
            media_list = []
            for media_id in media_ids:
                media = await self.media_crud.get_media(
                    media_id=media_id, user_id=user_id
                )
                if not media:
                    self.logger.warning(f"媒体文件不存在: ID={media_id}")
                    continue
                media_list.append(media)

            if not media_list:
                return {
                    "success": False,
                    "message": "没有找到要删除的媒体文件",
                    "total": 0,
                    "deleted": 0,
                    "failed": 0,
                }

            # 准备S3删除的键列表
            s3_keys_to_delete = []
            with create_s3_bucket(verify_bucket=False) as s3_bucket:
                for media in media_list:
                    # 提取原始文件的S3键
                    original_key = s3_bucket.extract_s3_key(
                        media.original_filepath_url)
                    if original_key:
                        s3_keys_to_delete.append(original_key)

                    # 提取缩略图的S3键
                    if media.thumbnail_filepath_url:
                        thumbnail_key = s3_bucket.extract_s3_key(
                            media.thumbnail_filepath_url
                        )
                        if thumbnail_key:
                            s3_keys_to_delete.append(thumbnail_key)

                    # 提取水印图的S3键
                    if media.watermark_filepath_url:
                        watermark_key = s3_bucket.extract_s3_key(
                            media.watermark_filepath_url
                        )
                        if watermark_key:
                            s3_keys_to_delete.append(watermark_key)

            # 删除S3中的文件
            s3_delete_results = {}
            if s3_keys_to_delete:
                with create_s3_bucket(verify_bucket=False) as s3_bucket:
                    s3_delete_results = s3_bucket.delete_files(
                        s3_keys=s3_keys_to_delete,
                        max_workers=2,  # 保守策略：降低删除并发
                    )

            # 删除数据库记录
            db_delete_results = []
            for media in media_list:
                try:
                    await self.media_crud.delete_media_from_s3(
                        media_id=media.id,
                        user_id=user_id,
                        language=language,
                    )
                    db_delete_results.append(True)
                except Exception as e:
                    self.logger.error(f"删除数据库记录失败: {str(e)}")
                    db_delete_results.append(False)

            # 统计结果
            total_files = len(media_list)
            db_success_count = sum(db_delete_results)

            # S3删除结果统计
            if isinstance(s3_delete_results, dict):
                s3_success_count = sum(
                    1 for success in s3_delete_results.values() if success
                )
            else:
                s3_success_count = 1 if s3_delete_results else 0

            # 计算总体成功数（数据库和S3都成功才算成功）
            overall_success_count = min(db_success_count, s3_success_count)
            failed_count = total_files - overall_success_count

            # 记录删除结果
            self.logger.info(
                f"媒体文件删除完成: 总计={total_files}, "
                f"数据库成功={db_success_count}, S3成功={s3_success_count}, "
                f"总体成功={overall_success_count}, 失败={failed_count}"
            )

            return {
                "success": failed_count == 0,
                "total": total_files,
                "deleted": overall_success_count,
                "failed": failed_count,
                "db_success": db_success_count,
                "s3_success": s3_success_count,
                "message": f"删除完成，成功删除 {overall_success_count}/{total_files} 个文件",
            }

        except Exception as e:
            self.logger.error(f"删除媒体文件失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "删除媒体文件失败",
            }


# 提供获取媒体服务的函数，避免模块级别的实例化问题
def get_media_service(
    media_crud: MediaCrud = Depends(get_media_crud),
) -> MediaService:
    """获取媒体服务实例"""
    return MediaService(media_crud)
