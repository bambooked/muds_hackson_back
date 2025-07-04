"""
認証システム実装のモジュールテスト

このテストスイートは、instanceCで実装した認証システムの各コンポーネントを
包括的にテストします。モックを使用して外部依存関係を排除し、
単体テストとして実行可能な設計になっています。

テスト対象:
- GoogleOAuth2Authentication
- DatabaseUserManagement  
- RoleBasedAuthorization
- JWT トークン管理
- セッション管理
"""

import pytest
import asyncio
import json
import secrets
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from typing import Dict, Any

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


class TestGoogleOAuth2Authentication:
    """Google OAuth2認証システムのテスト"""
    
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
    
    @pytest.fixture
    def oauth_auth(self, auth_config):
        """テスト用OAuth認証インスタンス"""
        with patch.dict('os.environ', {'JWT_SECRET_KEY': 'test_secret'}):
            return GoogleOAuth2Authentication(auth_config)
    
    @pytest.mark.asyncio
    async def test_initiate_google_oauth(self, oauth_auth):
        """OAuth2認証開始のテスト"""
        with patch('google_auth_oauthlib.flow.Flow.from_client_config') as mock_flow_class:
            mock_flow = Mock()
            mock_flow.authorization_url.return_value = (
                'https://accounts.google.com/oauth2/auth?client_id=test', 
                'test_state'
            )
            mock_flow_class.return_value = mock_flow
            
            # テスト実行
            result = await oauth_auth.initiate_google_oauth(
                redirect_uri='http://localhost:8000/auth/callback',
                state='custom_state'
            )
            
            # 検証
            assert 'auth_url' in result
            assert 'state' in result
            assert result['auth_url'].startswith('https://accounts.google.com')
            mock_flow.authorization_url.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_complete_google_oauth_success(self, oauth_auth):
        """OAuth2認証完了（成功）のテスト"""
        # モック設定
        mock_user_info = {
            'id': 'test_user_123',
            'email': 'test@university.ac.jp',
            'name': 'Test User',
            'verified_email': True,
            'picture': 'https://example.com/avatar.jpg'
        }
        
        with patch('google_auth_oauthlib.flow.Flow.from_client_config') as mock_flow_class, \
             patch.object(oauth_auth, '_get_oauth_state', return_value={'web': {'client_id': 'test'}}), \
             patch.object(oauth_auth, '_get_user_info', return_value=mock_user_info), \
             patch.object(oauth_auth, '_create_session'), \
             patch.object(oauth_auth, '_remove_oauth_state'):
            
            mock_flow = Mock()
            mock_credentials = Mock()
            mock_credentials.token = 'test_access_token'
            mock_credentials.refresh_token = 'test_refresh_token'
            mock_credentials.expiry = datetime.now() + timedelta(hours=1)
            mock_flow.credentials = mock_credentials
            mock_flow_class.return_value = mock_flow
            
            # テスト実行
            result = await oauth_auth.complete_google_oauth(
                authorization_code='test_code',
                state='test_state',
                redirect_uri='http://localhost:8000/auth/callback'
            )
            
            # 検証
            assert isinstance(result, UserContext)
            assert result.email == 'test@university.ac.jp'
            assert result.display_name == 'Test User'
            assert result.domain == 'university.ac.jp'
            assert 'student' in result.roles
    
    @pytest.mark.asyncio
    async def test_complete_google_oauth_invalid_domain(self, oauth_auth):
        """OAuth2認証完了（無効ドメイン）のテスト"""
        mock_user_info = {
            'id': 'test_user_123',
            'email': 'test@invalid.com',
            'name': 'Test User'
        }
        
        with patch('google_auth_oauthlib.flow.Flow.from_client_config') as mock_flow_class, \
             patch.object(oauth_auth, '_get_oauth_state', return_value={'web': {'client_id': 'test'}}), \
             patch.object(oauth_auth, '_get_user_info', return_value=mock_user_info):
            
            mock_flow = Mock()
            mock_flow_class.return_value = mock_flow
            
            # テスト実行・検証
            with pytest.raises(AuthError, match="Domain not allowed"):
                await oauth_auth.complete_google_oauth(
                    authorization_code='test_code',
                    state='test_state',
                    redirect_uri='http://localhost:8000/auth/callback'
                )
    
    @pytest.mark.asyncio
    async def test_authenticate_token_valid(self, oauth_auth):
        """有効JWTトークン認証のテスト"""
        # テスト用ユーザーコンテキスト作成
        user_context = UserContext(
            user_id='test_user_123',
            email='test@university.ac.jp',
            display_name='Test User',
            domain='university.ac.jp',
            roles=['student'],
            permissions={'documents': ['read', 'write']},
            session_id='test_session'
        )
        
        # JWTトークン生成
        access_token = await oauth_auth._generate_access_token(user_context)
        
        with patch.object(oauth_auth, '_get_session', return_value='{"user_id": "test_user_123"}'):
            # テスト実行
            result = await oauth_auth.authenticate_token(access_token)
            
            # 検証
            assert result is not None
            assert result.user_id == 'test_user_123'
            assert result.email == 'test@university.ac.jp'
    
    @pytest.mark.asyncio
    async def test_authenticate_token_invalid(self, oauth_auth):
        """無効JWTトークン認証のテスト"""
        # テスト実行
        result = await oauth_auth.authenticate_token('invalid_token')
        
        # 検証
        assert result is None
    
    @pytest.mark.asyncio
    async def test_validate_domain(self, oauth_auth):
        """ドメイン検証のテスト"""
        # 有効ドメイン
        valid_result = await oauth_auth.validate_domain(
            'test@university.ac.jp',
            ['university.ac.jp', 'test.edu']
        )
        assert valid_result is True
        
        # 無効ドメイン
        invalid_result = await oauth_auth.validate_domain(
            'test@invalid.com',
            ['university.ac.jp', 'test.edu']
        )
        assert invalid_result is False
        
        # 空のドメインリスト（全許可）
        empty_domains_result = await oauth_auth.validate_domain(
            'test@anything.com',
            []
        )
        assert empty_domains_result is True
    
    @pytest.mark.asyncio
    async def test_refresh_token(self, oauth_auth):
        """リフレッシュトークンのテスト"""
        user_context = UserContext(
            user_id='test_user_123',
            email='test@university.ac.jp',
            display_name='Test User',
            domain='university.ac.jp',
            roles=['student'],
            permissions={'documents': ['read']},
            session_id='test_session'
        )
        
        # リフレッシュトークン生成
        refresh_token = await oauth_auth._generate_refresh_token(user_context)
        
        with patch.object(oauth_auth, '_get_session', return_value=json.dumps({
            'user_id': user_context.user_id,
            'email': user_context.email,
            'display_name': user_context.display_name,
            'domain': user_context.domain,
            'roles': user_context.roles,
            'permissions': user_context.permissions,
            'metadata': {}
        })):
            # テスト実行
            result = await oauth_auth.refresh_token(refresh_token)
            
            # 検証
            assert result is not None
            assert 'access_token' in result
            assert 'refresh_token' in result
            assert result['token_type'] == 'bearer'
    
    @pytest.mark.asyncio
    async def test_logout(self, oauth_auth):
        """ログアウトのテスト"""
        with patch.object(oauth_auth, '_remove_session') as mock_remove_session:
            # セッション指定ログアウト
            result = await oauth_auth.logout('test_user', 'test_session')
            assert result is True
            mock_remove_session.assert_called_once_with('test_session')
        
        with patch.object(oauth_auth, '_remove_all_user_sessions') as mock_remove_all:
            # 全セッションログアウト
            result = await oauth_auth.logout('test_user')
            assert result is True
            mock_remove_all.assert_called_once_with('test_user')


