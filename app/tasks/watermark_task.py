import os
import subprocess
import tempfile
import math
from pathlib import Path
from typing import Union, List
from app.core.celery import celery_app, with_db_init
from app.core.logger import logger_manager
from app.utils.s3_bucket import create_s3_bucket
from app.utils.io_utils import download_inputs_if_needed


logger = logger_manager.get_logger(__name__)


def generate_image_watermark(
    input_paths: Union[str, Path, List[Union[str, Path]]],
    output_dir: Union[str, Path],
    text: str,
    font_size: int = 60,
    font_color: str = "white",
    opacity: float = 0.08,
):
    """
    为图片添加文字水印并转换为 WebP，支持单个文件或文件列表。

    Args:
        input_paths: 单个文件路径或文件列表
        output_dir: 输出文件夹
        text: 水印文字内容
        font_size: 字体大小（默认更大）
        font_color: 字体颜色
        opacity: 透明度 (0.0-1.0)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 统一 input_paths 为列表
    if isinstance(input_paths, (str, Path)):
        input_paths = [Path(input_paths)]
    else:
        input_paths = [Path(p) for p in input_paths]

    # 预处理文本
    input_text = "" if text is None else str(text)

    for file_path in input_paths:
        file_path = Path(file_path)
        if not file_path.is_file():
            logger.warning(f"跳过非文件: {file_path}")
            continue

        # 转换为 WebP 格式，添加水印
        output_file = output_dir / f"{file_path.stem}_watermark.webp"

        # 动态计算字号与颜色（取反色）、不透明度
        # 1) 尺寸（更大以便可见）
        fsize = font_size
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=p=0",
                str(file_path),
            ]
            res = subprocess.run(cmd, check=True, capture_output=True)
            out = res.stdout.decode().strip()
            if out:
                w_h = out.split(",")
                if len(w_h) == 2:
                    w = int(w_h[0])
                    h = int(w_h[1])
                    if w > 0 and h > 0:
                        dyn = int(min(w, h) * 0.06)
                        fsize = max(dyn, font_size)
                    else:
                        w, h = 1920, 1080
                else:
                    w, h = 1920, 1080
            else:
                w, h = 1920, 1080
        except Exception:
            # 合理默认尺寸，防止后续计算异常
            w, h = 1920, 1080
            dyn = int(min(w, h) * 0.06)
            fsize = max(dyn, font_size)

        # 2) 右下角区域平均色采样并取反
        fcolor = font_color
        falpha = opacity
        try:
            crop = (
                "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=rgb24,"
                "crop=iw*0.25:ih*0.18:iw-iw*0.25-10:ih-ih*0.18-10,scale=1:1"
            )
            cmd = [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(file_path),
                "-frames:v",
                "1",
                "-vf",
                crop,
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-",
            ]
            res = subprocess.run(cmd, check=True, capture_output=True)
            data = res.stdout
            if len(data) >= 3:
                sr, sg, sb = data[0], data[1], data[2]
                inv_r, inv_g, inv_b = 255 - sr, 255 - sg, 255 - sb
                fcolor = f"0x{inv_r:02x}{inv_g:02x}{inv_b:02x}"
                # 更透明但可见
                brightness = (0.299 * sr + 0.587 * sg + 0.114 * sb) / 255.0
                if brightness >= 0.7:
                    falpha = 0.10  # 亮背景，最透明
                elif brightness >= 0.4:
                    falpha = 0.15  # 中等背景，稍微明显一点
                else:
                    falpha = 0.18  # 暗背景，相对明显一点
        except Exception:
            pass

        # 构建平铺网格文本，写入临时文本文件，避免过滤器转义问题
        try:
            # 扩大画布以避免旋转后出现空白
            diag = int(math.hypot(w, h))
            canvas_side = max(64, int(diag * 1.4))
            canvas_w, canvas_h = canvas_side, canvas_side

            approx_char_w = max(int(fsize * 0.55), 1)
            text_len = max(len(input_text), 1)
            col_gap_px = int(fsize * 0.6)
            tile_w_px = text_len * approx_char_w + col_gap_px
            cols = max(int(math.ceil(canvas_w / max(tile_w_px, 1))) + 4, 2)
            line_spacing = int(fsize * 0.2)
            rows = max(
                int(math.ceil(canvas_h / max(fsize + line_spacing, 1))) + 4, 2)

            # 将像素级间距换算为空格数量（近似）
            gap_spaces = max(int(col_gap_px / approx_char_w), 1)
            col_sep = " " * gap_spaces
            one_row = (input_text + col_sep) * cols
            grid_lines = [one_row for _ in range(rows)]
            grid_text = "\n".join(grid_lines)

            # 写入临时文件
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".txt",
                prefix="wm_txt_",
                mode="w",
                encoding="utf-8",
            ) as tf:
                tf.write(grid_text)
                pattern_path = tf.name
        except Exception:
            # 回退为原始文本（单行）
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".txt",
                prefix="wm_txt_",
                mode="w",
                encoding="utf-8",
            ) as tf:
                tf.write(input_text or "")
                pattern_path = tf.name
            # 回退画布与行距
            canvas_w, canvas_h = w, h
            line_spacing = int(fsize * 0.2)

        # 使用 filter_complex 构建透明背景 + 文本 + 旋转 + 覆盖
        # 使用简化的处理流程，避免不必要的格式转换
        # 透明背景扩大以覆盖旋转后的边角，文本平铺，旋转 45 度
        filter_complex = (
            f"[0:v]scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos[base];"
            f"color=c=black@0.0:s={canvas_w}x{canvas_h}[bg];"
            f"[bg]format=rgba,drawtext=textfile={pattern_path}:fontsize={fsize}:fontcolor={fcolor}:alpha={falpha}:line_spacing={line_spacing}:x=0:y=0:fix_bounds=1,"
            f"rotate=45*PI/180:out_w=rotw(iw):out_h=roth(ih):fillcolor=black@0.0[wm];"
            f"[base][wm]overlay=x=(main_w-overlay_w)/2:y=(main_h-overlay_h)/2:shortest=1[vout]"
        )

        command = [
            "ffmpeg",
            "-hide_banner",  # 隐藏 FFmpeg 版本信息
            "-loglevel",
            "warning",  # 只显示警告和错误
            "-i",
            str(file_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-c:v",
            "libwebp",  # 强制输出 WebP
            "-q:v",
            "80",  # 质量
            "-frames:v",
            "1",
            "-y",  # 覆盖输出
            str(output_file),
        ]

        try:
            subprocess.run(command, check=True)
            logger.info(f"添加图片水印成功: {output_file}")
        except subprocess.CalledProcessError as e:
            logger.error(f"添加图片水印失败: {file_path}, 错误: {e}")
        finally:
            try:
                if "pattern_path" in locals() and os.path.exists(pattern_path):
                    os.remove(pattern_path)
            except Exception:
                pass


def generate_video_watermark(
    input_paths: Union[str, Path, List[Union[str, Path]]],
    output_dir: Union[str, Path],
    text: str,
    font_size: int = 60,
    font_color: str = "white",
    opacity: float = 0.15,
    start_time: float = 0.0,
    duration: float = None,
):
    """
    为视频添加文字水印并转换为 WebM，支持单个视频或视频列表。

    Args:
        input_paths: 单个视频路径或视频列表
        output_dir: 输出目录
        text: 水印文字内容
        font_size: 字体大小（默认更大）
        font_color: 字体颜色
        opacity: 透明度 (0.0-1.0)
        start_time: 水印开始时间（秒）
        duration: 水印持续时间（秒），None 表示持续到视频结束
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 统一为列表
    if isinstance(input_paths, (str, Path)):
        input_paths = [Path(input_paths)]
    else:
        input_paths = [Path(p) for p in input_paths]

    # 预处理文本
    input_text = "" if text is None else str(text)

    for file_path in input_paths:
        file_path = Path(file_path)
        if not file_path.is_file():
            logger.warning(f"跳过非文件: {file_path}")
            continue

        # 转换为 MP4 格式，添加水印（H.264 编码速度更快）
        output_file = output_dir / f"{file_path.stem}_watermark.mp4"

        # 动态计算字号与颜色（取反色）、不透明度
        # 采样时间靠近 start_time，默认 0.5s
        sample_t = start_time if start_time and start_time > 0 else 0.5

        # 1) 尺寸（更大以便可见）
        fsize = font_size
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=p=0",
                str(file_path),
            ]
            res = subprocess.run(cmd, check=True, capture_output=True)
            out = res.stdout.decode().strip()
            if out:
                w_h = out.split(",")
                if len(w_h) == 2:
                    w = int(w_h[0])
                    h = int(w_h[1])
                    if w > 0 and h > 0:
                        dyn = int(min(w, h) * 0.06)
                        fsize = max(dyn, font_size)
                    else:
                        w, h = 1920, 1080
                else:
                    w, h = 1920, 1080
            else:
                w, h = 1920, 1080
        except Exception:
            w, h = 1920, 1080
            dyn = int(min(w, h) * 0.06)
            fsize = max(dyn, font_size)

        # 2) 右下角区域平均色采样并取反
        fcolor = font_color
        falpha = opacity
        try:
            crop = (
                "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=rgb24,"
                "crop=iw*0.25:ih*0.18:iw-iw*0.25-10:ih-ih*0.18-10,scale=1:1"
            )
            cmd = [
                "ffmpeg",
                "-v",
                "error",
                "-ss",
                str(sample_t),
                "-i",
                str(file_path),
                "-frames:v",
                "1",
                "-vf",
                crop,
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-",
            ]
            res = subprocess.run(cmd, check=True, capture_output=True)
            data = res.stdout
            if len(data) >= 3:
                sr, sg, sb = data[0], data[1], data[2]
                inv_r, inv_g, inv_b = 255 - sr, 255 - sg, 255 - sb
                fcolor = f"0x{inv_r:02x}{inv_g:02x}{inv_b:02x}"
                brightness = (0.299 * sr + 0.587 * sg + 0.114 * sb) / 255.0
                if brightness >= 0.7:
                    falpha = 0.18  # 亮背景，视频需要稍微明显
                elif brightness >= 0.4:
                    falpha = 0.22  # 中等背景，适中透明度
                else:
                    falpha = 0.25  # 暗背景，相对明显一点
        except Exception:
            pass

        # 构建平铺网格文本，写入临时文本文件
        line_spacing = int(fsize * 0.2)
        try:
            diag = int(math.hypot(w, h))
            canvas_side = max(64, int(diag * 1.4))
            canvas_w, canvas_h = canvas_side, canvas_side

            approx_char_w = max(int(fsize * 0.55), 1)
            text_len = max(len(input_text), 1)
            col_gap_px = int(fsize * 0.6)
            tile_w_px = text_len * approx_char_w + col_gap_px
            cols = max(int(math.ceil((canvas_w) / max(tile_w_px, 1))) + 4, 2)
            rows = max(
                int(math.ceil((canvas_h) / max(fsize + line_spacing, 1))) + 4, 2)

            gap_spaces = max(int(col_gap_px / approx_char_w), 1)
            col_sep = " " * gap_spaces
            one_row = (input_text + col_sep) * cols
            grid_lines = [one_row for _ in range(rows)]
            grid_text = "\n".join(grid_lines)

            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".txt",
                prefix="wm_txt_",
                mode="w",
                encoding="utf-8",
            ) as tf:
                tf.write(grid_text)
                pattern_path = tf.name
        except Exception:
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".txt",
                prefix="wm_txt_",
                mode="w",
                encoding="utf-8",
            ) as tf:
                tf.write(input_text or "")
                pattern_path = tf.name
            canvas_w, canvas_h = w, h

        # 覆盖区间控制
        enable_expr = (
            f"between(t,{start_time},{start_time + (duration if duration else 999999)})"
        )

        # 计算720p缩放尺寸（保持宽高比，高度限制为720）
        # 如果原始高度小于720，则不缩放
        target_h = min(h, 720)
        # 确保宽度为偶数
        scale_expr = f"scale=-2:{target_h}:flags=lanczos"

        # 重新计算水印画布尺寸（基于720p）
        scaled_w = int(w * target_h / h) if h > 0 else w
        scaled_h = target_h
        diag_scaled = int(math.hypot(scaled_w, scaled_h))
        canvas_side_scaled = max(64, int(diag_scaled * 1.4))

        # 调整字体大小适配720p
        fsize_scaled = max(int(fsize * target_h / h), 30) if h > 0 else fsize

        # 使用 filter_complex 叠加平铺旋转文本
        # 先缩放到720p，再添加水印，减小文件体积并加快编码速度
        filter_complex = (
            f"[0:v]{scale_expr}[scaled];"
            f"[scaled]scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos[base];"
            f"color=c=black@0.0:s={canvas_side_scaled}x{canvas_side_scaled}[bg];"
            f"[bg]format=rgba,drawtext=textfile={pattern_path}:fontsize={fsize_scaled}:fontcolor={fcolor}:alpha={falpha}:line_spacing={line_spacing}:x=0:y=0:fix_bounds=1,"
            f"rotate=45*PI/180:out_w=rotw(iw):out_h=roth(ih):fillcolor=black@0.0[wm];"
            f"[base][wm]overlay=x=(main_w-overlay_w)/2:y=(main_h-overlay_h)/2:enable='{enable_expr}':shortest=1[vout]"
        )

        command = [
            "ffmpeg",
            "-hide_banner",  # 隐藏 FFmpeg 版本信息
            "-loglevel",
            "warning",  # 只显示警告和错误
            "-threads",
            "2",  # H.264 可以用 2 线程，仍然省内存
            "-i",
            str(file_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",  # H.264 编码，速度快 5-10 倍
            "-preset",
            "veryfast",  # 快速编码，质量仍然不错
            "-crf",
            "23",  # H.264 的 CRF 23 质量很好
            "-profile:v",
            "high",  # 高质量 profile
            "-level",
            "4.1",  # 兼容性好
            "-movflags",
            "+faststart",  # 优化网页播放，元数据前置
            "-pix_fmt",
            "yuv420p",  # 最大兼容性
            "-c:a",
            "aac",  # AAC 音频编码
            "-b:a",
            "128k",  # 音频码率
            "-y",  # 覆盖输出
            str(output_file),
        ]

        try:
            subprocess.run(command, check=True)
            logger.info(f"添加视频水印成功: {output_file}")
        except subprocess.CalledProcessError as e:
            logger.error(f"添加视频水印失败: {file_path}, 错误: {e}")
        finally:
            try:
                if "pattern_path" in locals() and os.path.exists(pattern_path):
                    os.remove(pattern_path)
            except Exception:
                pass


@celery_app.task(
    name="generate_image_watermark", bind=True, max_retries=3, default_retry_delay=30
)
@with_db_init
def generate_image_watermark_task(
    self,
    input_paths: Union[str, Path, List[Union[str, Path]]],
    output_dir: Union[str, Path],
    text: str,
    font_size: int = 60,
    font_color: str = "white",
    opacity: float = 0.08,
) -> None:
    try:
        # 确保输入为本地文件
        local_inputs = download_inputs_if_needed(input_paths)

        if not local_inputs:
            logger.warning("没有可用的本地输入文件，跳过图片水印生成")
            return

        # 使用临时本地目录保存输出，再上传到S3
        local_output_dir = Path(tempfile.mkdtemp(prefix="wm_img_out_"))

        # 调用同步函数添加文字水印
        generate_image_watermark(
            input_paths=local_inputs,
            output_dir=local_output_dir,
            text=text,
            font_size=font_size,
            font_color=font_color,
            opacity=opacity,
        )
        logger.info(f"文字水印任务成功: {input_paths}")

        # 准备上传到S3的文件路径和S3键
        source_inputs = [Path(p) for p in (local_inputs or [])]

        # 生成水印文件路径
        watermark_paths = []
        s3_keys = []

        for file_path in source_inputs:
            watermark_file = local_output_dir / \
                f"{file_path.stem}_watermark.webp"
            if watermark_file.exists():
                watermark_paths.append(str(watermark_file))
                # 生成S3键：使用调用方传入的S3前缀
                s3_key = f"{output_dir}/{file_path.stem}_watermark.webp"
                s3_keys.append(s3_key)

        # 上传水印图片到S3
        if watermark_paths:
            with create_s3_bucket() as s3_bucket:
                # 所有水印图片都是WebP格式
                content_types = ["image/webp"] * len(watermark_paths)

                s3_bucket.upload_files(
                    file_paths=watermark_paths,
                    s3_keys=s3_keys,
                    metadata_list=[],
                    content_types=content_types,
                    acl="public-read",
                )
                logger.info(f"成功上传 {len(watermark_paths)} 个水印图片到S3")

                # 检查是否上传成功，只有成功上传的文件才删除本地副本
                successful_uploads = []
                for file_path, s3_key in zip(watermark_paths, s3_keys):
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
                    f"成功删除 {len(successful_uploads)} 个本地文件，保留 {len(watermark_paths) - len(successful_uploads)} 个文件用于重试"
                )

    except Exception as e:
        logger.error(f"文字水印任务失败: {e}")
        # 如果任务失败，尝试重试
        if self.request.retries < self.max_retries:
            logger.warning(f"尝试重试任务，第 {self.request.retries + 1} 次重试")
            raise self.retry(exc=e, countdown=self.default_retry_delay)
        else:
            logger.error("任务重试次数已达上限，任务失败")
            raise


