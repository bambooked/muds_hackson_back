"""
簡略化された認証システムテスト

デコレータの問題を回避し、核心機能に集中したテストを実装します。
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

# テスト対象のインポート
from agent.source.interfaces.auth_implementations import (
    GoogleOAuth2Authentication,
    DatabaseUserManagement,
    RoleBasedAuthorization,
    create_auth_system
)
from agent.source.interfaces.auth_ports import (
    UserRole, Permission, AuthPortRegistry
)
from agent.source.interfaces.data_models import (
    AuthConfig, UserContext, AuthError
)


class TestCoreAuthenticationLogic:
    """核心認証ロジックのテスト"""
    
    @pytest.fixture
    def auth_config(self):
        """テスト用認証設定"""
        return AuthConfig(
            provider='google_oauth2',
            client_id='test_client_id',
            client_secret='test_client_secret',
            redirect_uri='http://localhost:8000/auth/callback',
            allowed_domains=['university.ac.jp', 'test.edu'],
            session_timeout_minutes=480
        )
    
    @pytest.mark.asyncio
    async def test_jwt_token_lifecycle(self, auth_config):
        """JWTトークンのライフサイクルテスト"""
        with patch.dict('os.environ', {'JWT_SECRET_KEY': 'test_secret'}):
            auth = GoogleOAuth2Authentication(auth_config)
            
            # テストユーザー作成
            user_context = UserContext(
                user_id='test_user_123',
                email='test@university.ac.jp',
                display_name='Test User',
                domain='university.ac.jp',
                roles=['student'],
                permissions={'documents': ['read', 'write']},
                session_id='test_session'
            )
            
            # アクセストークン生成
            access_token = await auth._generate_access_token(user_context)
            assert access_token is not None
            assert len(access_token) > 50  # JWTトークンの長さ確認
            
            # リフレッシュトークン生成
            refresh_token = await auth._generate_refresh_token(user_context)
            assert refresh_token is not None
            assert len(refresh_token) > 50
            
            # アクセストークンとリフレッシュトークンは異なる
            assert access_token != refresh_token
            
            # トークン検証（セッションモック）
            with patch.object(auth, '_get_session', return_value='mock_session'):
                verified_user = await auth.authenticate_token(access_token)
                assert verified_user is not None
                assert verified_user.user_id == user_context.user_id
                assert verified_user.email == user_context.email
    
    @pytest.mark.asyncio
    async def test_domain_validation_comprehensive(self, auth_config):
        """包括的ドメイン検証テスト"""
        with patch.dict('os.environ', {'JWT_SECRET_KEY': 'test_secret'}):
            auth = GoogleOAuth2Authentication(auth_config)
            
            # 有効ドメインテスト
            valid_cases = [
                ('user@university.ac.jp', ['university.ac.jp'], True),
                ('prof@test.edu', ['university.ac.jp', 'test.edu'], True),
                ('admin@University.AC.JP', ['university.ac.jp'], True),  # 大文字小文字
            ]
            
            for email, domains, expected in valid_cases:
                result = await auth.validate_domain(email, domains)
                assert result == expected, f"Failed for {email} with domains {domains}"
            
            # 無効ドメインテスト
            invalid_cases = [
                ('user@invalid.com', ['university.ac.jp'], False),
                ('test@gmail.com', ['university.ac.jp', 'test.edu'], False),
                ('', ['university.ac.jp'], False),  # 空文字
            ]
            
            for email, domains, expected in invalid_cases:
                result = await auth.validate_domain(email, domains)
                assert result == expected, f"Failed for {email} with domains {domains}"
            
            # 空ドメインリスト（全許可）
            result = await auth.validate_domain('any@domain.com', [])
            assert result is True
    
    @pytest.mark.asyncio
    async def test_user_management_comprehensive(self):
        """包括的ユーザー管理テスト"""
        user_mgmt = DatabaseUserManagement()
        
        # 複数ユーザー作成
        users = []
        for i in range(5):
            user = await user_mgmt.create_user(
                email=f'user{i}@university.ac.jp',
                display_name=f'User {i}',
                roles=[UserRole.STUDENT] if i < 3 else [UserRole.FACULTY],
                metadata={'index': i}
            )
            users.append(user)
        
        # 全ユーザー取得確認
        for user in users:
            retrieved = await user_mgmt.get_user(user.user_id)
            assert retrieved is not None
            assert retrieved.email == user.email
            assert retrieved.metadata['index'] == user.metadata['index']
        
        # 管理者作成
        admin = await user_mgmt.create_user(
            email='admin@university.ac.jp',
            display_name='Admin User',
            roles=[UserRole.ADMIN]
        )
        
        # 権限更新テスト
        for user in users[:2]:  # 最初の2人を教員に昇格
            success = await user_mgmt.update_user_roles(
                user_id=user.user_id,
                roles=[UserRole.FACULTY],
                updated_by=admin.user_id
            )
            assert success is True
            
            # 更新確認
            updated_user = await user_mgmt.get_user(user.user_id)
            assert 'faculty' in updated_user.roles
        
        # 検索テスト
        all_users = await user_mgmt.search_users('', limit=10)
        assert len(all_users) == 6  # 5 + admin
        
        student_users = await user_mgmt.search_users('', roles=[UserRole.STUDENT])
        faculty_users = await user_mgmt.search_users('', roles=[UserRole.FACULTY])
        
        # 役割更新後の数を確認
        assert len(student_users) >= 2  # 残りの学生
        assert len(faculty_users) >= 3  # 昇格した2人 + 元から教員1人
    
    @pytest.mark.asyncio
    async def test_authorization_matrix(self):
        """権限マトリクステスト"""
        authz = RoleBasedAuthorization()
        
        # 各役割のユーザーコンテキスト作成
        contexts = {
            'student': UserContext(
                user_id='student_123',
                email='student@university.ac.jp',
                display_name='Student User',
                domain='university.ac.jp',
                roles=['student'],
                permissions={'documents': ['read', 'write'], 'search': ['read']}
            ),
            'faculty': UserContext(
                user_id='faculty_123',
                email='faculty@university.ac.jp',
                display_name='Faculty User',
                domain='university.ac.jp',
                roles=['faculty'],
                permissions={
                    'documents': ['read', 'write', 'delete', 'share'],
                    'search': ['read'],
                    'users': ['read']
                }
            ),
            'admin': UserContext(
                user_id='admin_123',
                email='admin@university.ac.jp',
                display_name='Admin User',
                domain='university.ac.jp',
                roles=['admin'],
                permissions={
                    'documents': ['read', 'write', 'delete', 'admin'],
                    'users': ['read', 'write', 'delete', 'admin'],
                    'system': ['read', 'write', 'admin']
                }
            )
        }
        
        # 権限マトリクステスト
        test_cases = [
            # (role, resource, action, expected)
            ('student', 'documents', Permission.READ, True),
            ('student', 'documents', Permission.WRITE, True),
            ('student', 'documents', Permission.DELETE, False),
            ('student', 'users', Permission.READ, False),
            
            ('faculty', 'documents', Permission.READ, True),
            ('faculty', 'documents', Permission.WRITE, True),
            ('faculty', 'documents', Permission.DELETE, True),
            ('faculty', 'users', Permission.READ, True),
            ('faculty', 'users', Permission.DELETE, False),
            
            ('admin', 'documents', Permission.DELETE, True),
            ('admin', 'users', Permission.DELETE, True),
            ('admin', 'system', Permission.ADMIN, True),
            ('admin', 'any_resource', Permission.ADMIN, True),  # 管理者は全権限
        ]
        
        for role, resource, action, expected in test_cases:
            result = await authz.check_permission(
                contexts[role], resource, action
            )
            assert result == expected, f"Failed: {role} -> {resource}:{action.value} (expected {expected}, got {result})"
    
    @pytest.mark.asyncio
    async def test_registry_state_management(self):
        """レジストリ状態管理テスト"""
        registry = AuthPortRegistry()
        
        # 初期状態：認証無効
        assert registry._auth_enabled is False
        
        # 認証無効時の動作
        result = await registry.authenticate_request('any_token')
        assert result is None
        
        authorized = await registry.authorize_action(None, 'documents', Permission.WRITE)
        assert authorized is True  # 認証無効時は全許可
        
        # 認証有効化
        registry.enable_authentication(True)
        assert registry._auth_enabled is True
        
        # 認証有効だがポートなしの場合
        result = await registry.authenticate_request('any_token')
        assert result is None  # ポートがないのでNone
        
        authorized = await registry.authorize_action(None, 'documents', Permission.WRITE)
        assert authorized is False  # 認証有効でユーザーなしは拒否
    
    @pytest.mark.asyncio
    async def test_error_boundary_handling(self):
        """エラー境界ハンドリングテスト"""
        with patch.dict('os.environ', {'JWT_SECRET_KEY': 'test_secret'}):
            auth_config = AuthConfig(
                provider='google_oauth2',
                client_id='',  # 空のクライアントID
                client_secret='',
                redirect_uri='invalid_uri',
                allowed_domains=['university.ac.jp']
            )
            
            auth = GoogleOAuth2Authentication(auth_config)
            
            # 無効なトークンでの認証
            result = await auth.authenticate_token('completely_invalid_token')
            assert result is None
            
            # 空文字での認証
            result = await auth.authenticate_token('')
            assert result is None
            
            # Noneでの認証
            result = await auth.authenticate_token(None)
            assert result is None
    
    @pytest.mark.asyncio
    async def test_session_management_fallback(self):
        """セッション管理フォールバックテスト"""
        with patch.dict('os.environ', {'JWT_SECRET_KEY': 'test_secret'}):
            auth_config = AuthConfig(
                provider='google_oauth2',
                client_id='test_client_id',
                client_secret='test_client_secret',
                redirect_uri='http://localhost:8000/auth/callback',
                allowed_domains=['university.ac.jp']
            )
            
            # Redis接続失敗をシミュレート
            with patch('redis.from_url', side_effect=Exception("Redis connection failed")):
                auth = GoogleOAuth2Authentication(auth_config)
                
                # フォールバックでローカルストレージを使用
                assert isinstance(auth.session_manager, dict)
                
                # セッション操作テスト
                test_user = UserContext(
                    user_id='test_user',
                    email='test@university.ac.jp',
                    display_name='Test User',
                    domain='university.ac.jp',
                    roles=['student'],
                    permissions={'documents': ['read']},
                    session_id='test_session'
                )
                
                # セッション作成
                await auth._create_session(test_user)
                assert test_user.session_id in auth.session_manager
                
                # セッション取得
                session_data = await auth._get_session(test_user.session_id)
                assert session_data is not None
                
                # セッション削除
                await auth._remove_session(test_user.session_id)
                session_data = await auth._get_session(test_user.session_id)
                assert session_data is None


class TestIntegrationScenarios:
    """統合シナリオテスト"""
    
    @pytest.mark.asyncio
    async def test_complete_auth_flow(self):
        """完全な認証フローのテスト"""
        with patch.dict('os.environ', {'JWT_SECRET_KEY': 'test_secret'}):
            # 設定とシステム作成
            auth_config = AuthConfig(
                provider='google_oauth2',
                client_id='test_client_id',
                client_secret='test_client_secret',
                redirect_uri='http://localhost:8000/auth/callback',
                allowed_domains=['university.ac.jp']
            )
            
            registry = create_auth_system(auth_config)
            registry.enable_authentication(True)
            
            # 1. ユーザー作成
            user = await registry.user_mgmt_port.create_user(
                email='test@university.ac.jp',
                display_name='Test User',
                roles=[UserRole.STUDENT]
            )
            
            # 2. トークン生成
            access_token = await registry.auth_port._generate_access_token(user)
            
            # 3. セッション作成
            await registry.auth_port._create_session(user)
            
            # 4. 認証確認
            authenticated_user = await registry.authenticate_request(access_token)
            assert authenticated_user is not None
            assert authenticated_user.email == user.email
            
            # 5. 権限確認
            can_read = await registry.authorize_action(
                authenticated_user, 'documents', Permission.READ
            )
            assert can_read is True
            
            can_delete = await registry.authorize_action(
                authenticated_user, 'documents', Permission.DELETE
            )
            assert can_delete is False  # 学生は削除権限なし
            
            # 6. ログアウト
            logout_success = await registry.auth_port.logout(user.user_id, user.session_id)
            assert logout_success is True