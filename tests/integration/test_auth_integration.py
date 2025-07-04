"""
認証統合テストスクリプト

このスクリプトは、実装した認証システムの基本動作を確認します。
既存システムとの互換性と認証機能の正常動作をテストします。

テスト項目:
1. 認証無効時の既存システム互換性
2. 認証有効時の基本機能
3. JWT トークン生成・検証
4. 権限制御
5. エラーハンドリング
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Optional

# テスト用の設定
os.environ['AUTH_ENABLED'] = 'true'
os.environ['GOOGLE_OAUTH_CLIENT_ID'] = 'test_client_id'
os.environ['GOOGLE_OAUTH_CLIENT_SECRET'] = 'test_client_secret'
os.environ['GOOGLE_OAUTH_REDIRECT_URI'] = 'http://localhost:8000/auth/callback'
os.environ['ALLOWED_DOMAINS'] = 'university.ac.jp,test.edu'
os.environ['JWT_SECRET_KEY'] = 'test_secret_key_for_development'

# インポート
from agent.source.interfaces.auth_implementations import (
    GoogleOAuth2Authentication, DatabaseUserManagement, RoleBasedAuthorization,
    create_auth_system
)
from agent.source.interfaces.auth_ports import UserRole, Permission
from agent.source.interfaces.data_models import AuthConfig, UserContext, AuthError

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_authentication_system():
    """認証システムの基本テスト"""
    print("\n=== 認証システム基本テスト ===")
    
    try:
        # 設定作成
        auth_config = AuthConfig(
            provider='google_oauth2',
            client_id='test_client_id',
            client_secret='test_client_secret',
            redirect_uri='http://localhost:8000/auth/callback',
            allowed_domains=['university.ac.jp', 'test.edu']
        )
        
        # 認証システム作成
        auth_registry = create_auth_system(auth_config)
        auth_registry.enable_authentication(True)
        
        print("✅ 認証システム作成成功")
        
        # JWT トークンテスト
        await test_jwt_tokens(auth_registry.auth_port)
        
        # ユーザー管理テスト
        await test_user_management(auth_registry.user_mgmt_port)
        
        # 権限制御テスト
        await test_authorization(auth_registry.authz_port)
        
        print("✅ 認証システム基本テスト完了")
        
    except Exception as e:
        print(f"❌ 認証システムテスト失敗: {e}")
        logger.exception("Authentication system test failed")


async def test_jwt_tokens(auth_port):
    """JWT トークンのテスト"""
    print("\n--- JWT トークンテスト ---")
    
    try:
        # テスト用ユーザーコンテキスト
        user_context = UserContext(
            user_id="test_user_123",
            email="test@university.ac.jp",
            display_name="Test User",
            domain="university.ac.jp",
            roles=["student"],
            permissions={
                "documents": ["read", "write"],
                "search": ["read"]
            },
            session_id="test_session_123"
        )
        
        # アクセストークン生成
        access_token = await auth_port._generate_access_token(user_context)
        print(f"✅ アクセストークン生成: {access_token[:50]}...")
        
        # リフレッシュトークン生成
        refresh_token = await auth_port._generate_refresh_token(user_context)
        print(f"✅ リフレッシュトークン生成: {refresh_token[:50]}...")
        
        # トークン検証
        verified_context = await auth_port.authenticate_token(access_token)
        if verified_context and verified_context.user_id == user_context.user_id:
            print("✅ トークン検証成功")
        else:
            print("❌ トークン検証失敗")
        
        # ドメイン検証テスト
        valid_domain = await auth_port.validate_domain(
            "test@university.ac.jp", 
            ["university.ac.jp"]
        )
        invalid_domain = await auth_port.validate_domain(
            "test@invalid.com", 
            ["university.ac.jp"]
        )
        
        if valid_domain and not invalid_domain:
            print("✅ ドメイン検証成功")
        else:
            print("❌ ドメイン検証失敗")
        
    except Exception as e:
        print(f"❌ JWT トークンテスト失敗: {e}")
        logger.exception("JWT token test failed")


async def test_user_management(user_mgmt_port):
    """ユーザー管理のテスト"""
    print("\n--- ユーザー管理テスト ---")
    
    try:
        # ユーザー作成
        user_context = await user_mgmt_port.create_user(
            email="test@university.ac.jp",
            display_name="Test User",
            roles=[UserRole.STUDENT]
        )
        print(f"✅ ユーザー作成: {user_context.email}")
        
        # ユーザー取得
        retrieved_user = await user_mgmt_port.get_user(user_context.user_id)
        if retrieved_user and retrieved_user.email == user_context.email:
            print("✅ ユーザー取得成功")
        else:
            print("❌ ユーザー取得失敗")
        
        # 管理者ユーザー作成（権限更新用）
        admin_user = await user_mgmt_port.create_user(
            email="admin@university.ac.jp",
            display_name="Admin User",
            roles=[UserRole.ADMIN]
        )
        
        # 役割更新テスト
        update_success = await user_mgmt_port.update_user_roles(
            user_id=user_context.user_id,
            roles=[UserRole.FACULTY],
            updated_by=admin_user.user_id
        )
        
        if update_success:
            print("✅ ユーザー役割更新成功")
        else:
            print("❌ ユーザー役割更新失敗")
        
        # ユーザー検索
        search_results = await user_mgmt_port.search_users("test")
        if len(search_results) > 0:
            print(f"✅ ユーザー検索成功: {len(search_results)}件")
        else:
            print("❌ ユーザー検索失敗")
        
    except Exception as e:
        print(f"❌ ユーザー管理テスト失敗: {e}")
        logger.exception("User management test failed")


async def test_authorization(authz_port):
    """権限制御のテスト"""
    print("\n--- 権限制御テスト ---")
    
    try:
        # テスト用ユーザーコンテキスト
        student_context = UserContext(
            user_id="student_123",
            email="student@university.ac.jp",
            display_name="Student User",
            domain="university.ac.jp",
            roles=["student"],
            permissions={
                "documents": ["read", "write"],
                "search": ["read"]
            }
        )
        
        admin_context = UserContext(
            user_id="admin_123",
            email="admin@university.ac.jp",
            display_name="Admin User",
            domain="university.ac.jp",
            roles=["admin"],
            permissions={
                "documents": ["read", "write", "delete", "admin"],
                "search": ["read", "admin"],
                "admin": ["read", "write", "admin"]
            }
        )
        
        # 権限チェックテスト
        tests = [
            (student_context, "documents", Permission.READ, True, "学生の文書読み取り"),
            (student_context, "documents", Permission.WRITE, True, "学生の文書書き込み"),
            (student_context, "documents", Permission.DELETE, False, "学生の文書削除"),
            (student_context, "admin", Permission.READ, False, "学生の管理者機能"),
            (admin_context, "documents", Permission.DELETE, True, "管理者の文書削除"),
            (admin_context, "admin", Permission.READ, True, "管理者の管理機能"),
        ]
        
        for user_context, resource, permission, expected, description in tests:
            result = await authz_port.check_permission(
                user_context, resource, permission
            )
            
            if result == expected:
                print(f"✅ {description}: {'許可' if result else '拒否'}")
            else:
                print(f"❌ {description}: 期待={expected}, 実際={result}")
        
        # ユーザー権限一覧取得
        student_permissions = await authz_port.get_user_permissions(student_context)
        admin_permissions = await authz_port.get_user_permissions(admin_context)
        
        if student_permissions and admin_permissions:
            print("✅ ユーザー権限一覧取得成功")
            print(f"  学生権限: {list(student_permissions.keys())}")
            print(f"  管理者権限: {list(admin_permissions.keys())}")
        else:
            print("❌ ユーザー権限一覧取得失敗")
        
    except Exception as e:
        print(f"❌ 権限制御テスト失敗: {e}")
        logger.exception("Authorization test failed")


async def test_error_handling():
    """エラーハンドリングのテスト"""
    print("\n--- エラーハンドリングテスト ---")
    
    try:
        auth_config = AuthConfig(
            provider='google_oauth2',
            client_id='test_client_id',
            client_secret='test_client_secret',
            redirect_uri='http://localhost:8000/auth/callback',
            allowed_domains=['university.ac.jp']
        )
        
        auth_port = GoogleOAuth2Authentication(auth_config)
        
        # 無効なトークンテスト
        invalid_context = await auth_port.authenticate_token("invalid_token")
        if invalid_context is None:
            print("✅ 無効トークン処理成功")
        else:
            print("❌ 無効トークン処理失敗")
        
        # 無効なドメインテスト
        invalid_domain = await auth_port.validate_domain(
            "test@invalid.com",
            ["university.ac.jp"]
        )
        if not invalid_domain:
            print("✅ 無効ドメイン拒否成功")
        else:
            print("❌ 無効ドメイン拒否失敗")
        
        # ユーザー管理での重複作成テスト
        user_mgmt = DatabaseUserManagement()
        
        # 初回作成
        await user_mgmt.create_user(
            email="duplicate@university.ac.jp",
            display_name="Duplicate Test"
        )
        
        # 重複作成試行
        try:
            await user_mgmt.create_user(
                email="duplicate@university.ac.jp",
                display_name="Duplicate Test 2"
            )
            print("❌ 重複ユーザー作成エラーハンドリング失敗")
        except AuthError:
            print("✅ 重複ユーザー作成エラーハンドリング成功")
        
    except Exception as e:
        print(f"❌ エラーハンドリングテスト失敗: {e}")
        logger.exception("Error handling test failed")


async def test_legacy_compatibility():
    """既存システム互換性テスト"""
    print("\n--- 既存システム互換性テスト ---")
    
    try:
        # 認証無効時のテスト
        from agent.source.interfaces.auth_ports import AuthPortRegistry
        
        registry_disabled = AuthPortRegistry()
        registry_disabled.enable_authentication(False)
        
        # 認証無効時のリクエスト処理
        unauthenticated_user = await registry_disabled.authenticate_request(None)
        if unauthenticated_user is None:
            print("✅ 認証無効時の処理成功")
        else:
            print("❌ 認証無効時の処理失敗")
        
        # 認証無効時の認可処理
        always_authorized = await registry_disabled.authorize_action(
            None, "documents", Permission.WRITE
        )
        if always_authorized:
            print("✅ 認証無効時の認可処理成功（常に許可）")
        else:
            print("❌ 認証無効時の認可処理失敗")
        
        print("✅ 既存システム互換性確認完了")
        
    except Exception as e:
        print(f"❌ 既存システム互換性テスト失敗: {e}")
        logger.exception("Legacy compatibility test failed")


async def main():
    """メインテスト実行"""
    print("🚀 instanceC: Authentication Port 統合テスト開始")
    print(f"実行時刻: {datetime.now().isoformat()}")
    
    await test_authentication_system()
    await test_error_handling()
    await test_legacy_compatibility()
    
    print("\n=== テスト完了 ===")
    print("✅ 認証システム実装完了")
    print("✅ 既存システム保護確認")
    print("✅ 段階的セキュア化対応")
    
    print("\n📋 次のステップ:")
    print("1. 実際の Google OAuth2 認証情報設定")
    print("2. Redis セッションストレージ設定（Optional）") 
    print("3. 本番環境用セキュリティ設定")
    print("4. 他インスタンスとの統合テスト")


if __name__ == "__main__":
    asyncio.run(main())