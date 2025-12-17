import boto3
import mimetypes
import threading
from typing import Optional, Dict, Union, Callable, cast
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config
from app.core.config.settings import settings
from app.core.logger import logger_manager
from boto3.s3.transfer import TransferConfig
from urllib.parse import urlparse


class RobustS3Bucket:
    """
    专注于稳健上传下载的S3操作类
    提供核心的文件上传下载功能，包含重试机制和错误处理
    固定使用配置中指定的S3存储桶
    """

    def __init__(self, verify_bucket: bool = True):
        """
        初始化RobustS3Bucket
        从配置中读取AWS凭证和存储桶信息
        """
        self.logger = logger_manager.get_logger(__name__)
        self.access_key_id = settings.aws.AWS_ACCESS_KEY_ID
        self.secret_access_key = settings.aws.AWS_SECRET_ACCESS_KEY.get_secret_value()
        self.region = settings.aws.AWS_REGION
        self.bucket_name = settings.aws.AWS_BUCKET_NAME

        # 验证必要的配置参数
        if not all(
            [self.bucket_name, self.access_key_id,
                self.secret_access_key, self.region]
        ):
            missing_params = []
            if not self.bucket_name:
                missing_params.append("AWS_BUCKET_NAME")
            if not self.access_key_id:
                missing_params.append("AWS_ACCESS_KEY_ID")
            if not self.secret_access_key:
                missing_params.append("AWS_SECRET_ACCESS_KEY")
            if not self.region:
                missing_params.append("AWS_REGION")

            error_msg = f"缺少必要的AWS配置参数: {', '.join(missing_params)}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        # boto3配置 - 针对小内存服务器优化（2GB RAM）
        config = Config(
            region_name=self.region,
            retries={"max_attempts": 5, "mode": "adaptive"},  # 自适应重试
            max_pool_connections=10,  # 降低连接数，减少内存占用
            connect_timeout=60,  # 连接超时增加到60秒
            read_timeout=300,  # 读取超时增加到5分钟，支持大文件
        )

        try:
            # 初始化S3客户端
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=self.region,
                config=config,
            )

            # 线程池执行器 - 小内存服务器优化
            self.thread_pool = ThreadPoolExecutor(max_workers=3)  # 降低工作线程数
            self._shutdown_event = threading.Event()

            # 传输配置 - 针对2GB RAM优化
            self.transfer_config = TransferConfig(
                multipart_threshold=5 * 1024 * 1024,  # 5MB触发分片
                multipart_chunksize=5 * 1024 * 1024,  # 5MB分片大小
                max_concurrency=3,  # 降低并发数，减少内存压力
                use_threads=True,
            )

            self.logger.info(f"RobustS3Bucket初始化成功，区域: {self.region}")

            # 验证连接（可跳过以减少额外往返）
            if verify_bucket and (not self._verify_bucket_access()):
                self.logger.warning("存储桶访问验证失败，但S3Bucket实例已创建")

        except NoCredentialsError:
            self.logger.error("AWS凭证未配置")
            raise
        except Exception as e:
            self.logger.error(f"RobustS3Bucket初始化失败: {str(e)}")
            raise

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()

    def close(self):
        """关闭线程池"""
        self._shutdown_event.set()
        self.thread_pool.shutdown(wait=True)
        self.logger.info("RobustS3Bucket已关闭")

    def _verify_bucket_access(self) -> bool:
        """验证存储桶访问权限"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            self.logger.info(f"存储桶访问验证成功: {self.bucket_name}")
            return True
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                self.logger.warning(f"存储桶不存在: {self.bucket_name}")
            elif error_code == "403":
                self.logger.error(f"无权访问存储桶: {self.bucket_name}")
            else:
                self.logger.error(f"存储桶访问验证失败: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"验证存储桶访问时出错: {str(e)}")
            return False

    def _verify_upload_success(self, s3_key: str, local_file_path: Path) -> bool:
        """
        验证上传是否成功
        通过比较文件大小和ETag来验证
        """
        try:
            # 获取本地文件大小
            local_size = local_file_path.stat().st_size

            # 获取S3文件信息
            s3_info = self.get_file_info(s3_key)
            if not s3_info:
                return False

            # 比较文件大小
            if s3_info["size"] != local_size:
                self.logger.warning(
                    f"文件大小不匹配: 本地={local_size}, S3={s3_info['size']}"
                )
                return False

            return True

        except Exception as e:
            self.logger.error(f"验证上传失败: {str(e)}")
            return False

    def get_file_info(self, s3_key: str) -> Optional[Dict[str, any]]:
        """
        获取S3对象的信息，包括大小、ETag、内容类型等

        Args:
            s3_key: S3文件键

        Returns:
            Optional[Dict[str, any]]: 对象信息，若不存在或获取失败返回None
        """
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name, Key=s3_key)
            return {
                "size": response.get("ContentLength"),
                "etag": (response.get("ETag") or "").strip('"'),
                "content_type": response.get("ContentType"),
                "last_modified": response.get("LastModified"),
                "metadata": response.get("Metadata", {}),
            }
        except ClientError as e:
            error_code = e.response["Error"].get("Code")
            if error_code == "404":
                return None
            self.logger.error(f"获取文件信息失败 {s3_key}: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"获取文件信息时出错 {s3_key}: {str(e)}")
            return None

    def _verify_download_success(self, s3_key: str, local_file_path: Path) -> bool:
        """
        验证下载是否成功
        通过比较文件大小来验证
        """
        try:
            # 获取本地文件大小
            local_size = local_file_path.stat().st_size

            # 获取S3文件信息
            s3_info = self.get_file_info(s3_key)
            if not s3_info:
                return False

            # 比较文件大小
            if s3_info["size"] != local_size:
                self.logger.warning(
                    f"文件大小不匹配: S3={s3_info['size']}, 本地={local_size}"
                )
                return False

            return True

        except Exception as e:
            self.logger.error(f"验证下载失败: {str(e)}")
            return False

    def _upload_single_file(
        self,
        local_file_path: Union[str, Path],
        s3_key: str,
        metadata: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        verify: bool = True,
        acl: Optional[str] = None,
    ) -> bool:
        """
        内部方法：上传单个文件到S3

        Args:
            local_file_path: 本地文件路径
            s3_key: S3文件键
            metadata: 文件元数据
            content_type: 内容类型，自动检测如果未指定
            progress_callback: 进度回调函数 (uploaded_bytes, total_bytes)

        Returns:
            bool: 上传是否成功
        """
        local_file_path = Path(local_file_path)

        try:
            if not local_file_path.exists():
                self.logger.error(f"本地文件不存在: {local_file_path}")
                return False

            # 自动检测内容类型
            if content_type is None:
                content_type, _ = mimetypes.guess_type(str(local_file_path))
                if content_type is None:
                    content_type = "application/octet-stream"

            # 构建上传参数
            extra_args = {"ContentType": content_type}
            if acl:
                extra_args["ACL"] = acl

            if metadata:
                extra_args["Metadata"] = metadata

            # 进度回调包装器
            if progress_callback:
                file_size = local_file_path.stat().st_size

                class ProgressWrapper:
                    def __init__(self, callback, total_size):
                        self.callback = callback
                        self.total_size = total_size
                        self.uploaded = 0
                        self.lock = threading.Lock()

                    def __call__(self, bytes_transferred):
                        with self.lock:
                            self.uploaded += bytes_transferred
                            try:
                                self.callback(self.uploaded, self.total_size)
                            except Exception:
                                # 避免回调函数异常影响上传
                                pass

                extra_args["Callback"] = ProgressWrapper(
                    progress_callback, file_size)

            # 执行上传（使用传输配置提升吞吐）
            self.s3_client.upload_file(
                str(local_file_path),
                self.bucket_name,
                s3_key,
                ExtraArgs=extra_args,
                Config=self.transfer_config,
            )

            # 验证上传结果
            if (not verify) or self._verify_upload_success(s3_key, local_file_path):
                self.logger.info(
                    f"文件上传成功: {local_file_path} -> s3://{self.bucket_name}/{s3_key}"
                )
                return True
            else:
                self.logger.error(f"文件上传验证失败: {s3_key}")
                return False

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            self.logger.error(
                f"上传文件到S3失败 {local_file_path}: "
                f"错误代码={error_code}, 错误信息={error_msg}",
                exc_info=True
            )
            return False
        except Exception as e:
            self.logger.error(
                f"上传文件失败 {local_file_path}: {str(e)}",
                exc_info=True
            )
            return False

    def upload_files(
        self,
        file_paths: Union[str, list, tuple],
        s3_keys: Union[str, list, tuple],
        metadata_list: Optional[Union[dict, list, tuple]] = None,
        content_types: Optional[Union[str, list, tuple]] = None,
        progress_callback: Optional[Callable[[int, int, int], None]] = None,
        max_workers: int = 5,
        verify: bool = True,
        acl: Optional[Union[str, list, tuple]] = None,
    ) -> Union[bool, Dict[str, bool]]:
        """
        上传文件到S3，支持单个或多个文件，支持并发上传

        Args:
            file_paths: 本地文件路径，可以是单个字符串或列表/元组
            s3_keys: S3文件键，可以是单个字符串或列表/元组
            metadata_list: 文件元数据，可以是单个字典或列表/元组，可选
            content_types: 内容类型，可以是单个字符串或列表/元组，可选
            progress_callback: 进度回调函数 (file_index, uploaded_files, total_files)
            max_workers: 最大并发工作线程数

        Returns:
            Union[bool, Dict[str, bool]]: 单个文件返回bool，多个文件返回字典
        """
        # 如果是单个文件，转换为列表格式
        is_single_file = isinstance(file_paths, str)
        if is_single_file:
            file_paths = [file_paths]
            s3_keys = [s3_keys]
            if metadata_list and isinstance(metadata_list, dict):
                metadata_list = [metadata_list]
            if content_types and isinstance(content_types, str):
                content_types = [content_types]
            if acl and isinstance(acl, str):
                acl = [acl]

        # 验证参数长度一致性
        if len(file_paths) != len(s3_keys):
            raise ValueError("file_paths和s3_keys的长度必须一致")

        if metadata_list and len(metadata_list) != len(file_paths):
            raise ValueError("metadata_list的长度必须与file_paths一致")

        if content_types and len(content_types) != len(file_paths):
            raise ValueError("content_types的长度必须与content_types一致")

        # 仅当 acl 为序列时校验长度；若为字符串，则视为对所有文件统一应用
        if isinstance(acl, (list, tuple)) and len(cast(list, acl)) != len(file_paths):
            raise ValueError("acl 的长度必须与 file_paths 一致")

        # 如果只有一个文件，直接处理单个文件上传
        if len(file_paths) == 1:
            # 单文件路径下需要将 acl 传递到内部上传函数
            single_acl = (
                acl[0]
                if isinstance(acl, (list, tuple)) and len(cast(list, acl)) > 0
                else (acl if isinstance(acl, str) else None)
            )
            return self._upload_single_file(
                local_file_path=file_paths[0],
                s3_key=s3_keys[0],
                metadata=metadata_list[0] if metadata_list else None,
                content_type=content_types[0] if content_types else None,
                progress_callback=progress_callback,
                verify=verify,
                acl=single_acl,
            )

        # 多个文件的并发上传逻辑
        results = {}
        total_files = len(file_paths)
        uploaded_count = 0
        lock = threading.Lock()

        def upload_single_file(file_info):
            nonlocal uploaded_count
            file_path, s3_key, metadata, content_type, acl_value = file_info

            try:
                success = self._upload_single_file(
                    local_file_path=file_path,
                    s3_key=s3_key,
                    metadata=metadata,
                    content_type=content_type,
                    acl=acl_value,
                    verify=verify,
                )

                with lock:
                    results[s3_key] = success
                    uploaded_count += 1

                    if progress_callback:
                        try:
                            progress_callback(
                                uploaded_count, total_files, total_files)
                        except Exception:
                            pass

                return success

            except Exception as e:
                self.logger.error(f"批量上传文件失败 {file_path}: {str(e)}")
                with lock:
                    results[s3_key] = False
                    uploaded_count += 1

                    if progress_callback:
                        try:
                            progress_callback(
                                uploaded_count, total_files, total_files)
                        except Exception:
                            pass

                return False

        # 准备文件信息
        file_infos = []
        for i, (file_path, s3_key) in enumerate(zip(file_paths, s3_keys)):
            metadata = metadata_list[i] if metadata_list else None
            content_type = content_types[i] if content_types else None
            acl_value = (
                acl[i]
                if isinstance(acl, (list, tuple))
                else (acl if isinstance(acl, str) else None)
            )
            file_infos.append(
                (file_path, s3_key, metadata, content_type, acl_value))

        # 使用线程池并发上传
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            executor.map(upload_single_file, file_infos)

        # 统计结果
        success_count = sum(1 for success in results.values() if success)
        self.logger.info(f"批量上传完成: {success_count}/{total_files} 成功")

        return results

    def download_file(
        self,
        s3_key: str,
        local_file_path: Union[str, Path],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        """
        稳健地从S3下载文件

        Args:
            s3_key: S3文件键
            local_file_path: 本地保存路径
            progress_callback: 进度回调函数 (downloaded_bytes, total_bytes)

        Returns:
            bool: 下载是否成功
        """
        local_file_path = Path(local_file_path)

        try:
            # 确保本地目录存在
            local_file_path.parent.mkdir(parents=True, exist_ok=True)

            # 检查S3文件是否存在
            if not self.file_exists(s3_key):
                self.logger.error(f"S3文件不存在: {s3_key}")
                return False

            extra_args = {}
            if progress_callback:
                # 获取文件大小
                response = self.s3_client.head_object(
                    Bucket=self.bucket_name, Key=s3_key
                )
                file_size = response["ContentLength"]

                class ProgressWrapper:
                    def __init__(self, callback, total_size):
                        self.callback = callback
                        self.total_size = total_size
                        self.downloaded = 0
                        self.lock = threading.Lock()

                    def __call__(self, bytes_transferred):
                        with self.lock:
                            self.downloaded += bytes_transferred
                            try:
                                self.callback(self.downloaded, self.total_size)
                            except Exception:
                                pass

                extra_args["Callback"] = ProgressWrapper(
                    progress_callback, file_size)

            self.s3_client.download_file(
                self.bucket_name, s3_key, str(local_file_path), ExtraArgs=extra_args
            )

            # 验证下载结果
            if self._verify_download_success(s3_key, local_file_path):
                self.logger.info(
                    f"文件下载成功: s3://{self.bucket_name}/{s3_key} -> {local_file_path}"
                )
                return True
            else:
                self.logger.error(f"文件下载验证失败: {s3_key}")
                return False

        except Exception as e:
            self.logger.error(f"下载文件失败 {s3_key}: {str(e)}")
            return False

    def delete_files(
        self,
        s3_keys: Union[str, list, tuple],
        progress_callback: Optional[Callable[[int, int, int], None]] = None,
        max_workers: int = 5,
    ) -> Union[bool, Dict[str, bool]]:
        """
        删除S3文件，支持单个或多个文件，支持并发删除

        Args:
            s3_keys: S3文件键，可以是单个字符串或列表/元组
            progress_callback: 进度回调函数 (deleted_count, total_files, total_files)
            max_workers: 最大并发工作线程数

        Returns:
            Union[bool, Dict[str, bool]]: 单个文件返回bool，多个文件返回字典
        """
        # 如果是单个文件，转换为列表格式
        is_single_file = isinstance(s3_keys, str)
        if is_single_file:
            s3_keys = [s3_keys]

        # 如果只有一个文件，直接处理单个文件删除
        if len(s3_keys) == 1:
            try:
                self.s3_client.delete_object(
                    Bucket=self.bucket_name, Key=s3_keys[0])
                self.logger.info(
                    f"文件删除成功: s3://{self.bucket_name}/{s3_keys[0]}")
                return True
            except Exception as e:
                self.logger.error(f"删除文件失败 {s3_keys[0]}: {str(e)}")
                return False

        # 多个文件的并发删除逻辑
        results = {}
        total_files = len(s3_keys)
        deleted_count = 0
        lock = threading.Lock()

        def delete_single_file(s3_key):
            nonlocal deleted_count

            try:
                self.s3_client.delete_object(
                    Bucket=self.bucket_name, Key=s3_key)
                self.logger.info(f"文件删除成功: s3://{self.bucket_name}/{s3_key}")

                with lock:
                    results[s3_key] = True
                    deleted_count += 1

                    if progress_callback:
                        try:
                            progress_callback(
                                deleted_count, total_files, total_files)
                        except Exception:
                            pass

                return True

            except Exception as e:
                self.logger.error(f"删除文件失败 {s3_key}: {str(e)}")
                with lock:
                    results[s3_key] = False
                    deleted_count += 1

                    if progress_callback:
                        try:
                            progress_callback(
                                deleted_count, total_files, total_files)
                        except Exception:
                            pass

                return False

        # 使用线程池并发删除
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            executor.map(delete_single_file, s3_keys)

        # 统计结果
        success_count = sum(1 for success in results.values() if success)
        self.logger.info(f"批量删除完成: {success_count}/{total_files} 成功")

        return results if not is_single_file else results.get(s3_keys[0], False)

    def file_exists(self, s3_key: str) -> bool:
        """
        检查文件是否存在

        Args:
            s3_key: S3文件键

        Returns:
            bool: 文件是否存在
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                return False
            else:
                self.logger.error(f"检查文件存在性失败 {s3_key}: {str(e)}")
                return False
        except Exception as e:
            self.logger.error(f"检查文件存在性出错 {s3_key}: {str(e)}")
            return False

    def extract_s3_key(self, url_or_key: Optional[str]) -> Optional[str]:
        """
        将 URL 或 S3 路径规范化为 S3 对象键（Key）。
        兼容以下格式：
        - https://{bucket}.s3.{region}.amazonaws.com/path/to/key
        - https://s3.{region}.amazonaws.com/{bucket}/path/to/key
        - s3://{bucket}/path/to/key
        - path/to/key
        """
        if not url_or_key:
            return None
        try:
            value = url_or_key.strip()
            if value.startswith("s3://"):
                # s3://bucket/key -> 提取 key
                path = value[5:]
                parts = path.split("/", 1)
                return parts[1] if len(parts) > 1 else None

            if value.startswith("http://") or value.startswith("https://"):
                parsed = urlparse(value)
                host = (parsed.netloc or "").lower()
                path = (parsed.path or "").lstrip("/")

                # Path-style: s3.{region}.amazonaws.com/{bucket}/key 或 s3.amazonaws.com/{bucket}/key
                if (
                    host.startswith("s3.")
                    or host == "s3.amazonaws.com"
                    or host.startswith("s3-")
                    or host.startswith("s3.dualstack.")
                ):
                    if path:
                        parts = path.split("/", 1)
                        return parts[1] if len(parts) > 1 else None

                # Virtual-hosted–style: {bucket}.s3.{region}.amazonaws.com/key
                return path or None

            # 已经是 key
            return value.lstrip("/")
        except Exception:
            return url_or_key.lstrip("/")

    def generate_presigned_url(
        self,
        s3_key: str,
        operation: str = "get_object",
        expiration: int = 3600,
        response_content_type: Optional[str] = None,
        response_content_disposition: Optional[str] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        生成预签名URL用于临时访问S3对象

        Args:
            s3_key: S3文件键
            operation: 操作类型，支持 'get_object', 'put_object', 'delete_object'
            expiration: URL过期时间（秒），默认1小时
            response_content_type: 响应内容类型（仅对get_object有效）
            response_content_disposition: 响应内容处置（仅对get_object有效）
            **kwargs: 其他传递给boto3的参数

        Returns:
            str: 预签名URL，失败时返回None
        """
        try:
            # 验证操作类型
            valid_operations = ["get_object", "put_object", "delete_object"]
            if operation not in valid_operations:
                self.logger.error(f"不支持的操作类型: {operation}")
                return None

            # 构建参数（注意：ExpiresIn 只能作为 generate_presigned_url 的顶层参数，不能放入 Params）
            params = {
                "Bucket": self.bucket_name,
                "Key": s3_key,
            }

            # 添加响应参数（仅对get_object有效）
            if operation == "get_object":
                if response_content_type:
                    params["ResponseContentType"] = response_content_type
                if response_content_disposition:
                    params["ResponseContentDisposition"] = response_content_disposition

            # 添加其他参数
            params.update(kwargs)

            # 生成预签名URL
            presigned_url = self.s3_client.generate_presigned_url(
                operation, Params=params, ExpiresIn=expiration
            )

            self.logger.info(
                f"生成预签名URL成功: {operation} {s3_key}, 过期时间: {expiration}秒"
            )
            return presigned_url

        except Exception as e:
            self.logger.error(f"生成预签名URL失败 {s3_key}: {str(e)}")
            return None

    def get_file_url(self, s3_key: str) -> str:
        """
        获取文件URL
        """
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"


# 使用示例和工厂函数
def create_s3_bucket(verify_bucket: bool = True) -> RobustS3Bucket:
    """
    创建RobustS3Bucket实例的工厂函数
    从配置中读取AWS_BUCKET_NAME，固定使用配置的存储桶

    Returns:
        RobustS3Bucket: 配置好的RobustS3Bucket实例
    """
    return RobustS3Bucket(verify_bucket=verify_bucket)