class TestDatabaseUserManagement:
    """ユーザー管理システムのテスト"""
    
    @pytest.fixture
    def user_mgmt(self):
        """テスト用ユーザー管理インスタンス"""
        return DatabaseUserManagement()
    
    @pytest.mark.asyncio
    async def test_create_user(self, user_mgmt):
        """ユーザー作成のテスト"""
        # テスト実行
        user_context = await user_mgmt.create_user(
            email='test@university.ac.jp',
            display_name='Test User',
            roles=[UserRole.STUDENT],
            metadata={'department': 'Computer Science'}
        )
        
        # 検証
        assert user_context.email == 'test@university.ac.jp'
        assert user_context.display_name == 'Test User'
        assert user_context.domain == 'university.ac.jp'
        assert 'student' in user_context.roles
        assert user_context.metadata['department'] == 'Computer Science'
    
    @pytest.mark.asyncio
    async def test_create_user_duplicate(self, user_mgmt):
        """重複ユーザー作成のテスト"""
        # 初回作成
        await user_mgmt.create_user(
            email='duplicate@university.ac.jp',
            display_name='First User'
        )
        
        # 重複作成試行
        with pytest.raises(AuthError, match="User already exists"):
            await user_mgmt.create_user(
                email='duplicate@university.ac.jp',
                display_name='Second User'
            )
    
    @pytest.mark.asyncio
    async def test_get_user(self, user_mgmt):
        """ユーザー取得のテスト"""
        # ユーザー作成
        created_user = await user_mgmt.create_user(
            email='gettest@university.ac.jp',
            display_name='Get Test User'
        )
        
        # ユーザー取得
        retrieved_user = await user_mgmt.get_user(created_user.user_id)
        
        # 検証
        assert retrieved_user is not None
        assert retrieved_user.user_id == created_user.user_id
        assert retrieved_user.email == created_user.email
        
        # 存在しないユーザー
        nonexistent_user = await user_mgmt.get_user('nonexistent_id')
        assert nonexistent_user is None
    
    @pytest.mark.asyncio
    async def test_update_user_roles(self, user_mgmt):
        """ユーザー役割更新のテスト"""
        # ユーザーと管理者作成
        user = await user_mgmt.create_user(
            email='roletest@university.ac.jp',
            display_name='Role Test User',
            roles=[UserRole.STUDENT]
        )
        
        admin = await user_mgmt.create_user(
            email='admin@university.ac.jp',
            display_name='Admin User',
            roles=[UserRole.ADMIN]
        )
        
        # 役割更新
        success = await user_mgmt.update_user_roles(
            user_id=user.user_id,
            roles=[UserRole.FACULTY],
            updated_by=admin.user_id
        )
        
        # 検証
        assert success is True
        
        # 更新後のユーザー確認
        updated_user = await user_mgmt.get_user(user.user_id)
        assert 'faculty' in updated_user.roles
    
    @pytest.mark.asyncio
    async def test_update_user_roles_insufficient_permission(self, user_mgmt):
        """権限不足での役割更新のテスト"""
        # 一般ユーザー2人作成
        user1 = await user_mgmt.create_user(
            email='user1@university.ac.jp',
            display_name='User 1',
            roles=[UserRole.STUDENT]
        )
        
        user2 = await user_mgmt.create_user(
            email='user2@university.ac.jp',
            display_name='User 2',
            roles=[UserRole.STUDENT]
        )
        
        # 権限なしでの役割更新試行
        with pytest.raises(AuthError, match="Insufficient permissions"):
            await user_mgmt.update_user_roles(
                user_id=user2.user_id,
                roles=[UserRole.FACULTY],
                updated_by=user1.user_id
            )
    
    @pytest.mark.asyncio
    async def test_search_users(self, user_mgmt):
        """ユーザー検索のテスト"""
        # テストユーザー作成
        await user_mgmt.create_user(
            email='alice@university.ac.jp',
            display_name='Alice Smith',
            roles=[UserRole.STUDENT]
        )
        
        await user_mgmt.create_user(
            email='bob@university.ac.jp',
            display_name='Bob Jones',
            roles=[UserRole.FACULTY]
        )
        
        # 名前検索
        results = await user_mgmt.search_users('Alice')
        assert len(results) == 1
        assert results[0].display_name == 'Alice Smith'
        
        # メール検索
        results = await user_mgmt.search_users('bob@university')
        assert len(results) == 1
        assert results[0].email == 'bob@university.ac.jp'
        
        # 役割フィルタ
        results = await user_mgmt.search_users('', roles=[UserRole.FACULTY])
        faculty_users = [r for r in results if 'faculty' in r.roles]
        assert len(faculty_users) >= 1


