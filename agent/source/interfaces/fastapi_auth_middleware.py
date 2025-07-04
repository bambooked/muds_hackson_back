"""
FastAPI認証ミドルウェア

このモジュールは、既存のpaas_api.pyに非破壊的に統合可能な認証ミドルウェアを提供します。
設定による機能切り替えをサポートし、認証無効時は既存システムを完全に保護します。

主要機能:
- リクエスト認証ミドルウェア
- 権限チェックデコレータ
- OAuth2エンドポイント
- セッション管理
- 既存APIの段階的セキュア化
"""

import os
import logging
from typing import Optional, Callable, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse, JSONResponse
try:
    from fastapi.middleware.base import BaseHTTPMiddleware
except ImportError:
    # Fallback for older FastAPI versions
    from starlette.middleware.base import BaseHTTPMiddleware

from .auth_ports import AuthPortRegistry, Permission
from .auth_implementations import create_auth_system
from .data_models import UserContext, AuthConfig, AuthError, PaaSConfig

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    認証ミドルウェア
    
    機能:
    - リクエストからトークン抽出
    - ユーザーコンテキスト設定
    - 認証無効時の透過的処理
    """
    
    def __init__(self, app: FastAPI, auth_registry: AuthPortRegistry):
        super().__init__(app)
        self.auth_registry = auth_registry
        self.security = HTTPBearer(auto_error=False)
    
    async def dispatch(self, request: Request, call_next: Callable):
        """リクエスト処理"""
        try:
            # 認証が無効な場合は既存システムそのまま
            if not self.auth_registry._auth_enabled:
                return await call_next(request)
            
            # 認証除外パス
            excluded_paths = [
                '/docs', '/redoc', '/openapi.json',
                '/health', '/',
                '/auth/login', '/auth/callback', '/auth/logout'
            ]
            
            if request.url.path in excluded_paths:
                return await call_next(request)
            
            # トークン取得
            token = await self._extract_token(request)
            user_context = None
            
            if token:
                user_context = await self.auth_registry.authenticate_request(token)
            
            # ユーザーコンテキストをリクエストに設定
            request.state.user_context = user_context
            request.state.authenticated = user_context is not None
            
            response = await call_next(request)
            return response
            
        except Exception as e:
            logger.error(f"Authentication middleware error: {e}")
            # エラー時は認証なしで継続（既存システム保護）
            request.state.user_context = None
            request.state.authenticated = False
            return await call_next(request)
    
    async def _extract_token(self, request: Request) -> Optional[str]:
        """リクエストからトークン抽出"""
        # Authorization ヘッダー
        authorization = request.headers.get('Authorization')
        if authorization and authorization.startswith('Bearer '):
            return authorization[7:]
        
        # Cookie
        token = request.cookies.get('access_token')
        if token:
            return token
        
        # Query parameter (非推奨だが緊急時用)
        token = request.query_params.get('token')
        if token:
            return token
        
        return None


class AuthEndpoints:
    """
    認証関連エンドポイント
    
    機能:
    - OAuth2ログイン
    - コールバック処理
    - ログアウト
    - ユーザー情報取得
    """
    
    def __init__(self, auth_registry: AuthPortRegistry):
        self.auth_registry = auth_registry
        self.security = HTTPBearer(auto_error=False)
    
    def register_routes(self, app: FastAPI):
        """認証ルートを登録"""
        
        @app.get("/auth/login")
        async def login(request: Request, redirect_url: Optional[str] = None):
            """Google OAuth2ログイン開始"""
            if not self.auth_registry._auth_enabled:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication is disabled"
                )
            
            try:
                # リダイレクトURI構築
                base_url = str(request.base_url).rstrip('/')
                callback_uri = f"{base_url}/auth/callback"
                
                # OAuth2フロー開始
                auth_result = await self.auth_registry.auth_port.initiate_google_oauth(
                    redirect_uri=callback_uri
                )
                
                # State にリダイレクト先を保存
                if redirect_url:
                    # 簡易実装: 実際はセッションストレージを使用
                    pass
                
                return RedirectResponse(
                    url=auth_result['auth_url'],
                    status_code=status.HTTP_302_FOUND
                )
                
            except AuthError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
            except Exception as e:
                logger.error(f"Login initiation failed: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Login initiation failed"
                )
        
        @app.get("/auth/callback")
        async def callback(
            request: Request,
            code: str,
            state: str,
            error: Optional[str] = None
        ):
            """OAuth2コールバック処理"""
            if not self.auth_registry._auth_enabled:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication is disabled"
                )
            
            if error:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"OAuth error: {error}"
                )
            
            try:
                # コールバックURI構築
                base_url = str(request.base_url).rstrip('/')
                callback_uri = f"{base_url}/auth/callback"
                
                # OAuth2フロー完了
                user_context = await self.auth_registry.auth_port.complete_google_oauth(
                    authorization_code=code,
                    state=state,
                    redirect_uri=callback_uri
                )
                
                # JWT トークン生成
                access_token = await self.auth_registry.auth_port._generate_access_token(user_context)
                refresh_token = await self.auth_registry.auth_port._generate_refresh_token(user_context)
                
                # レスポンス作成
                response = JSONResponse({
                    "message": "Login successful",
                    "user": {
                        "email": user_context.email,
                        "display_name": user_context.display_name,
                        "roles": user_context.roles
                    },
                    "access_token": access_token,
                    "token_type": "bearer",
                    "expires_in": 3600
                })
                
                # セキュアクッキーにトークン設定
                response.set_cookie(
                    key="access_token",
                    value=access_token,
                    max_age=3600,
                    httponly=True,
                    secure=True,
                    samesite="lax"
                )
                
                response.set_cookie(
                    key="refresh_token", 
                    value=refresh_token,
                    max_age=30*24*3600,  # 30日
                    httponly=True,
                    secure=True,
                    samesite="lax"
                )
                
                return response
                
            except AuthError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
            except Exception as e:
                logger.error(f"OAuth callback failed: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Authentication failed"
                )
        
        @app.post("/auth/logout")
        async def logout(request: Request):
            """ログアウト"""
            if not self.auth_registry._auth_enabled:
                return {"message": "Authentication is disabled"}
            
            try:
                user_context = getattr(request.state, 'user_context', None)
                if user_context:
                    await self.auth_registry.auth_port.logout(
                        user_id=user_context.user_id,
                        session_id=user_context.session_id
                    )
                
                response = JSONResponse({"message": "Logout successful"})
                response.delete_cookie("access_token")
                response.delete_cookie("refresh_token")
                
                return response
                
            except Exception as e:
                logger.error(f"Logout failed: {e}")
                return JSONResponse(
                    {"message": "Logout completed"},
                    status_code=status.HTTP_200_OK
                )
        
        @app.get("/auth/me")
        async def get_current_user(request: Request):
            """現在のユーザー情報取得"""
            if not self.auth_registry._auth_enabled:
                return {"message": "Authentication is disabled"}
            
            user_context = getattr(request.state, 'user_context', None)
            if not user_context:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated"
                )
            
            return {
                "user_id": user_context.user_id,
                "email": user_context.email,
                "display_name": user_context.display_name,
                "domain": user_context.domain,
                "roles": user_context.roles,
                "permissions": user_context.permissions,
                "session_id": user_context.session_id,
                "expires_at": user_context.expires_at.isoformat() if user_context.expires_at else None
            }
        
        @app.post("/auth/refresh")
        async def refresh_token(request: Request):
            """トークン更新"""
            if not self.auth_registry._auth_enabled:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication is disabled"
                )
            
            try:
                refresh_token = request.cookies.get('refresh_token')
                if not refresh_token:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Refresh token not found"
                    )
                
                token_response = await self.auth_registry.auth_port.refresh_token(refresh_token)
                if not token_response:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token refresh failed"
                    )
                
                response = JSONResponse(token_response)
                
                # 新しいトークンをクッキーに設定
                response.set_cookie(
                    key="access_token",
                    value=token_response['access_token'],
                    max_age=3600,
                    httponly=True,
                    secure=True,
                    samesite="lax"
                )
                
                if 'refresh_token' in token_response:
                    response.set_cookie(
                        key="refresh_token",
                        value=token_response['refresh_token'],
                        max_age=30*24*3600,
                        httponly=True,
                        secure=True,
                        samesite="lax"
                    )
                
                return response
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Token refresh failed"
                )


def require_authentication(
    auth_registry: AuthPortRegistry,
    optional: bool = False
):
    """
    認証必須デコレータ
    
    Args:
        auth_registry: 認証レジストリ
        optional: Trueの場合、認証なしでも継続（user_contextはNoneになる）
    """
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            if not auth_registry._auth_enabled:
                # 認証無効時
                kwargs['user_context'] = None
                return await func(request, *args, **kwargs)
            
            user_context = getattr(request.state, 'user_context', None)
            
            if not optional and not user_context:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            kwargs['user_context'] = user_context
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def require_permission(
    auth_registry: AuthPortRegistry,
    resource: str,
    action: Permission,
    optional: bool = False
):
    """
    権限必須デコレータ
    
    Args:
        auth_registry: 認証レジストリ
        resource: リソース名
        action: 必要な権限
        optional: Trueの場合、権限なしでも継続
    """
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            if not auth_registry._auth_enabled:
                # 認証無効時は全許可
                kwargs['user_context'] = None
                return await func(request, *args, **kwargs)
            
            user_context = getattr(request.state, 'user_context', None)
            
            if not user_context:
                if not optional:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required"
                    )
                kwargs['user_context'] = None
                return await func(request, *args, **kwargs)
            
            # 権限チェック
            authorized = await auth_registry.authorize_action(
                user_context, resource, action
            )
            
            if not authorized and not optional:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {resource}:{action.value}"
                )
            
            kwargs['user_context'] = user_context
            kwargs['authorized'] = authorized
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def setup_auth_integration(
    app: FastAPI,
    config: PaaSConfig
) -> Optional[AuthPortRegistry]:
    """
    既存FastAPIアプリケーションに認証システムを統合
    
    Args:
        app: FastAPIアプリケーション
        config: PaaS設定
        
    Returns:
        AuthPortRegistry: 認証レジストリ（認証無効時はNone）
    """
    try:
        if not config.enable_authentication or not config.auth:
            logger.info("Authentication is disabled")
            return None
        
        # 認証システム作成
        auth_registry = create_auth_system(config.auth)
        auth_registry.enable_authentication(True)
        
        # ミドルウェア追加
        app.add_middleware(AuthenticationMiddleware, auth_registry=auth_registry)
        
        # 認証エンドポイント追加
        auth_endpoints = AuthEndpoints(auth_registry)
        auth_endpoints.register_routes(app)
        
        logger.info("Authentication system integrated successfully")
        return auth_registry
        
    except Exception as e:
        logger.error(f"Authentication integration failed: {e}")
        logger.warning("Continuing without authentication")
        return None


# 使用例とテストヘルパー

def create_test_user_context() -> UserContext:
    """テスト用ユーザーコンテキスト作成"""
    return UserContext(
        user_id="test_user_123",
        email="test@university.ac.jp",
        display_name="Test User",
        domain="university.ac.jp",
        roles=["student"],
        permissions={
            "documents": ["read", "write"],
            "search": ["read"]
        },
        session_id="test_session_123",
        expires_at=datetime.now()
    )


async def test_auth_integration():
    """認証統合のテスト関数"""
    from fastapi import FastAPI
    
    app = FastAPI()
    
    # テスト用設定
    auth_config = AuthConfig(
        provider="google_oauth2",
        client_id="test_client_id",
        client_secret="test_client_secret", 
        redirect_uri="http://localhost:8000/auth/callback",
        allowed_domains=["university.ac.jp"]
    )
    
    paas_config = PaaSConfig(
        environment="development",
        enable_authentication=True,
        auth=auth_config
    )
    
    # 認証統合
    auth_registry = setup_auth_integration(app, paas_config)
    
    if auth_registry:
        
        @app.get("/test/public")
        async def public_endpoint():
            return {"message": "Public endpoint"}
        
        @app.get("/test/authenticated") 
        @require_authentication(auth_registry)
        async def authenticated_endpoint(request: Request, user_context: Optional[UserContext] = None):
            if user_context:
                return {"message": f"Hello, {user_context.display_name}"}
            else:
                return {"message": "Hello, anonymous"}
        
        @app.get("/test/admin")
        @require_permission(auth_registry, "admin", Permission.READ)
        async def admin_endpoint(
            request: Request, 
            user_context: Optional[UserContext] = None,
            authorized: bool = False
        ):
            return {
                "message": "Admin endpoint",
                "user": user_context.email if user_context else None,
                "authorized": authorized
            }
    
    return app, auth_registry


if __name__ == "__main__":
    # テスト実行例
    import asyncio
    
    async def main():
        app, auth_registry = await test_auth_integration()
        print("Authentication integration test completed")
        
        if auth_registry:
            print("Authentication enabled")
        else:
            print("Authentication disabled")
    
    asyncio.run(main())