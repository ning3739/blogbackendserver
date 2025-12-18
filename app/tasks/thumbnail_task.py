import os
import subprocess
import tempfile
from pathlib import Path
from typing import Union, List
from app.core.celery import celery_app, with_db_init
from app.core.logger import logger_manager
from app.utils.s3_bucket import create_s3_bucket
from app.utils.io_utils import download_inputs_if_needed


logger = logger_manager.get_logger(__name__)


def generate_image_thumbnail(
    input_paths: Union[str, Path, List[Union[str, Path]]],
    output_dir: Union[str, Path],
    width: int = 200,
    height: int = -1,
):
    """
    生成缩略图并转换为 WebP，支持单个文件或文件列表。

    Args:
        input_paths: 单个文件路径或文件列表
        output_dir: 输出文件夹
        width: 缩略图宽度
        height: 缩略图高度
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 统一 input_paths 为列表
    if isinstance(input_paths, (str, Path)):
        input_paths = [Path(input_paths)]
    else:
        input_paths = [Path(p) for p in input_paths]

    for file_path in input_paths:
        file_path = Path(file_path)
        if not file_path.is_file():
            logger.warning(f"跳过非文件: {file_path}")
            continue

        output_file = output_dir / f"{file_path.stem}_thumbnail.webp"

        # 构建 ffmpeg 命令
        if width == height:
            # 先按较短边缩放到目标尺寸，再裁剪为正方形，避免裁剪尺寸超过图像尺寸
            vf_core = (
                f"scale='if(gt(a,1),-2,{width})':'if(gt(a,1),{height},-2)',"
                f"crop={width}:{height}"
            )
        else:
            # 非正方形时仅缩放以适配目标盒子，保持比例
            vf_core = f"scale={width}:{height}:force_original_aspect_ratio=decrease"

        # 统一色彩范围（full -> limited）后再缩放/裁剪，最后转换为 yuv420p。
        # 注意：必须在转换为 yuv420p 之前确保宽高为偶数，否则会触发“image dimensions must be divisible by subsampling factor”。
        vf_option = (
            f"zscale=rangein=full:range=limited,"
            f"{vf_core},"
            f"scale=trunc(iw/2)*2:trunc(ih/2)*2,"
            f"format=yuv420p"
        )

        command = [
            "ffmpeg",
            "-i",
            str(file_path),
            "-vf",
            vf_option,
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libwebp",  # 强制输出 WebP
            "-q:v",
            "80",  # 质量
            "-y",  # 覆盖输出
            str(output_file),
        ]

        try:
            subprocess.run(command, check=True)
            logger.info(f"生成缩略图成功: {output_file}")
        except subprocess.CalledProcessError as e:
            logger.error(f"生成缩略图失败: {file_path}, 错误: {e}")


def generate_video_thumbnail(
    input_paths: Union[str, Path, List[Union[str, Path]]],
    output_dir: Union[str, Path],
    width: int = 320,
    height: int = -1,
    duration: int = 10,
):
    """
    生成 WebM 缩略视频，支持单个视频或视频列表。

    Args:
        input_paths: 单个视频路径或视频列表
        output_dir: 输出目录
        width: 缩略视频宽度，高度 -1 表示等比缩放
        height: 缩略视频高度，默认为 -1，按宽度等比缩放
        duration: 缩略视频最大时长（秒）
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 统一为列表
    if isinstance(input_paths, (str, Path)):
        input_paths = [Path(input_paths)]
    else:
        input_paths = [Path(p) for p in input_paths]

    for file_path in input_paths:
        file_path = Path(file_path)
        if not file_path.is_file():
            logger.warning(f"跳过非文件: {file_path}")
            continue

        output_file = output_dir / f"{file_path.stem}_thumbnail.mp4"

        # 构建 ffmpeg 命令
        vf_core = f"scale={width}:{height}:force_original_aspect_ratio=decrease"
        # 同上，先统一范围，再缩放，保证偶数尺寸，最后转为 yuv420p
        vf_option = (
            f"zscale=rangein=full:range=limited,"
            f"{vf_core},"
            f"scale=trunc(iw/2)*2:trunc(ih/2)*2,"
            f"format=yuv420p"
        )

        command = [
            "ffmpeg",
            "-threads",
            "2",  # H.264 可以用 2 线程
            "-i",
            str(file_path),
            "-t",
            str(duration),  # 截取前 duration 秒
            "-vf",
            vf_option,
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",  # H.264 编码，速度快
            "-preset",
            "ultrafast",  # 最快编码（缩略图不需要高压缩率）
            "-crf",
            "28",  # 缩略图质量足够
            "-profile:v",
            "baseline",  # 最大兼容性
            "-movflags",
            "+faststart",  # 网页播放优化
            "-c:a",
            "aac",  # AAC 音频
            "-b:a",
            "64k",  # 缩略图音频码率
            "-y",  # 覆盖输出
            str(output_file),
        ]

        try:
            subprocess.run(command, check=True)
            logger.info(f"生成 WebM 缩略视频成功: {output_file}")
        except subprocess.CalledProcessError as e:
            logger.error(f"生成 WebM 缩略视频失败: {file_path}, 错误: {e}")