class TestRoleBasedAuthorization:
    """役割ベース認可システムのテスト"""
    
    @pytest.fixture
    def authz(self):
        """テスト用認可インスタンス"""
        return RoleBasedAuthorization()
    
    @pytest.fixture
    def student_context(self):
        """テスト用学生ユーザーコンテキスト"""
        return UserContext(
            user_id='student_123',
            email='student@university.ac.jp',
            display_name='Student User',
            domain='university.ac.jp',
            roles=['student'],
            permissions={
                'documents': ['read', 'write'],
                'search': ['read']
            }
        )
    
    @pytest.fixture
    def faculty_context(self):
        """テスト用教員ユーザーコンテキスト"""
        return UserContext(
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
        )
    
    @pytest.fixture
    def admin_context(self):
        """テスト用管理者ユーザーコンテキスト"""
        return UserContext(
            user_id='admin_123',
            email='admin@university.ac.jp',
            display_name='Admin User',
            domain='university.ac.jp',
            roles=['admin'],
            permissions={
                'documents': ['read', 'write', 'delete', 'admin'],
                'search': ['read', 'admin'],
                'users': ['read', 'write', 'delete', 'admin'],
                'system': ['read', 'write', 'admin']
            }
        )
    
    @pytest.mark.asyncio
    async def test_check_permission_student(self, authz, student_context):
        """学生権限チェックのテスト"""
        # 許可される操作
        assert await authz.check_permission(student_context, 'documents', Permission.READ) is True
        assert await authz.check_permission(student_context, 'documents', Permission.WRITE) is True
        assert await authz.check_permission(student_context, 'search', Permission.READ) is True
        
        # 拒否される操作
        assert await authz.check_permission(student_context, 'documents', Permission.DELETE) is False
        assert await authz.check_permission(student_context, 'users', Permission.READ) is False
        assert await authz.check_permission(student_context, 'system', Permission.READ) is False
    
    @pytest.mark.asyncio
    async def test_check_permission_faculty(self, authz, faculty_context):
        """教員権限チェックのテスト"""
        # 許可される操作
        assert await authz.check_permission(faculty_context, 'documents', Permission.READ) is True
        assert await authz.check_permission(faculty_context, 'documents', Permission.WRITE) is True
        assert await authz.check_permission(faculty_context, 'documents', Permission.DELETE) is True
        assert await authz.check_permission(faculty_context, 'documents', Permission.SHARE) is True
        assert await authz.check_permission(faculty_context, 'users', Permission.READ) is True
        
        # 拒否される操作
        assert await authz.check_permission(faculty_context, 'users', Permission.DELETE) is False
        assert await authz.check_permission(faculty_context, 'system', Permission.ADMIN) is False
    
    @pytest.mark.asyncio
    async def test_check_permission_admin(self, authz, admin_context):
        """管理者権限チェックのテスト"""
        # 管理者は全ての操作が許可される
        assert await authz.check_permission(admin_context, 'documents', Permission.DELETE) is True
        assert await authz.check_permission(admin_context, 'users', Permission.DELETE) is True
        assert await authz.check_permission(admin_context, 'system', Permission.ADMIN) is True
        assert await authz.check_permission(admin_context, 'any_resource', Permission.ADMIN) is True
    
    @pytest.mark.asyncio
    async def test_get_user_permissions(self, authz, student_context, admin_context):
        """ユーザー権限一覧取得のテスト"""
        # 学生権限
        student_perms = await authz.get_user_permissions(student_context)
        assert 'documents' in student_perms
        assert Permission.READ in student_perms['documents']
        assert Permission.WRITE in student_perms['documents']
        assert Permission.DELETE not in student_perms.get('documents', [])
        
        # 管理者権限
        admin_perms = await authz.get_user_permissions(admin_context)
        assert 'documents' in admin_perms
        assert 'users' in admin_perms
        assert 'system' in admin_perms
        assert Permission.ADMIN in admin_perms['documents']
    
    @pytest.mark.asyncio
    async def test_check_resource_ownership(self, authz, faculty_context, student_context):
        """リソース所有権チェックのテスト"""
        # 教員は所有権あり
        assert await authz.check_resource_ownership(
            faculty_context, 'document', 'doc_123'
        ) is True
        
        # 学生は所有権なし（簡易実装）
        assert await authz.check_resource_ownership(
            student_context, 'document', 'doc_123'
        ) is False
    
    @pytest.mark.asyncio
    async def test_grant_permission(self, authz, admin_context, faculty_context):
        """権限付与のテスト"""
        # 管理者による権限付与（成功）
        result = await authz.grant_permission(
            grantor=admin_context,
            grantee_id='user_123',
            resource='documents',
            permissions=[Permission.READ, Permission.WRITE]
        )
        assert result is True
        
        # 教員による権限付与（成功）
        result = await authz.grant_permission(
            grantor=faculty_context,
            grantee_id='user_123',
            resource='documents',
            permissions=[Permission.READ]
        )
        assert result is True


