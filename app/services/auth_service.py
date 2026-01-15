import random
from typing import Dict, Optional, Union
from authlib.integrations.starlette_client import OAuth
from fastapi.security import APIKeyCookie
from fastapi.responses import RedirectResponse
from fastapi import HTTPException, Depends, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.auth_crud import AuthCrud
from app.models.auth_model import CodeType, SocialProvider
from app.utils.email import email_service
from app.core.logger import logger_manager
from app.core.database.mysql import mysql_manager
from app.core.config.settings import settings
from app.core.security import security_manager
from app.core.i18n.i18n import get_message, Language


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.auth_crud = AuthCrud(db)
        self.email_service = email_service
        self.security_manager = security_manager
        self.logger = logger_manager.get_logger(__name__)
        # Oauth Provider
        self.github = OAuth().register(
            name="github",
            client_id=settings.social_account.GITHUB_CLIENT_ID.get_secret_value(),
            client_secret=settings.social_account.GITHUB_CLIENT_SECRET.get_secret_value(),
            access_token_url="https://github.com/login/oauth/access_token",
            authorize_url="https://github.com/login/oauth/authorize",
            client_kwargs={"scope": "user:email"},
        )
        self.google = OAuth().register(
            name="google",
            client_id=settings.social_account.GOOGLE_CLIENT_ID.get_secret_value(),
            client_secret=settings.social_account.GOOGLE_CLIENT_SECRET.get_secret_value(),
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

    def random_username(self) -> str:
        """Generate a random username."""
        username = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=6))
        return username

    def _clear_auth_cookies(self, response: Response) -> None:
        """清理所有认证相关的 cookie
        
        在以下情况调用：
        - Token 解码失败
        - Token 数据不完整
        - Token 刷新失败
        """
        response.delete_cookie(
            "access_token",
            domain=settings.domain.COOKIE_DOMAIN,
            path="/",
        )
        response.delete_cookie(
            "refresh_token",
            domain=settings.domain.COOKIE_DOMAIN,
            path="/",
        )

    def _set_auth_cookies(
        self, 
        response: Response, 
        access_token: str, 
        refresh_token: str
    ) -> None:
        """设置认证相关的 cookie
        
        Args:
            response: FastAPI Response 对象
            access_token: 新的 access token
            refresh_token: 新的 refresh token
        """
        # 设置 access token cookie
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
            domain=settings.domain.COOKIE_DOMAIN,
            max_age=settings.jwt.JWT_ACCESS_TOKEN_EXPIRATION,
        )
        
        # 设置 refresh token cookie
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
            domain=settings.domain.COOKIE_DOMAIN,
            max_age=settings.jwt.JWT_REFRESH_TOKEN_EXPIRATION,
        )

    async def _social_account_login(
        self,
        request,
        email: str,
        username: str,
        avatar_url: str,
        provider: SocialProvider,
        provider_user_id: str,
    ) -> Dict[str, Optional[str]]:
        """Social account login."""
        # 创建或更新社交账户
        tokens = await self.auth_crud.social_account_login(
            request=request,
            email=email,
            username=username,
            avatar_url=avatar_url,
            provider=provider,
            provider_user_id=provider_user_id,
        )
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def send_auth_code_email(self, email: str, type: CodeType) -> bool:
        # 生成验证码
        code = str(random.randint(100000, 999999))  # 生成6位随机验证码

        # 保存验证码
        await self.auth_crud.create_code_crud(email=email, type=type, code=code)

        # 获取用户ID（如果用户存在）
        from app.core.i18n.i18n import get_current_language

        current_language = get_current_language()
        if type == CodeType.verified:
            if current_language == Language.ZH_CN:
                subject = f"[{settings.app.APP_NAME}] - 账号激活码"
            else:
                subject = f"[{settings.app.APP_NAME}] - Account Activation Code"
            await self.email_service.send_email(
                subject=subject,
                recipient=email,
                template="verification",
                code=code,
            )
            self.logger.info(f"verification email has been sent to {email}")
        else:
            if current_language == Language.ZH_CN:
                subject = f"[{settings.app.APP_NAME}] - 密码重置码"
            else:
                subject = f"[{settings.app.APP_NAME}] - Password Reset Code"
            await self.email_service.send_email(
                subject=subject,
                recipient=email,
                template="resetcode",
                code=code,
            )
            self.logger.info(f"password reset email has been sent to {email}")

        return True

    async def create_user_account(
        self, email: str, username: str, password: str, code: str
    ) -> bool:
        """Create a new user account."""
        # 检查密码是否符合要求
        if not self.security_manager.validate_password(password):
            raise HTTPException(
                status_code=400,
                detail=get_message("auth.common.invalidPassword"),
            )

        # 加密密码
        password_hash = self.security_manager.hash_password(password)

        # 创建用户
        await self.auth_crud.create_user_account(
            email=email,
            username=username,
            password_hash=password_hash,
            code=code,
            type=CodeType.verified,
        )

        return True

    async def reset_user_password(
        self, email: str, new_password: str, code: str
    ) -> bool:
        """Reset user password."""
        # 检查密码是否符合要求
        if not self.security_manager.validate_password(new_password):
            raise HTTPException(
                status_code=400,
                detail=get_message("auth.common.invalidPassword"),
            )

        # 重置密码
        result = await self.auth_crud.reset_user_password(
            email=email, new_password=new_password, code=code
        )

        return result

    async def account_login(
        self,
        request,
        email: str,
        password: str,
        response: Response,
    ) -> bool:
        """User account login."""
        token_data = await self.auth_crud.account_login(
            request=request, email=email, password=password
        )

        # 设置access token cookie
        response.set_cookie(
            key="access_token",
            value=token_data["access_token"],
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
            domain=settings.domain.COOKIE_DOMAIN,
            max_age=settings.jwt.JWT_ACCESS_TOKEN_EXPIRATION,
        )

        # 设置refresh token cookie
        response.set_cookie(
            key="refresh_token",
            value=token_data["refresh_token"],
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
            domain=settings.domain.COOKIE_DOMAIN,
            max_age=settings.jwt.JWT_REFRESH_TOKEN_EXPIRATION,
        )

        return True

    async def account_logout(
        self, request: Request, response: Response, user_id: int
    ) -> bool:
        """User account logout - Revoke all user tokens and blacklist access token."""
        try:
            # 获取 access token 的 JTI（用于加入黑名单）
            access_token_cookie = APIKeyCookie(name="access_token", auto_error=False)
            access_token = await access_token_cookie(request)
            access_token_jti = None

            if access_token:
                token_data = self.security_manager.decode_token(access_token)
                if token_data:
                    access_token_jti = token_data.get("jti")

            # 撤销所有 refresh token 并将 access token 加入黑名单
            await self.auth_crud.account_logout(
                user_id=user_id, access_token_jti=access_token_jti
            )

            # 清理用户的cookies
            response.delete_cookie(
                "access_token",
                domain=settings.domain.COOKIE_DOMAIN,
                path="/",
            )
            response.delete_cookie(
                "refresh_token",
                domain=settings.domain.COOKIE_DOMAIN,
                path="/",
            )
            self.logger.info(f"User tokens cleaned up for user_id: {user_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error cleaning up user tokens: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=get_message("auth.common.internalError"),
            )

    async def generate_access_token(
        self, request, response: Response
    ) -> Dict[str, str]:
        """Generate access token and rotate refresh token for user
        
        实现 Token Rotation：返回新的 access token 和 refresh token
        
        Args:
            request: FastAPI Request 对象
            response: FastAPI Response 对象
            
        Returns:
            包含 access_token 和 refresh_token 的字典
            
        Raises:
            HTTPException: Token 无效、过期或刷新失败时
        """
        # 步骤 1: 获取 refresh_token
        refresh_cookie_token = APIKeyCookie(name="refresh_token", auto_error=False)
        refresh_token = await refresh_cookie_token(request)

        if not refresh_token:
            raise HTTPException(
                status_code=404,
                detail=get_message("auth.generateAccessToken.refreshTokenNotFound"),
            )

        # 步骤 2: 解码 refresh_token
        token_data = self.security_manager.decode_token(refresh_token)
        if not token_data:
            self._clear_auth_cookies(response)
            raise HTTPException(
                status_code=401,
                detail=get_message("common.insufficientPermissions"),
            )

        # 步骤 3: 验证 token 数据完整性
        user_id = token_data.get("user_id")
        email_id = token_data.get("email")
        jit = token_data.get("jti")

        if not user_id or not email_id or not jit:
            self._clear_auth_cookies(response)
            raise HTTPException(
                status_code=401,
                detail=get_message("common.insufficientPermissions"),
            )

        # 步骤 4: 生成新的 token 对（Token Rotation）
        try:
            tokens = await self.auth_crud.generate_access_token(
                user_id=user_id,
                email=email_id,
                jit=jit,
            )
        except HTTPException:
            self._clear_auth_cookies(response)
            raise

        # 步骤 5: 设置新的 cookie
        self._set_auth_cookies(
            response,
            tokens["access_token"],
            tokens["refresh_token"],
        )

        return tokens

    async def check_auth_token(self, request) -> Dict[str, Union[str, bool]]:
        """Check access token."""
        access_token = APIKeyCookie(name="access_token", auto_error=False)
        access_token = await access_token(request)
        refresh_token = APIKeyCookie(name="refresh_token", auto_error=False)
        refresh_token = await refresh_token(request)
        if not access_token and not refresh_token:
            return {
                "access_token": False,
                "refresh_token": False,
            }
        elif access_token and not refresh_token:
            access_token_data = self.security_manager.decode_token(access_token)
            if not access_token_data:
                return {
                    "access_token": False,
                    "refresh_token": False,
                }
            else:
                return {
                    "access_token": True,
                    "refresh_token": False,
                }
        elif refresh_token and not access_token:
            refresh_token_data = self.security_manager.decode_token(refresh_token)
            if not refresh_token_data:
                return {
                    "access_token": False,
                    "refresh_token": False,
                }
            else:
                return {
                    "access_token": False,
                    "refresh_token": True,
                }
        else:
            return {
                "access_token": True,
                "refresh_token": True,
            }

    async def github_login(
        self,
        request,
    ):
        """GitHub login."""
        redirect_uri = str(settings.social_account.GITHUB_REDIRECT_URI)
        return await self.github.authorize_redirect(request, redirect_uri)

    async def github_callback(
        self,
        request,
    ) -> RedirectResponse:
        """GitHub callback."""
        token = await self.github.authorize_access_token(request)
        if not token:
            raise HTTPException(
                status_code=404,
                detail=get_message("auth.githubCallback.githubTokenNotFound"),
            )
        user_info = await self.github.get("https://api.github.com/user", token=token)
        user_info = user_info.json()
        email = user_info.get("email")
        avatar_url = user_info.get("avatar_url")
        if not email:
            email_response = await self.github.get(
                "https://api.github.com/user/emails", token=token
            )
            if email_response.status_code == 200:
                email_data = email_response.json()
                primary_email = next(
                    (
                        e["email"]
                        for e in email_data
                        if e.get("primary") and e.get("verified")
                    ),
                    None,
                )
                if primary_email:
                    email = primary_email
                else:
                    raise HTTPException(
                        status_code=404,
                        detail=get_message("auth.githubCallback.githubEmailNotFound"),
                    )

        # 创建或更新社交账户
        username = user_info.get("login").lower()
        if not username:
            # 如果没有用户名，生成随机名字
            username = self.random_username()

        tokens = await self._social_account_login(
            request=request,
            email=email,
            username=username,
            avatar_url=avatar_url,
            provider=SocialProvider.github,
            provider_user_id=str(user_info.get("id")),
        )

        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        # 跳转到前端
        allowed_origins = [
            x.strip()
            for x in settings.cors.CORS_ALLOWED_ORIGINS.split(",")
            if x.strip()
        ]
        redirect_response = RedirectResponse(
            url=allowed_origins[0]
            if allowed_origins
            else settings.cors.CORS_ALLOWED_ORIGINS.strip()
        )

        # 设置access token cookie
        redirect_response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
            domain=settings.domain.COOKIE_DOMAIN,
            max_age=settings.jwt.JWT_ACCESS_TOKEN_EXPIRATION,
        )

        # 设置refresh token cookie
        redirect_response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
            domain=settings.domain.COOKIE_DOMAIN,
            max_age=settings.jwt.JWT_REFRESH_TOKEN_EXPIRATION,
        )

        return redirect_response

    async def google_login(
        self,
        request,
    ):
        """Google login."""
        redirect_uri = str(settings.social_account.GOOGLE_REDIRECT_URI)
        return await self.google.authorize_redirect(request, redirect_uri)

    async def google_callback(
        self,
        request,
    ) -> RedirectResponse:
        """Google callback."""
        tokens = await self.google.authorize_access_token(request)
        if not tokens:
            raise HTTPException(
                status_code=404,
                detail=get_message("auth.googleCallback.googleTokenNotFound"),
            )
        user_info = await self.google.get(
            "https://www.googleapis.com/userinfo/v2/me", token=tokens
        )
        user_info = user_info.json()
        email = user_info.get("email")
        avatar_url = user_info.get("picture")
        if not email:
            raise HTTPException(
                status_code=404,
                detail=get_message("auth.googleCallback.googleEmailNotFound"),
            )
        username = user_info.get("name").lower()
        if not username:
            # 如果没有用户名，生成随机名字
            username = self.random_username()

        tokens = await self._social_account_login(
            request=request,
            email=email,
            username=username,
            avatar_url=avatar_url,
            provider=SocialProvider.google,
            provider_user_id=str(user_info.get("id")),
        )

        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        # 跳转到前端
        allowed_origins = [
            x.strip()
            for x in settings.cors.CORS_ALLOWED_ORIGINS.split(",")
            if x.strip()
        ]
        redirect_response = RedirectResponse(
            url=allowed_origins[0]
            if allowed_origins
            else settings.cors.CORS_ALLOWED_ORIGINS.strip()
        )

        # 设置access token cookie
        redirect_response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
            domain=settings.domain.COOKIE_DOMAIN,
            max_age=settings.jwt.JWT_ACCESS_TOKEN_EXPIRATION,
        )

        # 设置refresh token cookie
        redirect_response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
            domain=settings.domain.COOKIE_DOMAIN,
            max_age=settings.jwt.JWT_REFRESH_TOKEN_EXPIRATION,
        )

        return redirect_response

    async def reset_logged_in_user_password(
        self,
        user_email: str,
        new_password: str,
    ) -> bool:
        """重置已登录用户的密码"""
        await self.auth_crud.reset_logged_in_user_password(
            user_email=user_email, new_password=new_password
        )

        return True


def get_auth_service(db: AsyncSession = Depends(mysql_manager.get_db)) -> AuthService:
    """获取AuthService实例"""
    return AuthService(db)