@celery_app.task(
    name="generate_image_thumbnail", bind=True, max_retries=3, default_retry_delay=30
)
@with_db_init
def generate_image_thumbnail_task(
    self,
    input_paths: Union[str, Path, List[Union[str, Path]]],
    output_dir: Union[str, Path],
    width: int = 200,
    height: int = -1,
) -> None:
    try:
        # 确保输入为本地文件
        local_inputs = download_inputs_if_needed(input_paths)

        if not local_inputs:
            logger.warning("没有可用的本地输入文件，跳过缩略图生成")
            return

        # 使用临时本地目录保存输出，再上传到S3
        local_output_dir = Path(tempfile.mkdtemp(prefix="thumb_out_"))

        # 调用同步函数生成缩略图
        generate_image_thumbnail(local_inputs, local_output_dir, width, height)
        logger.info(f"缩略图任务成功: {input_paths}")

        # 准备上传到S3的文件路径和S3键
        source_inputs = [Path(p) for p in (local_inputs or [])]

        # 生成缩略图文件路径（WebP格式）
        thumbnail_paths = []
        s3_keys = []

        for file_path in source_inputs:
            thumbnail_file = local_output_dir / \
                f"{file_path.stem}_thumbnail.webp"
            if thumbnail_file.exists():
                thumbnail_paths.append(str(thumbnail_file))
                # 生成S3键：使用调用方传入的S3前缀
                s3_key = f"{output_dir}/{file_path.stem}_thumbnail.webp"
                s3_keys.append(s3_key)

        # 上传缩略图到S3
        if thumbnail_paths:
            with create_s3_bucket() as s3_bucket:
                s3_bucket.upload_files(
                    file_paths=thumbnail_paths,
                    s3_keys=s3_keys,
                    metadata_list=[],
                    content_types=["image/webp"] * len(thumbnail_paths),
                    acl="public-read",
                )
                logger.info(f"成功上传 {len(thumbnail_paths)} 个缩略图到S3")

                # 检查是否上传成功，只有成功上传的文件才删除本地副本
                successful_uploads = []
                for file_path, s3_key in zip(thumbnail_paths, s3_keys):
                    if s3_bucket.file_exists(s3_key):
                        successful_uploads.append(file_path)
                        logger.debug(f"确认文件上传成功: {s3_key}")
                    else:
                        logger.warning(f"文件上传可能失败，保留本地副本: {s3_key}")

                # 删除成功上传的本地文件
                for file_path in successful_uploads:
                    try:
                        os.remove(file_path)
                        logger.debug(f"已删除本地文件: {file_path}")
                    except OSError as e:
                        logger.warning(f"删除本地文件失败: {file_path}, 错误: {e}")

                logger.info(
                    f"成功删除 {len(successful_uploads)} 个本地文件，保留 {len(thumbnail_paths) - len(successful_uploads)} 个文件用于重试"
                )

    except Exception as e:
        logger.error(f"缩略图任务失败: {e}")
        # 如果任务失败，尝试重试
        if self.request.retries < self.max_retries:
            logger.warning(f"尝试重试任务，第 {self.request.retries + 1} 次重试")
            raise self.retry(exc=e, countdown=self.default_retry_delay)
        else:
            logger.error("任务重试次数已达上限，任务失败")
            raise


