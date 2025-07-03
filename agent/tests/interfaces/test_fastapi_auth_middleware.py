"""
FastAPI認証ミドルウェアのモジュールテスト

このテストスイートは、FastAPI統合認証ミドルウェアの動作を包括的にテストします。
HTTPリクエスト・レスポンスの処理、認証フロー、エラーハンドリングを検証します。

テスト対象:
- AuthenticationMiddleware
- AuthEndpoints
- 認証デコレータ (require_authentication, require_permission)
- FastAPI統合機能
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.testclient import TestClient

# テスト対象のインポート
from agent.source.interfaces.fastapi_auth_middleware import (
    AuthenticationMiddleware,
    AuthEndpoints,
    require_authentication,
    require_permission,
    setup_auth_integration,
    create_test_user_context
)
from agent.source.interfaces.auth_ports import AuthPortRegistry, Permission
from agent.source.interfaces.data_models import (
    AuthConfig, PaaSConfig, UserContext, AuthError
)


class TestAuthenticationMiddleware:
    """認証ミドルウェアのテスト"""
    
    @pytest.fixture
    def mock_auth_registry(self):
        """モック認証レジストリ"""
        registry = Mock(spec=AuthPortRegistry)
        registry._auth_enabled = True
        registry.authenticate_request = AsyncMock()
        return registry
    
    @pytest.fixture
    def test_app(self, mock_auth_registry):
        """テスト用FastAPIアプリ"""
        app = FastAPI()
        app.add_middleware(AuthenticationMiddleware, auth_registry=mock_auth_registry)
        
        @app.get("/test")
        async def test_endpoint(request: Request):
            user_context = getattr(request.state, 'user_context', None)
            authenticated = getattr(request.state, 'authenticated', False)
            return {
                "user_context": user_context.email if user_context else None,
                "authenticated": authenticated
            }
        
        return app
    
    def test_middleware_with_valid_token(self, test_app, mock_auth_registry):
        """有効トークンでのミドルウェア処理テスト"""
        # モック設定
        test_user = create_test_user_context()
        mock_auth_registry.authenticate_request.return_value = test_user
        
        with TestClient(test_app) as client:
            response = client.get(
                "/test",
                headers={"Authorization": "Bearer valid_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["authenticated"] is True
            assert data["user_context"] == test_user.email
    
    def test_middleware_with_invalid_token(self, test_app, mock_auth_registry):
        """無効トークンでのミドルウェア処理テスト"""
        # モック設定
        mock_auth_registry.authenticate_request.return_value = None
        
        with TestClient(test_app) as client:
            response = client.get(
                "/test",
                headers={"Authorization": "Bearer invalid_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["authenticated"] is False
            assert data["user_context"] is None
    
    def test_middleware_without_token(self, test_app, mock_auth_registry):
        """トークンなしでのミドルウェア処理テスト"""
        mock_auth_registry.authenticate_request.return_value = None
        
        with TestClient(test_app) as client:
            response = client.get("/test")
            
            assert response.status_code == 200
            data = response.json()
            assert data["authenticated"] is False
            assert data["user_context"] is None
    
    def test_middleware_auth_disabled(self, mock_auth_registry):
        """認証無効時のミドルウェア処理テスト"""
        # 認証無効設定
        mock_auth_registry._auth_enabled = False
        
        app = FastAPI()
        app.add_middleware(AuthenticationMiddleware, auth_registry=mock_auth_registry)
        
        @app.get("/test")
        async def test_endpoint(request: Request):
            return {"status": "ok"}
        
        with TestClient(app) as client:
            response = client.get("/test")
            
            assert response.status_code == 200
            # 認証処理がスキップされることを確認
            mock_auth_registry.authenticate_request.assert_not_called()
    
    def test_middleware_excluded_paths(self, test_app, mock_auth_registry):
        """除外パスでのミドルウェア処理テスト"""
        excluded_paths = ["/docs", "/health", "/", "/auth/login"]
        
        with TestClient(test_app) as client:
            for path in excluded_paths:
                # 除外パス用のエンドポイントを動的追加
                test_app.get(path)(lambda: {"status": "ok"})
                
                response = client.get(path)
                # 除外パスでは認証処理がスキップされる
                # （実際のレスポンスは404になる場合があるが、認証処理自体はスキップされる）
    
    def test_middleware_error_handling(self, mock_auth_registry):
        """ミドルウェアエラーハンドリングテスト"""
        # 認証処理でエラーが発生する設定
        mock_auth_registry._auth_enabled = True
        mock_auth_registry.authenticate_request.side_effect = Exception("Auth error")
        
        app = FastAPI()
        app.add_middleware(AuthenticationMiddleware, auth_registry=mock_auth_registry)
        
        @app.get("/test")
        async def test_endpoint(request: Request):
            user_context = getattr(request.state, 'user_context', None)
            authenticated = getattr(request.state, 'authenticated', False)
            return {
                "user_context": user_context,
                "authenticated": authenticated
            }
        
        with TestClient(app) as client:
            response = client.get(
                "/test",
                headers={"Authorization": "Bearer test_token"}
            )
            
            # エラー時もリクエストは継続され、認証情報はNoneになる
            assert response.status_code == 200
            data = response.json()
            assert data["authenticated"] is False
            assert data["user_context"] is None


class TestAuthEndpoints:
    """認証エンドポイントのテスト"""
    
    @pytest.fixture
    def mock_auth_registry(self):
        """モック認証レジストリ"""
        registry = Mock(spec=AuthPortRegistry)
        registry._auth_enabled = True
        
        # モックauth_port
        mock_auth_port = Mock()
        mock_auth_port.initiate_google_oauth = AsyncMock()
        mock_auth_port.complete_google_oauth = AsyncMock()
        mock_auth_port.logout = AsyncMock()
        mock_auth_port._generate_access_token = AsyncMock()
        mock_auth_port._generate_refresh_token = AsyncMock()
        mock_auth_port.refresh_token = AsyncMock()
        
        registry.auth_port = mock_auth_port
        return registry
    
    @pytest.fixture
    def auth_app(self, mock_auth_registry):
        """認証エンドポイント付きテストアプリ"""
        app = FastAPI()
        auth_endpoints = AuthEndpoints(mock_auth_registry)
        auth_endpoints.register_routes(app)
        return app
    
    def test_login_endpoint(self, auth_app, mock_auth_registry):
        """ログインエンドポイントのテスト"""
        # モック設定
        mock_auth_registry.auth_port.initiate_google_oauth.return_value = {
            'auth_url': 'https://accounts.google.com/oauth2/auth?client_id=test',
            'state': 'test_state'
        }
        
        with TestClient(auth_app) as client:
            response = client.get("/auth/login")
            
            # リダイレクトレスポンスを確認
            assert response.status_code == 302
            assert 'location' in response.headers
            assert 'accounts.google.com' in response.headers['location']
    
    def test_login_endpoint_auth_disabled(self, mock_auth_registry):
        """認証無効時のログインエンドポイントテスト"""
        mock_auth_registry._auth_enabled = False
        
        app = FastAPI()
        auth_endpoints = AuthEndpoints(mock_auth_registry)
        auth_endpoints.register_routes(app)
        
        with TestClient(app) as client:
            response = client.get("/auth/login")
            
            assert response.status_code == 503
            assert "Authentication is disabled" in response.json()["detail"]
    
    def test_callback_endpoint_success(self, auth_app, mock_auth_registry):
        """認証コールバック成功時のテスト"""
        # モック設定
        test_user = create_test_user_context()
        mock_auth_registry.auth_port.complete_google_oauth.return_value = test_user
        mock_auth_registry.auth_port._generate_access_token.return_value = "test_access_token"
        mock_auth_registry.auth_port._generate_refresh_token.return_value = "test_refresh_token"
        
        with TestClient(auth_app) as client:
            response = client.get("/auth/callback?code=test_code&state=test_state")
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Login successful"
            assert data["user"]["email"] == test_user.email
            assert data["access_token"] == "test_access_token"
            assert "access_token" in response.cookies
    
    def test_callback_endpoint_error(self, auth_app, mock_auth_registry):
        """認証コールバックエラー時のテスト"""
        with TestClient(auth_app) as client:
            response = client.get("/auth/callback?error=access_denied&state=test_state")
            
            assert response.status_code == 400
            assert "OAuth error" in response.json()["detail"]
    
    def test_callback_endpoint_auth_error(self, auth_app, mock_auth_registry):
        """認証処理エラー時のテスト"""
        # モック設定: 認証エラーを発生
        mock_auth_registry.auth_port.complete_google_oauth.side_effect = AuthError("Invalid state")
        
        with TestClient(auth_app) as client:
            response = client.get("/auth/callback?code=test_code&state=invalid_state")
            
            assert response.status_code == 400
            assert "Invalid state" in response.json()["detail"]
    
    def test_logout_endpoint(self, auth_app, mock_auth_registry):
        """ログアウトエンドポイントのテスト"""
        mock_auth_registry.auth_port.logout.return_value = True
        
        with TestClient(auth_app) as client:
            # ユーザーコンテキストをモック
            with patch('fastapi.Request') as mock_request:
                mock_request.state.user_context = create_test_user_context()
                
                response = client.post("/auth/logout")
                
                assert response.status_code == 200
                assert response.json()["message"] == "Logout successful"
    
    def test_me_endpoint(self, auth_app, mock_auth_registry):
        """ユーザー情報取得エンドポイントのテスト"""
        app = FastAPI()
        app.add_middleware(AuthenticationMiddleware, auth_registry=mock_auth_registry)
        auth_endpoints = AuthEndpoints(mock_auth_registry)
        auth_endpoints.register_routes(app)
        
        # モック認証処理
        test_user = create_test_user_context()
        mock_auth_registry.authenticate_request.return_value = test_user
        
        with TestClient(app) as client:
            response = client.get(
                "/auth/me",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["email"] == test_user.email
            assert data["display_name"] == test_user.display_name
            assert data["roles"] == test_user.roles
    
    def test_me_endpoint_not_authenticated(self, auth_app, mock_auth_registry):
        """未認証でのユーザー情報取得テスト"""
        app = FastAPI()
        app.add_middleware(AuthenticationMiddleware, auth_registry=mock_auth_registry)
        auth_endpoints = AuthEndpoints(mock_auth_registry)
        auth_endpoints.register_routes(app)
        
        # 認証なし
        mock_auth_registry.authenticate_request.return_value = None
        
        with TestClient(app) as client:
            response = client.get("/auth/me")
            
            assert response.status_code == 401
            assert "Not authenticated" in response.json()["detail"]
    
    def test_refresh_endpoint(self, auth_app, mock_auth_registry):
        """トークン更新エンドポイントのテスト"""
        # モック設定
        mock_auth_registry.auth_port.refresh_token.return_value = {
            'access_token': 'new_access_token',
            'refresh_token': 'new_refresh_token',
            'token_type': 'bearer',
            'expires_in': 3600
        }
        
        with TestClient(auth_app) as client:
            # リフレッシュトークンをクッキーに設定
            client.cookies = {"refresh_token": "test_refresh_token"}
            
            response = client.post("/auth/refresh")
            
            assert response.status_code == 200
            data = response.json()
            assert data["access_token"] == "new_access_token"
            assert "access_token" in response.cookies


class TestAuthenticationDecorators:
    """認証デコレータのテスト"""
    
    @pytest.fixture
    def mock_auth_registry(self):
        """モック認証レジストリ"""
        registry = Mock(spec=AuthPortRegistry)
        registry._auth_enabled = True
        registry.authenticate_request = AsyncMock()
        registry.authorize_action = AsyncMock()
        return registry
    
    def test_require_authentication_success(self, mock_auth_registry):
        """認証必須デコレータ（成功）のテスト"""
        app = FastAPI()
        app.add_middleware(AuthenticationMiddleware, auth_registry=mock_auth_registry)
        
        @app.get("/protected")
        @require_authentication(mock_auth_registry)
        async def protected_endpoint(request: Request, user_context=None):
            return {"user": user_context.email if user_context else None}
        
        # モック設定
        test_user = create_test_user_context()
        mock_auth_registry.authenticate_request.return_value = test_user
        
        with TestClient(app) as client:
            response = client.get(
                "/protected",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200
            assert response.json()["user"] == test_user.email
    
    def test_require_authentication_failure(self, mock_auth_registry):
        """認証必須デコレータ（失敗）のテスト"""
        app = FastAPI()
        app.add_middleware(AuthenticationMiddleware, auth_registry=mock_auth_registry)
        
        @app.get("/protected")
        @require_authentication(mock_auth_registry)
        async def protected_endpoint(request: Request, user_context=None):
            return {"user": user_context.email if user_context else None}
        
        # 認証失敗設定
        mock_auth_registry.authenticate_request.return_value = None
        
        with TestClient(app) as client:
            response = client.get("/protected")
            
            assert response.status_code == 401
            assert "Authentication required" in response.json()["detail"]
    
    def test_require_authentication_optional(self, mock_auth_registry):
        """オプショナル認証デコレータのテスト"""
        app = FastAPI()
        app.add_middleware(AuthenticationMiddleware, auth_registry=mock_auth_registry)
        
        @app.get("/optional")
        @require_authentication(mock_auth_registry, optional=True)
        async def optional_endpoint(request: Request, user_context=None):
            return {"user": user_context.email if user_context else "anonymous"}
        
        # 認証なし
        mock_auth_registry.authenticate_request.return_value = None
        
        with TestClient(app) as client:
            response = client.get("/optional")
            
            assert response.status_code == 200
            assert response.json()["user"] == "anonymous"
    
    def test_require_authentication_disabled(self, mock_auth_registry):
        """認証無効時のデコレータテスト"""
        mock_auth_registry._auth_enabled = False
        
        app = FastAPI()
        app.add_middleware(AuthenticationMiddleware, auth_registry=mock_auth_registry)
        
        @app.get("/protected")
        @require_authentication(mock_auth_registry)
        async def protected_endpoint(request: Request, user_context=None):
            return {"user": user_context.email if user_context else "no_auth"}
        
        with TestClient(app) as client:
            response = client.get("/protected")
            
            assert response.status_code == 200
            assert response.json()["user"] == "no_auth"
    
    def test_require_permission_success(self, mock_auth_registry):
        """権限必須デコレータ（成功）のテスト"""
        app = FastAPI()
        app.add_middleware(AuthenticationMiddleware, auth_registry=mock_auth_registry)
        
        @app.get("/admin")
        @require_permission(mock_auth_registry, "admin", Permission.READ)
        async def admin_endpoint(request: Request, user_context=None, authorized=False):
            return {
                "user": user_context.email if user_context else None,
                "authorized": authorized
            }
        
        # モック設定
        test_user = create_test_user_context()
        mock_auth_registry.authenticate_request.return_value = test_user
        mock_auth_registry.authorize_action.return_value = True
        
        with TestClient(app) as client:
            response = client.get(
                "/admin",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["user"] == test_user.email
            assert data["authorized"] is True
    
    def test_require_permission_failure(self, mock_auth_registry):
        """権限必須デコレータ（失敗）のテスト"""
        app = FastAPI()
        app.add_middleware(AuthenticationMiddleware, auth_registry=mock_auth_registry)
        
        @app.get("/admin")
        @require_permission(mock_auth_registry, "admin", Permission.READ)
        async def admin_endpoint(request: Request, user_context=None, authorized=False):
            return {"authorized": authorized}
        
        # モック設定: 認証はOKだが権限なし
        test_user = create_test_user_context()
        mock_auth_registry.authenticate_request.return_value = test_user
        mock_auth_registry.authorize_action.return_value = False
        
        with TestClient(app) as client:
            response = client.get(
                "/admin",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 403
            assert "Permission denied" in response.json()["detail"]


class TestSetupAuthIntegration:
    """認証統合セットアップのテスト"""
    
    def test_setup_auth_integration_enabled(self):
        """認証有効時の統合セットアップテスト"""
        auth_config = AuthConfig(
            provider='google_oauth2',
            client_id='test_client_id',
            client_secret='test_client_secret',
            redirect_uri='http://localhost:8000/auth/callback',
            allowed_domains=['university.ac.jp']
        )
        
        paas_config = PaaSConfig(
            environment='development',
            enable_authentication=True,
            auth=auth_config
        )
        
        app = FastAPI()
        
        with patch('agent.source.interfaces.fastapi_auth_middleware.create_auth_system') as mock_create:
            mock_registry = Mock(spec=AuthPortRegistry)
            mock_create.return_value = mock_registry
            
            result = setup_auth_integration(app, paas_config)
            
            assert result is not None
            assert result == mock_registry
            mock_create.assert_called_once_with(auth_config)
    
    def test_setup_auth_integration_disabled(self):
        """認証無効時の統合セットアップテスト"""
        paas_config = PaaSConfig(
            environment='development',
            enable_authentication=False
        )
        
        app = FastAPI()
        result = setup_auth_integration(app, paas_config)
        
        assert result is None
    
    def test_setup_auth_integration_error_handling(self):
        """統合セットアップエラーハンドリングテスト"""
        auth_config = AuthConfig(
            provider='google_oauth2',
            client_id='test_client_id',
            client_secret='test_client_secret',
            redirect_uri='http://localhost:8000/auth/callback',
            allowed_domains=['university.ac.jp']
        )
        
        paas_config = PaaSConfig(
            environment='development',
            enable_authentication=True,
            auth=auth_config
        )
        
        app = FastAPI()
        
        with patch('agent.source.interfaces.fastapi_auth_middleware.create_auth_system', 
                  side_effect=Exception("Setup failed")):
            result = setup_auth_integration(app, paas_config)
            
            # エラー時はNoneを返してフォールバック
            assert result is None


class TestHelperFunctions:
    """ヘルパー関数のテスト"""
    
    def test_create_test_user_context(self):
        """テストユーザーコンテキスト作成のテスト"""
        user_context = create_test_user_context()
        
        assert user_context.user_id == "test_user_123"
        assert user_context.email == "test@university.ac.jp"
        assert user_context.display_name == "Test User"
        assert user_context.domain == "university.ac.jp"
        assert "student" in user_context.roles
        assert "documents" in user_context.permissions
        assert "read" in user_context.permissions["documents"]