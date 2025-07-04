"""
テスト用共通設定とフィクスチャ

認証システムテストで使用される共通設定、フィクスチャ、
モックオブジェクトを定義します。
"""

import pytest
import asyncio
import os
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta

# テスト対象モジュールのインポート
from agent.source.interfaces.data_models import AuthConfig, UserContext


@pytest.fixture(scope="session")
def event_loop():
    """イベントループフィクスチャ（セッションスコープ）"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
def test_auth_config():
    """テスト用認証設定"""
    return AuthConfig(
        provider='google_oauth2',
        client_id='test_client_id_12345',
        client_secret='test_client_secret_67890',
        redirect_uri='http://localhost:8000/auth/callback',
        allowed_domains=['university.ac.jp', 'test.edu', 'example.com'],
        session_timeout_minutes=480,
        require_email_verification=True
    )


@pytest.fixture
def test_user_contexts():
    """テスト用ユーザーコンテキスト集"""
    return {
        'student': UserContext(
            user_id='student_user_123',
            email='student@university.ac.jp',
            display_name='Test Student',
            domain='university.ac.jp',
            roles=['student'],
            permissions={
                'documents': ['read', 'write'],
                'search': ['read'],
                'users': [],
                'system': []
            },
            session_id='student_session_123',
            expires_at=datetime.now() + timedelta(hours=8),
            metadata={
                'department': 'Computer Science',
                'year': '3rd',
                'student_id': 'ST2021001'
            }
        ),
        'faculty': UserContext(
            user_id='faculty_user_456',
            email='prof.smith@university.ac.jp',
            display_name='Prof. John Smith',
            domain='university.ac.jp',
            roles=['faculty'],
            permissions={
                'documents': ['read', 'write', 'delete', 'share'],
                'search': ['read'],
                'users': ['read'],
                'system': ['read']
            },
            session_id='faculty_session_456',
            expires_at=datetime.now() + timedelta(hours=8),
            metadata={
                'department': 'Computer Science',
                'position': 'Associate Professor',
                'employee_id': 'EMP2019001'
            }
        ),
        'admin': UserContext(
            user_id='admin_user_789',
            email='admin@university.ac.jp',
            display_name='System Administrator',
            domain='university.ac.jp',
            roles=['admin'],
            permissions={
                'documents': ['read', 'write', 'delete', 'admin'],
                'search': ['read', 'admin'],
                'users': ['read', 'write', 'delete', 'admin'],
                'system': ['read', 'write', 'admin']
            },
            session_id='admin_session_789',
            expires_at=datetime.now() + timedelta(hours=8),
            metadata={
                'access_level': 'full',
                'employee_id': 'ADM2020001'
            }
        ),
        'guest': UserContext(
            user_id='guest_user_999',
            email='guest@example.com',
            display_name='Guest User',
            domain='example.com',
            roles=['guest'],
            permissions={
                'documents': ['read'],
                'search': ['read'],
                'users': [],
                'system': []
            },
            session_id='guest_session_999',
            expires_at=datetime.now() + timedelta(hours=1),
            metadata={
                'access_type': 'temporary'
            }
        )
    }


@pytest.fixture
def mock_google_userinfo():
    """モックGoogle UserInfo APIレスポンス"""
    return {
        'id': 'google_user_12345',
        'email': 'test@university.ac.jp',
        'verified_email': True,
        'name': 'Test User',
        'given_name': 'Test',
        'family_name': 'User',
        'picture': 'https://lh3.googleusercontent.com/a/default-user',
        'locale': 'en'
    }


@pytest.fixture
def mock_oauth_credentials():
    """モックOAuth2認証情報"""
    mock_creds = Mock()
    mock_creds.token = 'mock_access_token_12345'
    mock_creds.refresh_token = 'mock_refresh_token_67890'
    mock_creds.expiry = datetime.now() + timedelta(hours=1)
    mock_creds.valid = True
    return mock_creds


@pytest.fixture
def mock_session_data():
    """モックセッションデータ"""
    return {
        'user_id': 'test_user_123',
        'email': 'test@university.ac.jp',
        'display_name': 'Test User',
        'domain': 'university.ac.jp',
        'roles': ['student'],
        'permissions': {
            'documents': ['read', 'write'],
            'search': ['read']
        },
        'created_at': datetime.now().isoformat(),
        'expires_at': (datetime.now() + timedelta(hours=8)).isoformat(),
        'metadata': {
            'last_login': datetime.now().isoformat(),
            'login_count': 5
        }
    }


@pytest.fixture
def mock_jwt_secret():
    """モックJWT秘密鍵"""
    return 'test_jwt_secret_key_for_testing_only_do_not_use_in_production'


@pytest.fixture(autouse=True)
def setup_test_environment(mock_jwt_secret):
    """テスト環境設定（自動実行）"""
    # 環境変数設定
    original_env = os.environ.copy()
    os.environ.update({
        'JWT_SECRET_KEY': mock_jwt_secret,
        'AUTH_ENABLED': 'true',
        'GOOGLE_OAUTH_CLIENT_ID': 'test_client_id',
        'GOOGLE_OAUTH_CLIENT_SECRET': 'test_client_secret',
        'ALLOWED_DOMAINS': 'university.ac.jp,test.edu',
        'ENVIRONMENT': 'testing'
    })
    
    yield
    
    # 環境変数復元
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_redis_session_manager():
    """モックRedisセッション管理"""
    mock_redis = Mock()
    mock_redis.get = AsyncMock()
    mock_redis.set = AsyncMock()
    mock_redis.setex = AsyncMock()
    mock_redis.delete = AsyncMock()
    mock_redis.keys = AsyncMock()
    return mock_redis


@pytest.fixture
def mock_local_session_manager():
    """モックローカルセッション管理"""
    return {}


@pytest.fixture
def mock_google_oauth_flow():
    """モックGoogle OAuthフロー"""
    mock_flow = Mock()
    mock_flow.authorization_url.return_value = (
        'https://accounts.google.com/o/oauth2/auth?client_id=test&state=test_state',
        'test_state'
    )
    mock_flow.fetch_token = Mock()
    mock_flow.credentials = Mock()
    return mock_flow


@pytest.fixture
def invalid_domain_user_info():
    """無効ドメインのユーザー情報"""
    return {
        'id': 'invalid_user_123',
        'email': 'user@invalid-domain.com',
        'verified_email': True,
        'name': 'Invalid Domain User',
        'picture': 'https://example.com/avatar.jpg'
    }


@pytest.fixture
def expired_token_payload():
    """期限切れトークンペイロード"""
    return {
        'user_id': 'test_user_123',
        'email': 'test@university.ac.jp',
        'roles': ['student'],
        'iat': int((datetime.now() - timedelta(hours=2)).timestamp()),
        'exp': int((datetime.now() - timedelta(hours=1)).timestamp())  # 1時間前に期限切れ
    }


@pytest.fixture
def test_permission_matrix():
    """テスト用権限マトリクス"""
    return {
        'student': {
            'documents': ['read', 'write'],
            'search': ['read'],
            'users': [],
            'system': []
        },
        'faculty': {
            'documents': ['read', 'write', 'delete', 'share'],
            'search': ['read'],
            'users': ['read'],
            'system': ['read']
        },
        'admin': {
            'documents': ['read', 'write', 'delete', 'admin'],
            'search': ['read', 'admin'],
            'users': ['read', 'write', 'delete', 'admin'],
            'system': ['read', 'write', 'admin']
        },
        'guest': {
            'documents': ['read'],
            'search': ['read'],
            'users': [],
            'system': []
        }
    }


# テスト用ヘルパー関数

def create_mock_request_with_auth(user_context=None, authenticated=False):
    """認証情報付きモックリクエスト作成"""
    mock_request = Mock()
    mock_request.state = Mock()
    mock_request.state.user_context = user_context
    mock_request.state.authenticated = authenticated
    mock_request.headers = {}
    mock_request.cookies = {}
    mock_request.query_params = {}
    return mock_request


def create_mock_fastapi_response():
    """モックFastAPIレスポンス作成"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.cookies = {}
    mock_response.set_cookie = Mock()
    mock_response.delete_cookie = Mock()
    return mock_response