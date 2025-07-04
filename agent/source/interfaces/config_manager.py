"""
PaaS設定管理システム

このモジュールは、新機能の有効/無効切り替えと既存config.pyとの統合を提供します。
環境変数や設定ファイルからPaaS機能の設定を読み込み、各ポートの初期化を制御します。

Claude Code実装ガイダンス：
- 既存config.pyとの互換性維持
- 環境変数による設定オーバーライド
- フォールバック機能：新機能無効時は既存システム継続
- 設定検証とエラーハンドリング

設定例（.env）：
```
# PaaS機能切り替え
ENABLE_GOOGLE_DRIVE=true
ENABLE_VECTOR_SEARCH=false
ENABLE_AUTHENTICATION=false

# Google Drive設定
GOOGLE_DRIVE_CREDENTIALS_PATH=/path/to/credentials.json
GOOGLE_DRIVE_MAX_FILE_SIZE_MB=100

# 認証設定（将来用）
OAUTH_CLIENT_ID=your_client_id
OAUTH_CLIENT_SECRET=your_client_secret
```
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import asdict

try:
    from .data_models import (
        PaaSConfig,
        GoogleDriveConfig,
        VectorSearchConfig,
        AuthConfig
    )
except ImportError:
    # スタンドアロン実行時の絶対インポート
    from agent.source.interfaces.data_models import (
        PaaSConfig,
        GoogleDriveConfig,
        VectorSearchConfig,
        AuthConfig
    )


class PaaSConfigManager:
    """
    PaaS設定の統合管理クラス
    
    役割：
    1. 環境変数からPaaS設定を読み込み
    2. 設定ファイルとの統合
    3. 各ポートの初期化制御
    4. 設定変更時の動的切り替え
    """
    
    def __init__(self, config_file_path: Optional[str] = None):
        """
        初期化
        
        Args:
            config_file_path: 設定ファイルパス（オプション）
        """
        self.config_file_path = config_file_path
        self._config: Optional[PaaSConfig] = None
        self._logger = logging.getLogger(__name__)
    
    def load_config(self) -> PaaSConfig:
        """
        設定を読み込み・構築
        
        Returns:
            PaaSConfig: 構築された設定
        """
        if self._config is None:
            self._config = self._build_config()
            self._validate_config()
        
        return self._config
    
    def _build_config(self) -> PaaSConfig:
        """設定構築（環境変数 + 設定ファイル）"""
        # 基本設定
        config = PaaSConfig(
            environment=os.getenv("PAAS_ENVIRONMENT", "development"),
            api_host=os.getenv("API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("API_PORT", "8000")),
            debug=os.getenv("DEBUG", "false").lower() == "true"
        )
        
        # 機能フラグ
        config.enable_google_drive = self._get_bool_env("ENABLE_GOOGLE_DRIVE", False)
        config.enable_vector_search = self._get_bool_env("ENABLE_VECTOR_SEARCH", False)
        config.enable_authentication = self._get_bool_env("ENABLE_AUTHENTICATION", False)
        config.enable_monitoring = self._get_bool_env("ENABLE_MONITORING", False)
        
        # Google Drive設定
        if config.enable_google_drive:
            config.google_drive = self._build_google_drive_config()
        
        # Vector Search設定
        if config.enable_vector_search:
            config.vector_search = self._build_vector_search_config()
        
        # 認証設定
        if config.enable_authentication:
            config.auth = self._build_auth_config()
        
        # 設定ファイルからの追加読み込み
        if self.config_file_path and Path(self.config_file_path).exists():
            file_config = self._load_config_file()
            config = self._merge_configs(config, file_config)
        
        self._logger.info(f"PaaS設定を読み込みました: {self._get_config_summary(config)}")
        return config
    
    def _build_google_drive_config(self) -> GoogleDriveConfig:
        """Google Drive設定構築"""
        credentials_path = os.getenv("GOOGLE_DRIVE_CREDENTIALS_PATH", "")
        if not credentials_path:
            self._logger.warning("Google Drive有効だが認証情報パスが未設定")
        
        return GoogleDriveConfig(
            credentials_path=credentials_path,
            scopes=self._get_list_env("GOOGLE_DRIVE_SCOPES", [
                'https://www.googleapis.com/auth/drive.readonly'
            ]),
            max_file_size_mb=int(os.getenv("GOOGLE_DRIVE_MAX_FILE_SIZE_MB", "100")),
            supported_mime_types=self._get_list_env("GOOGLE_DRIVE_SUPPORTED_TYPES", [
                'application/pdf',
                'text/csv',
                'application/json',
                'text/plain'
            ]),
            sync_interval_minutes=int(os.getenv("GOOGLE_DRIVE_SYNC_INTERVAL", "60")),
            batch_size=int(os.getenv("GOOGLE_DRIVE_BATCH_SIZE", "10"))
        )
    
    def _build_vector_search_config(self) -> VectorSearchConfig:
        """Vector Search設定構築"""
        return VectorSearchConfig(
            provider=os.getenv("VECTOR_SEARCH_PROVIDER", "chroma"),
            host=os.getenv("VECTOR_SEARCH_HOST", "localhost"),
            port=int(os.getenv("VECTOR_SEARCH_PORT", "8000")),
            collection_name=os.getenv("VECTOR_SEARCH_COLLECTION", "research_documents"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
            similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.7")),
            max_results=int(os.getenv("VECTOR_SEARCH_MAX_RESULTS", "50")),
            persist_directory=os.getenv("VECTOR_SEARCH_PERSIST_DIR")
        )
    
    def _build_auth_config(self) -> AuthConfig:
        """認証設定構築"""
        return AuthConfig(
            provider=os.getenv("AUTH_PROVIDER", "google_oauth2"),
            client_id=os.getenv("OAUTH_CLIENT_ID", ""),
            client_secret=os.getenv("OAUTH_CLIENT_SECRET", ""),
            redirect_uri=os.getenv("OAUTH_REDIRECT_URI", ""),
            allowed_domains=self._get_list_env("OAUTH_ALLOWED_DOMAINS", []),
            session_timeout_minutes=int(os.getenv("SESSION_TIMEOUT_MINUTES", "480")),
            require_email_verification=self._get_bool_env("REQUIRE_EMAIL_VERIFICATION", True)
        )
    
    def _load_config_file(self) -> Dict[str, Any]:
        """設定ファイル読み込み"""
        try:
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self._logger.warning(f"設定ファイル読み込み失敗: {e}")
            return {}
    
    def _merge_configs(self, base_config: PaaSConfig, file_config: Dict[str, Any]) -> PaaSConfig:
        """設定マージ（ファイル設定で環境変数設定をオーバーライド）"""
        # 簡易実装：主要フラグのみオーバーライド
        if "enable_google_drive" in file_config:
            base_config.enable_google_drive = file_config["enable_google_drive"]
        if "enable_vector_search" in file_config:
            base_config.enable_vector_search = file_config["enable_vector_search"]
        if "enable_authentication" in file_config:
            base_config.enable_authentication = file_config["enable_authentication"]
        
        return base_config
    
    def _validate_config(self):
        """設定検証"""
        if not self._config:
            return
        
        # Google Drive設定検証
        if self._config.enable_google_drive and self._config.google_drive:
            creds_path = self._config.google_drive.credentials_path
            if creds_path and not Path(creds_path).exists():
                self._logger.warning(f"Google Drive認証ファイルが見つかりません: {creds_path}")
        
        # Vector Search設定検証
        if self._config.enable_vector_search and self._config.vector_search:
            if self._config.vector_search.provider not in ['chroma', 'qdrant', 'pinecone']:
                self._logger.warning(f"サポートされていないVector Searchプロバイダー: {self._config.vector_search.provider}")
        
        # 認証設定検証
        if self._config.enable_authentication and self._config.auth:
            if not self._config.auth.client_id or not self._config.auth.client_secret:
                self._logger.warning("認証有効だがOAuth認証情報が不完全です")
    
    def _get_config_summary(self, config: PaaSConfig) -> str:
        """設定サマリー生成"""
        enabled_features = []
        if config.enable_google_drive:
            enabled_features.append("GoogleDrive")
        if config.enable_vector_search:
            enabled_features.append("VectorSearch")
        if config.enable_authentication:
            enabled_features.append("Authentication")
        if config.enable_monitoring:
            enabled_features.append("Monitoring")
        
        return f"環境={config.environment}, 有効機能=[{', '.join(enabled_features)}]"
    
    def _get_bool_env(self, key: str, default: bool) -> bool:
        """環境変数からブール値取得"""
        value = os.getenv(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    def _get_list_env(self, key: str, default: list) -> list:
        """環境変数からリスト取得（カンマ区切り）"""
        value = os.getenv(key)
        if value:
            return [item.strip() for item in value.split(',')]
        return default
    
    # ========================================
    # Public Interface Methods
    # ========================================
    
    def is_google_drive_enabled(self) -> bool:
        """Google Drive機能が有効かチェック"""
        config = self.load_config()
        return config.enable_google_drive
    
    def is_vector_search_enabled(self) -> bool:
        """Vector Search機能が有効かチェック"""
        config = self.load_config()
        return config.enable_vector_search
    
    def is_authentication_enabled(self) -> bool:
        """認証機能が有効かチェック"""
        config = self.load_config()
        return config.enable_authentication
    
    def get_google_drive_config(self) -> Optional[GoogleDriveConfig]:
        """Google Drive設定取得"""
        config = self.load_config()
        return config.google_drive if config.enable_google_drive else None
    
    def get_vector_search_config(self) -> Optional[VectorSearchConfig]:
        """Vector Search設定取得"""
        config = self.load_config()
        return config.vector_search if config.enable_vector_search else None
    
    def get_auth_config(self) -> Optional[AuthConfig]:
        """認証設定取得"""
        config = self.load_config()
        return config.auth if config.enable_authentication else None
    
    def save_config_to_file(self, file_path: str):
        """設定をファイルに保存"""
        config = self.load_config()
        config_dict = asdict(config)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False, default=str)
        
        self._logger.info(f"設定をファイルに保存しました: {file_path}")
    
    def reload_config(self):
        """設定を再読み込み"""
        self._config = None
        self.load_config()
        self._logger.info("設定を再読み込みしました")


# ========================================
# Singleton Instance
# ========================================

# グローバル設定マネージャーインスタンス
_config_manager: Optional[PaaSConfigManager] = None


def get_config_manager() -> PaaSConfigManager:
    """
    設定マネージャーのシングルトンインスタンス取得
    
    Claude Code使用例：
    ```python
    from agent.source.interfaces.config_manager import get_config_manager
    
    config_manager = get_config_manager()
    
    if config_manager.is_google_drive_enabled():
        google_config = config_manager.get_google_drive_config()
        # Google Drive機能を初期化
    else:
        # 既存システム継続
    ```
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = PaaSConfigManager()
    return _config_manager