@celery_app.task(
    name="generate_video_thumbnail", bind=True, max_retries=3, default_retry_delay=30
)
@with_db_init
def generate_video_thumbnail_task(
    self,
    input_paths: Union[str, Path, List[Union[str, Path]]],
    output_dir: Union[str, Path],
    width: int = 320,
    height: int = -1,
    duration: int = 10,
) -> None:
    try:
        # 确保输入为本地文件
        local_inputs = download_inputs_if_needed(input_paths)

        if not local_inputs:
            logger.warning("没有可用的本地输入文件，跳过视频缩略图生成")
            return

        # 使用临时本地目录保存输出，再上传到S3
        local_output_dir = Path(tempfile.mkdtemp(prefix="vthumb_out_"))

        # 调用同步函数生成视频缩略图
        generate_video_thumbnail(
            local_inputs, local_output_dir, width, height, duration
        )
        logger.info(f"视频缩略图任务成功: {input_paths}")

        # 准备上传到S3的文件路径和S3键
        source_inputs = [Path(p) for p in (local_inputs or [])]

        # 生成缩略视频文件路径（MP4格式）
        thumbnail_paths = []
        s3_keys = []

        for file_path in source_inputs:
            thumbnail_file = local_output_dir / \
                f"{file_path.stem}_thumbnail.mp4"
            if thumbnail_file.exists():
                thumbnail_paths.append(str(thumbnail_file))
                # 生成S3键：使用调用方传入的S3前缀
                s3_key = f"{output_dir}/{file_path.stem}_thumbnail.mp4"
                s3_keys.append(s3_key)

        # 上传缩略视频到S3
        if thumbnail_paths:
            with create_s3_bucket() as s3_bucket:
                s3_bucket.upload_files(
                    file_paths=thumbnail_paths,
                    s3_keys=s3_keys,
                    metadata_list=[],
                    content_types=["video/mp4"] * len(thumbnail_paths),
                    acl="public-read",
                )
                logger.info(f"成功上传 {len(thumbnail_paths)} 个缩略视频到S3")

                # 检查是否上传成功，只有成功上传的文件才删除本地副本
                successful_uploads = []
                for file_path, s3_key in zip(thumbnail_paths, s3_keys):
                    if s3_bucket.file_exists(s3_key):
                        successful_uploads.append(file_path)
                        logger.debug(f"确认文件上传成功: {s3_key}")
                    else:
                        logger.warning(f"文件上传可能失败，保留本地副本: {s3_key}")

                # 删除成功上传的本地文件
                for file_path in successful_uploads:
                    try:
                        os.remove(file_path)
                        logger.debug(f"已删除本地文件: {file_path}")
                    except OSError as e:
                        logger.warning(f"删除本地文件失败: {file_path}, 错误: {e}")

                logger.info(
                    f"成功删除 {len(successful_uploads)} 个本地文件，保留 {len(thumbnail_paths) - len(successful_uploads)} 个文件用于重试"
                )

    except Exception as e:
        logger.error(f"视频缩略图任务失败: {e}")
        # 如果任务失败，尝试重试
        if self.request.retries < self.max_retries:
            logger.warning(f"尝试重试任务，第 {self.request.retries + 1} 次重试")
            raise self.retry(exc=e, countdown=self.default_retry_delay)
        else:
            logger.error("任务重试次数已达上限，任务失败")
            raise