@celery_app.task(
    name="generate_video_watermark", bind=True, max_retries=3, default_retry_delay=30
)
@with_db_init
def generate_video_watermark_task(
    self,
    input_paths: Union[str, Path, List[Union[str, Path]]],
    output_dir: Union[str, Path],
    text: str,
    font_size: int = 60,
    font_color: str = "white",
    opacity: float = 0.15,
    start_time: float = 0.0,
    duration: float = None,
) -> None:
    try:
        # 确保输入为本地文件
        local_inputs = download_inputs_if_needed(input_paths)

        if not local_inputs:
            logger.warning("没有可用的本地输入文件，跳过视频水印生成")
            return

        # 使用临时本地目录保存输出，再上传到S3
        local_output_dir = Path(tempfile.mkdtemp(prefix="wm_vid_out_"))

        # 调用同步函数添加视频文字水印
        generate_video_watermark(
            input_paths=local_inputs,
            output_dir=local_output_dir,
            text=text,
            font_size=font_size,
            font_color=font_color,
            opacity=opacity,
            start_time=start_time,
            duration=duration,
        )
        logger.info(f"视频文字水印任务成功: {input_paths}")

        # 准备上传到S3的文件路径和S3键
        source_inputs = [Path(p) for p in (local_inputs or [])]

        # 生成水印视频文件路径
        watermark_paths = []
        s3_keys = []

        for file_path in source_inputs:
            watermark_file = local_output_dir / \
                f"{file_path.stem}_watermark.mp4"
            if watermark_file.exists():
                watermark_paths.append(str(watermark_file))
                # 生成S3键：使用调用方传入的S3前缀
                s3_key = f"{output_dir}/{file_path.stem}_watermark.mp4"
                s3_keys.append(s3_key)

        # 上传水印视频到S3
        if watermark_paths:
            with create_s3_bucket() as s3_bucket:
                # 所有水印视频都是MP4格式
                content_types = ["video/mp4"] * len(watermark_paths)

                s3_bucket.upload_files(
                    file_paths=watermark_paths,
                    s3_keys=s3_keys,
                    metadata_list=[],
                    content_types=content_types,
                    acl="public-read",
                )
                logger.info(f"成功上传 {len(watermark_paths)} 个水印视频到S3")

                # 检查是否上传成功，只有成功上传的文件才删除本地副本
                successful_uploads = []
                for file_path, s3_key in zip(watermark_paths, s3_keys):
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
                    f"成功删除 {len(successful_uploads)} 个本地文件，保留 {len(watermark_paths) - len(successful_uploads)} 个文件用于重试"
                )

    except Exception as e:
        logger.error(f"视频文字水印任务失败: {e}")
        # 如果任务失败，尝试重试
        if self.request.retries < self.max_retries:
            logger.warning(f"尝试重试任务，第 {self.request.retries + 1} 次重试")
            raise self.retry(exc=e, countdown=self.default_retry_delay)
        else:
            logger.error("任务重试次数已达上限，任务失败")
            raise
