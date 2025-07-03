"""
config_manager.pyモジュールの包括的テスト

このテストモジュールは、PaaSConfigManagerおよび設定管理機能の詳細なテストを提供します。
環境変数、設定ファイル、機能フラグの動作を包括的にテスト。

実行方法:
```bash
# 単体テスト実行
uv run pytest agent/tests/test_config_manager_module.py -v

# カバレッジ付き実行
uv run pytest agent/tests/test_config_manager_module.py --cov=agent.source.interfaces.config_manager --cov-report=html -v
```
"""

import os
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
from typing import Dict, Any

# テスト対象のインポート
from agent.source.interfaces.config_manager import (
    PaaSConfigManager,
    get_config_manager,
    init_config_manager,
    is_feature_enabled,
    get_feature_config,
    create_env_template
)
from agent.source.interfaces.data_models import (
    PaaSConfig,
    GoogleDriveConfig,
    VectorSearchConfig,
    AuthConfig
)


class TestPaaSConfigManagerInitialization:
    """PaaSConfigManager初期化テストクラス"""
    
    def test_initialization_without_config_file(self):
        """設定ファイルなしでの初期化テスト"""
        manager = PaaSConfigManager()
        
        assert manager.config_file_path is None
        assert manager._config is None
    
    def test_initialization_with_config_file(self):
        """設定ファイル指定での初期化テスト"""
        config_path = "/tmp/test_config.json"
        manager = PaaSConfigManager(config_path)
        
        assert manager.config_file_path == config_path
        assert manager._config is None