def init_config_manager(config_file_path: Optional[str] = None) -> PaaSConfigManager:
    """
    設定マネージャーを明示的に初期化
    
    Args:
        config_file_path: 設定ファイルパス
        
    Returns:
        PaaSConfigManager: 初期化された設定マネージャー
    """
    global _config_manager
    _config_manager = PaaSConfigManager(config_file_path)
    return _config_manager


# ========================================
# Convenience Functions
# ========================================

def is_feature_enabled(feature_name: str) -> bool:
    """
    機能有効状態の簡易チェック
    
    Args:
        feature_name: 'google_drive', 'vector_search', 'authentication'
        
    Returns:
        bool: 機能有効状態
    """
    manager = get_config_manager()
    
    if feature_name == 'google_drive':
        return manager.is_google_drive_enabled()
    elif feature_name == 'vector_search':
        return manager.is_vector_search_enabled()
    elif feature_name == 'authentication':
        return manager.is_authentication_enabled()
    else:
        return False


def get_feature_config(feature_name: str) -> Optional[Any]:
    """
    機能設定の簡易取得
    
    Args:
        feature_name: 'google_drive', 'vector_search', 'authentication'
        
    Returns:
        対応する設定オブジェクト（機能無効時はNone）
    """
    manager = get_config_manager()
    
    if feature_name == 'google_drive':
        return manager.get_google_drive_config()
    elif feature_name == 'vector_search':
        return manager.get_vector_search_config()
    elif feature_name == 'authentication':
        return manager.get_auth_config()
    else:
        return None