class TestAuthPortRegistry:
    """認証ポートレジストリのテスト"""
    
    @pytest.fixture
    def auth_config(self):
        """テスト用認証設定"""
        return AuthConfig(
            provider='google_oauth2',
            client_id='test_client_id',
            client_secret='test_client_secret',
            redirect_uri='http://localhost:8000/auth/callback',
            allowed_domains=['university.ac.jp']
        )
    
    @pytest.mark.asyncio
    async def test_create_auth_system(self, auth_config):
        """認証システム作成のテスト"""
        with patch.dict('os.environ', {'JWT_SECRET_KEY': 'test_secret'}):
            registry = create_auth_system(auth_config)
            
            # 検証
            assert registry.auth_port is not None
            assert registry.user_mgmt_port is not None
            assert registry.authz_port is not None
            assert isinstance(registry.auth_port, GoogleOAuth2Authentication)
            assert isinstance(registry.user_mgmt_port, DatabaseUserManagement)
            assert isinstance(registry.authz_port, RoleBasedAuthorization)
    
    @pytest.mark.asyncio
    async def test_registry_authentication_disabled(self):
        """認証無効時のレジストリ動作テスト"""
        registry = AuthPortRegistry()
        registry.enable_authentication(False)
        
        # 認証無効時は None を返す
        result = await registry.authenticate_request('any_token')
        assert result is None
        
        # 認証無効時は True を返す（全許可）
        authorized = await registry.authorize_action(
            None, 'documents', Permission.WRITE
        )
        assert authorized is True
    
    @pytest.mark.asyncio
    async def test_registry_authentication_enabled(self, auth_config):
        """認証有効時のレジストリ動作テスト"""
        with patch.dict('os.environ', {'JWT_SECRET_KEY': 'test_secret'}):
            registry = create_auth_system(auth_config)
            registry.enable_authentication(True)
            
            # 無効トークンでの認証試行
            result = await registry.authenticate_request('invalid_token')
            assert result is None
            
            # 認証済みユーザーなしでの認可試行
            authorized = await registry.authorize_action(
                None, 'documents', Permission.WRITE
            )
            assert authorized is False