class TestPaaSConfigManagerEnvironmentVariables:
    """環境変数読み込みテストクラス"""
    
    def test_load_config_default_values(self):
        """デフォルト値での設定読み込みテスト"""
        # 環境変数をクリア
        env_vars_to_clear = [
            'PAAS_ENVIRONMENT', 'API_HOST', 'API_PORT', 'DEBUG',
            'ENABLE_GOOGLE_DRIVE', 'ENABLE_VECTOR_SEARCH', 
            'ENABLE_AUTHENTICATION', 'ENABLE_MONITORING'
        ]
        
        with patch.dict(os.environ, {}, clear=True):
            manager = PaaSConfigManager()
            config = manager.load_config()
            
            # デフォルト値確認
            assert config.environment == "development"
            assert config.api_host == "0.0.0.0"
            assert config.api_port == 8000
            assert config.debug is False
            assert config.enable_google_drive is False
            assert config.enable_vector_search is False
            assert config.enable_authentication is False
            assert config.enable_monitoring is False
    
    def test_load_config_with_environment_variables(self):
        """環境変数設定での設定読み込みテスト"""
        env_vars = {
            'PAAS_ENVIRONMENT': 'production',
            'API_HOST': '127.0.0.1',
            'API_PORT': '9000',
            'DEBUG': 'true',
            'ENABLE_GOOGLE_DRIVE': 'true',
            'ENABLE_VECTOR_SEARCH': 'false',
            'ENABLE_AUTHENTICATION': '1',
            'ENABLE_MONITORING': 'yes'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            manager = PaaSConfigManager()
            config = manager.load_config()
            
            # 環境変数値確認
            assert config.environment == "production"
            assert config.api_host == "127.0.0.1"
            assert config.api_port == 9000
            assert config.debug is True
            assert config.enable_google_drive is True
            assert config.enable_vector_search is False
            assert config.enable_authentication is True
            assert config.enable_monitoring is True
    
    def test_bool_env_parsing(self):
        """ブール値環境変数パースのテスト"""
        manager = PaaSConfigManager()
        
        # True パターン
        assert manager._get_bool_env('TEST_TRUE_1', False) is False  # デフォルト
        
        true_values = ['true', 'True', 'TRUE', '1', 'yes', 'YES', 'on', 'ON']
        for value in true_values:
            with patch.dict(os.environ, {'TEST_BOOL': value}):
                assert manager._get_bool_env('TEST_BOOL', False) is True, f"Failed for value: {value}"
        
        # False パターン
        false_values = ['false', 'False', 'FALSE', '0', 'no', 'NO', 'off', 'OFF', 'invalid']
        for value in false_values:
            with patch.dict(os.environ, {'TEST_BOOL': value}):
                assert manager._get_bool_env('TEST_BOOL', True) is False, f"Failed for value: {value}"
    
    def test_list_env_parsing(self):
        """リスト環境変数パースのテスト"""
        manager = PaaSConfigManager()
        
        # デフォルト値
        assert manager._get_list_env('NONEXISTENT', ['default']) == ['default']
        
        # カンマ区切りリスト
        with patch.dict(os.environ, {'TEST_LIST': 'item1,item2,item3'}):
            result = manager._get_list_env('TEST_LIST', [])
            assert result == ['item1', 'item2', 'item3']
        
        # スペース含みリスト
        with patch.dict(os.environ, {'TEST_LIST': 'item1, item2 , item3'}):
            result = manager._get_list_env('TEST_LIST', [])
            assert result == ['item1', 'item2', 'item3']  # スペーストリム


class TestPaaSConfigManagerGoogleDriveConfig:
    """Google Drive設定テストクラス"""
    
    def test_google_drive_config_disabled(self):
        """Google Drive無効時の設定テスト"""
        with patch.dict(os.environ, {'ENABLE_GOOGLE_DRIVE': 'false'}, clear=True):
            manager = PaaSConfigManager()
            config = manager.load_config()
            
            assert config.enable_google_drive is False
            assert config.google_drive is None
    
    def test_google_drive_config_enabled_default(self):
        """Google Drive有効・デフォルト設定テスト"""
        with patch.dict(os.environ, {'ENABLE_GOOGLE_DRIVE': 'true'}, clear=True):
            manager = PaaSConfigManager()
            config = manager.load_config()
            
            assert config.enable_google_drive is True
            assert config.google_drive is not None
            assert config.google_drive.credentials_path == ""
            assert config.google_drive.max_file_size_mb == 100
            assert config.google_drive.sync_interval_minutes == 60
            assert config.google_drive.batch_size == 10
            assert 'https://www.googleapis.com/auth/drive.readonly' in config.google_drive.scopes
    
    def test_google_drive_config_custom_settings(self):
        """Google Drive有効・カスタム設定テスト"""
        env_vars = {
            'ENABLE_GOOGLE_DRIVE': 'true',
            'GOOGLE_DRIVE_CREDENTIALS_PATH': '/custom/path/credentials.json',
            'GOOGLE_DRIVE_MAX_FILE_SIZE_MB': '200',
            'GOOGLE_DRIVE_SYNC_INTERVAL': '120',
            'GOOGLE_DRIVE_BATCH_SIZE': '20',
            'GOOGLE_DRIVE_SCOPES': 'scope1,scope2,scope3',
            'GOOGLE_DRIVE_SUPPORTED_TYPES': 'application/pdf,text/csv'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            manager = PaaSConfigManager()
            config = manager.load_config()
            
            gd_config = config.google_drive
            assert gd_config.credentials_path == '/custom/path/credentials.json'
            assert gd_config.max_file_size_mb == 200
            assert gd_config.sync_interval_minutes == 120
            assert gd_config.batch_size == 20
            assert gd_config.scopes == ['scope1', 'scope2', 'scope3']
            assert gd_config.supported_mime_types == ['application/pdf', 'text/csv']


class TestPaaSConfigManagerVectorSearchConfig:
    """Vector Search設定テストクラス"""
    
    def test_vector_search_config_disabled(self):
        """Vector Search無効時の設定テスト"""
        with patch.dict(os.environ, {'ENABLE_VECTOR_SEARCH': 'false'}, clear=True):
            manager = PaaSConfigManager()
            config = manager.load_config()
            
            assert config.enable_vector_search is False
            assert config.vector_search is None
    
    def test_vector_search_config_enabled_default(self):
        """Vector Search有効・デフォルト設定テスト"""
        with patch.dict(os.environ, {'ENABLE_VECTOR_SEARCH': 'true'}, clear=True):
            manager = PaaSConfigManager()
            config = manager.load_config()
            
            assert config.enable_vector_search is True
            assert config.vector_search is not None
            assert config.vector_search.provider == 'chroma'
            assert config.vector_search.host == 'localhost'
            assert config.vector_search.port == 8000
            assert config.vector_search.collection_name == 'research_documents'
            assert config.vector_search.similarity_threshold == 0.7
    
    def test_vector_search_config_custom_settings(self):
        """Vector Search有効・カスタム設定テスト"""
        env_vars = {
            'ENABLE_VECTOR_SEARCH': 'true',
            'VECTOR_SEARCH_PROVIDER': 'qdrant',
            'VECTOR_SEARCH_HOST': 'vector.example.com',
            'VECTOR_SEARCH_PORT': '6333',
            'VECTOR_SEARCH_COLLECTION': 'custom_collection',
            'EMBEDDING_MODEL': 'custom-embedding-model',
            'SIMILARITY_THRESHOLD': '0.8',
            'VECTOR_SEARCH_MAX_RESULTS': '100',
            'VECTOR_SEARCH_PERSIST_DIR': '/custom/persist'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            manager = PaaSConfigManager()
            config = manager.load_config()
            
            vs_config = config.vector_search
            assert vs_config.provider == 'qdrant'
            assert vs_config.host == 'vector.example.com'
            assert vs_config.port == 6333
            assert vs_config.collection_name == 'custom_collection'
            assert vs_config.embedding_model == 'custom-embedding-model'
            assert vs_config.similarity_threshold == 0.8
            assert vs_config.max_results == 100
            assert vs_config.persist_directory == '/custom/persist'


class TestPaaSConfigManagerAuthConfig:
    """認証設定テストクラス"""
    
    def test_auth_config_disabled(self):
        """認証無効時の設定テスト"""
        with patch.dict(os.environ, {'ENABLE_AUTHENTICATION': 'false'}, clear=True):
            manager = PaaSConfigManager()
            config = manager.load_config()
            
            assert config.enable_authentication is False
            assert config.auth is None
    
    def test_auth_config_enabled_default(self):
        """認証有効・デフォルト設定テスト"""
        with patch.dict(os.environ, {'ENABLE_AUTHENTICATION': 'true'}, clear=True):
            manager = PaaSConfigManager()
            config = manager.load_config()
            
            assert config.enable_authentication is True
            assert config.auth is not None
            assert config.auth.provider == 'google_oauth2'
            assert config.auth.session_timeout_minutes == 480
            assert config.auth.require_email_verification is True
    
    def test_auth_config_custom_settings(self):
        """認証有効・カスタム設定テスト"""
        env_vars = {
            'ENABLE_AUTHENTICATION': 'true',
            'AUTH_PROVIDER': 'saml',
            'OAUTH_CLIENT_ID': 'custom_client_id',
            'OAUTH_CLIENT_SECRET': 'custom_client_secret',
            'OAUTH_REDIRECT_URI': 'https://example.com/callback',
            'OAUTH_ALLOWED_DOMAINS': 'example.com,test.com',
            'SESSION_TIMEOUT_MINUTES': '240',
            'REQUIRE_EMAIL_VERIFICATION': 'false'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            manager = PaaSConfigManager()
            config = manager.load_config()
            
            auth_config = config.auth
            assert auth_config.provider == 'saml'
            assert auth_config.client_id == 'custom_client_id'
            assert auth_config.client_secret == 'custom_client_secret'
            assert auth_config.redirect_uri == 'https://example.com/callback'
            assert auth_config.allowed_domains == ['example.com', 'test.com']
            assert auth_config.session_timeout_minutes == 240
            assert auth_config.require_email_verification is False


class TestPaaSConfigManagerFileConfig:
    """設定ファイル読み込みテストクラス"""
    
    def test_load_config_file_success(self):
        """設定ファイル読み込み成功テスト"""
        config_data = {
            'enable_google_drive': True,
            'enable_vector_search': False,
            'enable_authentication': True
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(config_data, temp_file)
            temp_file.flush()
            
            try:
                manager = PaaSConfigManager(temp_file.name)
                
                with patch.dict(os.environ, {}, clear=True):
                    config = manager.load_config()
                    
                    # ファイル設定が環境変数設定をオーバーライド
                    assert config.enable_google_drive is True
                    assert config.enable_vector_search is False
                    assert config.enable_authentication is True
                    
            finally:
                Path(temp_file.name).unlink(missing_ok=True)
    
    def test_load_config_file_not_found(self):
        """設定ファイル不存在時のテスト"""
        manager = PaaSConfigManager("/nonexistent/config.json")
        
        with patch.dict(os.environ, {'ENABLE_GOOGLE_DRIVE': 'true'}, clear=True):
            config = manager.load_config()
            
            # 環境変数設定が使用される
            assert config.enable_google_drive is True
    
    def test_load_config_file_invalid_json(self):
        """無効JSON設定ファイルのテスト"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_file.write("invalid json content")
            temp_file.flush()
            
            try:
                manager = PaaSConfigManager(temp_file.name)
                
                with patch.dict(os.environ, {'ENABLE_GOOGLE_DRIVE': 'true'}, clear=True):
                    config = manager.load_config()
                    
                    # 環境変数設定が使用される（ファイル読み込み失敗）
                    assert config.enable_google_drive is True
                    
            finally:
                Path(temp_file.name).unlink(missing_ok=True)


class TestPaaSConfigManagerValidation:
    """設定検証テストクラス"""
    
    def test_validation_google_drive_missing_credentials(self):
        """Google Drive認証ファイル不存在時の警告テスト"""
        env_vars = {
            'ENABLE_GOOGLE_DRIVE': 'true',
            'GOOGLE_DRIVE_CREDENTIALS_PATH': '/nonexistent/credentials.json'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            manager = PaaSConfigManager()
            
            # ログキャプチャ
            with patch('agent.source.interfaces.config_manager.logging.warning') as mock_warning:
                config = manager.load_config()
                
                # 警告が出力されることを確認
                mock_warning.assert_called()
                warning_message = mock_warning.call_args[0][0]
                assert "認証ファイルが見つかりません" in warning_message
    
    def test_validation_vector_search_unsupported_provider(self):
        """Vector Search非サポートプロバイダーの警告テスト"""
        env_vars = {
            'ENABLE_VECTOR_SEARCH': 'true',
            'VECTOR_SEARCH_PROVIDER': 'unsupported_provider'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            manager = PaaSConfigManager()
            
            with patch('agent.source.interfaces.config_manager.logging.warning') as mock_warning:
                config = manager.load_config()
                
                mock_warning.assert_called()
                warning_message = mock_warning.call_args[0][0]
                assert "サポートされていないVector Searchプロバイダー" in warning_message
    
    def test_validation_auth_incomplete_oauth(self):
        """認証OAuth情報不完全時の警告テスト"""
        env_vars = {
            'ENABLE_AUTHENTICATION': 'true',
            'OAUTH_CLIENT_ID': 'client_id',
            # OAUTH_CLIENT_SECRET未設定
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            manager = PaaSConfigManager()
            
            with patch('agent.source.interfaces.config_manager.logging.warning') as mock_warning:
                config = manager.load_config()
                
                mock_warning.assert_called()
                warning_message = mock_warning.call_args[0][0]
                assert "OAuth認証情報が不完全" in warning_message


class TestPaaSConfigManagerPublicInterface:
    """パブリックインターフェースメソッドテストクラス"""
    
    def test_feature_check_methods(self):
        """機能有効チェックメソッドのテスト"""
        env_vars = {
            'ENABLE_GOOGLE_DRIVE': 'true',
            'ENABLE_VECTOR_SEARCH': 'false',
            'ENABLE_AUTHENTICATION': 'true'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            manager = PaaSConfigManager()
            
            assert manager.is_google_drive_enabled() is True
            assert manager.is_vector_search_enabled() is False
            assert manager.is_authentication_enabled() is True
    
    def test_get_config_methods(self):
        """設定取得メソッドのテスト"""
        env_vars = {
            'ENABLE_GOOGLE_DRIVE': 'true',
            'ENABLE_VECTOR_SEARCH': 'false',
            'GOOGLE_DRIVE_CREDENTIALS_PATH': '/test/credentials.json'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            manager = PaaSConfigManager()
            
            gd_config = manager.get_google_drive_config()
            assert gd_config is not None
            assert isinstance(gd_config, GoogleDriveConfig)
            assert gd_config.credentials_path == '/test/credentials.json'
            
            vs_config = manager.get_vector_search_config()
            assert vs_config is None  # 無効のため
            
            auth_config = manager.get_auth_config()
            assert auth_config is None  # 無効のため
    
    def test_save_config_to_file(self):
        """設定ファイル保存テスト"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_file_path = temp_file.name
        
        try:
            with patch.dict(os.environ, {'ENABLE_GOOGLE_DRIVE': 'true'}, clear=True):
                manager = PaaSConfigManager()
                manager.save_config_to_file(temp_file_path)
                
                # ファイル内容確認
                with open(temp_file_path, 'r') as f:
                    saved_config = json.load(f)
                
                assert saved_config['enable_google_drive'] is True
                assert saved_config['environment'] == 'development'
                
        finally:
            Path(temp_file_path).unlink(missing_ok=True)
    
    def test_reload_config(self):
        """設定再読み込みテスト"""
        manager = PaaSConfigManager()
        
        # 初回読み込み
        with patch.dict(os.environ, {'ENABLE_GOOGLE_DRIVE': 'false'}, clear=True):
            config1 = manager.load_config()
            assert config1.enable_google_drive is False
        
        # 環境変数変更後、再読み込み
        with patch.dict(os.environ, {'ENABLE_GOOGLE_DRIVE': 'true'}, clear=True):
            manager.reload_config()
            config2 = manager.load_config()
            assert config2.enable_google_drive is True


class TestSingletonFunctions:
    """シングルトン関数テストクラス"""
    
    def test_get_config_manager_singleton(self):
        """get_config_manager()シングルトンテスト"""
        manager1 = get_config_manager()
        manager2 = get_config_manager()
        
        assert manager1 is manager2  # 同一インスタンス
    
    def test_init_config_manager_override(self):
        """init_config_manager()での上書きテスト"""
        # 初期状態
        manager1 = get_config_manager()
        
        # 明示的初期化
        manager2 = init_config_manager("/custom/config.json")
        
        # 新しいインスタンスに置き換わる
        manager3 = get_config_manager()
        assert manager3 is manager2
        assert manager3 is not manager1
    
    def test_is_feature_enabled_convenience(self):
        """is_feature_enabled()便利関数テスト"""
        with patch.dict(os.environ, {
            'ENABLE_GOOGLE_DRIVE': 'true',
            'ENABLE_VECTOR_SEARCH': 'false'
        }, clear=True):
            # グローバル設定マネージャーをリセット
            with patch('agent.source.interfaces.config_manager._config_manager', None):
                assert is_feature_enabled('google_drive') is True
                assert is_feature_enabled('vector_search') is False
                assert is_feature_enabled('authentication') is False
                assert is_feature_enabled('unknown_feature') is False
    
    def test_get_feature_config_convenience(self):
        """get_feature_config()便利関数テスト"""
        with patch.dict(os.environ, {
            'ENABLE_GOOGLE_DRIVE': 'true',
            'GOOGLE_DRIVE_CREDENTIALS_PATH': '/test/path'
        }, clear=True):
            # グローバル設定マネージャーをリセット
            with patch('agent.source.interfaces.config_manager._config_manager', None):
                gd_config = get_feature_config('google_drive')
                assert gd_config is not None
                assert isinstance(gd_config, GoogleDriveConfig)
                
                vs_config = get_feature_config('vector_search')
                assert vs_config is None
                
                unknown_config = get_feature_config('unknown_feature')
                assert unknown_config is None


class TestEnvTemplateGeneration:
    """環境変数テンプレート生成テストクラス"""
    
    def test_create_env_template(self):
        """環境変数テンプレート作成テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            
            try:
                # テンプレート作成
                create_env_template()
                
                # ファイル存在確認
                template_path = Path(".env.template")
                assert template_path.exists()
                
                # 内容確認
                content = template_path.read_text()
                assert "ENABLE_GOOGLE_DRIVE=" in content
                assert "ENABLE_VECTOR_SEARCH=" in content
                assert "ENABLE_AUTHENTICATION=" in content
                assert "GOOGLE_DRIVE_CREDENTIALS_PATH=" in content
                assert "OAUTH_CLIENT_ID=" in content
                
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    """スタンドアロンテスト実行"""
    print("=== config_manager.py モジュールテスト実行 ===")
    
    # テスト実行
    import subprocess
    import sys
    
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            __file__, 
            '-v', 
            '--tb=short'
        ], cwd=Path(__file__).parent.parent.parent, capture_output=True, text=True)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        print(f"\nテスト結果: {'SUCCESS' if result.returncode == 0 else 'FAILED'}")
        sys.exit(result.returncode)
        
    except Exception as e:
        print(f"テスト実行エラー: {e}")
        sys.exit(1)