# ========================================
# Integration with Existing Config
# ========================================

def create_env_template():
    """
    環境変数テンプレートファイル作成
    
    Claude Code使用時の注意：
    - 開発者が設定を理解しやすいようテンプレート提供
    - 実際の認証情報は含めない
    """
    template_content = """# PaaS機能設定
# 各機能を有効にするにはtrueに設定してください

# Google Drive連携
ENABLE_GOOGLE_DRIVE=false
GOOGLE_DRIVE_CREDENTIALS_PATH=/path/to/google_drive_credentials.json
GOOGLE_DRIVE_MAX_FILE_SIZE_MB=100
GOOGLE_DRIVE_SYNC_INTERVAL=60

# ベクトル検索
ENABLE_VECTOR_SEARCH=false
VECTOR_SEARCH_PROVIDER=chroma
VECTOR_SEARCH_HOST=localhost
VECTOR_SEARCH_PORT=8000

# 認証システム
ENABLE_AUTHENTICATION=false
OAUTH_CLIENT_ID=your_google_oauth_client_id
OAUTH_CLIENT_SECRET=your_google_oauth_client_secret
OAUTH_REDIRECT_URI=http://localhost:8000/auth/callback

# モニタリング
ENABLE_MONITORING=false

# API設定
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false
PAAS_ENVIRONMENT=development
"""
    
    template_path = Path(".env.template")
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(template_content)
    
    print(f"環境変数テンプレートを作成しました: {template_path}")
    print("実際の設定には.envファイルを作成してください。")


if __name__ == "__main__":
    """スタンドアロン実行時の設定確認"""
    print("=== PaaS Configuration Manager Test ===")
    
    # 設定マネージャー初期化
    manager = get_config_manager()
    config = manager.load_config()
    
    print(f"環境: {config.environment}")
    print(f"API Host: {config.api_host}:{config.api_port}")
    print(f"デバッグモード: {config.debug}")
    print()
    
    print("機能有効状態:")
    print(f"  Google Drive: {config.enable_google_drive}")
    print(f"  Vector Search: {config.enable_vector_search}")
    print(f"  認証: {config.enable_authentication}")
    print(f"  モニタリング: {config.enable_monitoring}")
    print()
    
    if config.enable_google_drive and config.google_drive:
        print("Google Drive設定:")
        print(f"  認証ファイル: {config.google_drive.credentials_path}")
        print(f"  最大ファイルサイズ: {config.google_drive.max_file_size_mb}MB")
        print(f"  サポート形式: {config.google_drive.supported_mime_types}")
    
    # 環境変数テンプレート作成
    create_env_template()