class TestErrorHandling:
    """エラーハンドリングのテスト"""
    
    @pytest.mark.asyncio
    async def test_auth_error_propagation(self):
        """認証エラーの伝播テスト"""
        config = AuthConfig(
            provider='google_oauth2',
            client_id='',  # 空のクライアントID
            client_secret='',
            redirect_uri='invalid_uri',
            allowed_domains=[]
        )
        
        with patch.dict('os.environ', {'JWT_SECRET_KEY': 'test_secret'}):
            auth = GoogleOAuth2Authentication(config)
            
            # 無効な設定でのOAuth開始試行
            with pytest.raises(AuthError):
                await auth.initiate_google_oauth('invalid_redirect')
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Graceful Degradationのテスト"""
        # Redis接続失敗をシミュレート
        with patch('redis.from_url', side_effect=Exception("Redis connection failed")):
            config = AuthConfig(
                provider='google_oauth2',
                client_id='test_client_id',
                client_secret='test_client_secret',
                redirect_uri='http://localhost:8000/auth/callback',
                allowed_domains=['university.ac.jp']
            )
            
            with patch.dict('os.environ', {'JWT_SECRET_KEY': 'test_secret'}):
                # Redisが利用できなくてもローカルストレージにフォールバック
                auth = GoogleOAuth2Authentication(config)
                assert isinstance(auth.session_manager, dict)  # ローカルストレージ