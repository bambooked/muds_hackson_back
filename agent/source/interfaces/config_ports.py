"""
設定管理インターフェース定義

このモジュールは、環境別設定管理、機能切り替え、秘密情報管理を抽象化します。
開発・ステージング・本番環境での設定分離と、動的な機能制御を提供。

Claude Code実装ガイダンス：
- 環境変数とファイル設定の統合管理
- 秘密情報の安全な取り扱い
- 設定変更の即座反映
- 設定検証とエラーハンドリング

実装優先順位：
1. ConfigurationPort (基本設定管理)
2. EnvironmentPort (環境別設定)
3. FeatureTogglePort (機能切り替え)

セキュリティ要件：
- 秘密情報の暗号化保存
- 設定変更の監査ログ
- 権限ベース設定アクセス
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union, Type, TypeVar
from datetime import datetime
from enum import Enum
from pathlib import Path
import json

from .data_models import (
    PaaSConfig,
    GoogleDriveConfig,
    VectorSearchConfig,
    AuthConfig,
    UserContext,
    PaaSError
)


T = TypeVar('T')


class Environment(Enum):
    """環境種別"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class ConfigSource(Enum):
    """設定ソース"""
    ENVIRONMENT_VARIABLES = "env_vars"
    CONFIG_FILE = "config_file"
    DATABASE = "database"
    REMOTE_CONFIG = "remote_config"
    DEFAULT = "default"


class SecretType(Enum):
    """秘密情報種別"""
    API_KEY = "api_key"
    PASSWORD = "password"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    CONNECTION_STRING = "connection_string"


class ConfigurationPort(ABC):
    """
    設定管理インターフェース
    
    役割：
    - 統一設定アクセス
    - 設定検証
    - 動的設定更新
    
    Claude Code実装ガイダンス：
    - 型安全な設定アクセス
    - 階層的設定構造サポート
    - 設定変更の即座反映
    - デフォルト値の適切な処理
    
    推奨実装パッケージ：
    - pydantic（設定検証）
    - python-dotenv（環境変数）
    - cryptography（秘密情報暗号化）
    """
    
    @abstractmethod
    async def load_config(
        self,
        environment: Environment,
        config_sources: List[ConfigSource] = None
    ) -> PaaSConfig:
        """
        設定読み込み
        
        Args:
            environment: 対象環境
            config_sources: 設定ソース優先順位
            
        Returns:
            PaaSConfig: 読み込まれた設定
            
        Claude Code実装例：
        ```python
        async def load_config(self, environment, config_sources=None):
            if config_sources is None:
                config_sources = [
                    ConfigSource.ENVIRONMENT_VARIABLES,
                    ConfigSource.CONFIG_FILE,
                    ConfigSource.DEFAULT
                ]
            
            config_data = {}
            
            # 各ソースから設定を読み込み（優先順位順）
            for source in config_sources:
                try:
                    source_data = await self._load_from_source(source, environment)
                    config_data.update(source_data)
                except Exception as e:
                    # ログ出力して継続
                    pass
            
            # PaaSConfig作成・検証
            try:
                return PaaSConfig(**config_data)
            except Exception as e:
                raise PaaSError(f"Config validation failed: {e}")
        ```
        """
        pass
    
    @abstractmethod
    async def get_config_value(
        self,
        key: str,
        default: Optional[T] = None,
        value_type: Type[T] = str
    ) -> Optional[T]:
        """
        設定値取得
        
        Args:
            key: 設定キー（ドット記法サポート: 'google_drive.client_id'）
            default: デフォルト値
            value_type: 期待する型
            
        Returns:
            Optional[T]: 設定値
            
        Claude Code実装例：
        ```python
        async def get_config_value(self, key, default=None, value_type=str):
            try:
                # ドット記法による階層アクセス
                keys = key.split('.')
                value = self.current_config
                
                for k in keys:
                    if hasattr(value, k):
                        value = getattr(value, k)
                    elif isinstance(value, dict) and k in value:
                        value = value[k]
                    else:
                        return default
                
                # 型変換
                if value_type != str and value is not None:
                    return value_type(value)
                
                return value
            except Exception:
                return default
        ```
        """
        pass
    
    @abstractmethod
    async def set_config_value(
        self,
        key: str,
        value: Any,
        persist: bool = True,
        user_context: Optional[UserContext] = None
    ) -> bool:
        """
        設定値更新
        
        Args:
            key: 設定キー
            value: 新しい値
            persist: 永続化するか
            user_context: 更新実行ユーザー
            
        Returns:
            bool: 更新成功可否
            
        Claude Code実装時の注意：
        - 権限チェック（管理者のみ設定変更可能）
        - 設定検証実行
        - 変更履歴の記録
        - 関連サービスへの通知
        """
        pass
    
    @abstractmethod
    async def validate_config(
        self,
        config: PaaSConfig
    ) -> Dict[str, List[str]]:
        """
        設定検証
        
        Args:
            config: 検証対象設定
            
        Returns:
            Dict[str, List[str]]: エラー情報（キー別エラーリスト）
            
        Claude Code実装例：
        ```python
        async def validate_config(self, config):
            errors = {}
            
            # 必須項目チェック
            if config.enable_google_drive and not config.google_drive:
                errors['google_drive'] = ['Google Drive config required when enabled']
            
            # Google Drive設定検証
            if config.google_drive:
                drive_errors = []
                if not config.google_drive.credentials_path:
                    drive_errors.append('credentials_path is required')
                if not Path(config.google_drive.credentials_path).exists():
                    drive_errors.append('credentials file not found')
                if drive_errors:
                    errors['google_drive'] = drive_errors
            
            # その他の検証...
            
            return errors
        ```
        """
        pass
    
    @abstractmethod
    async def get_config_schema(self) -> Dict[str, Any]:
        """
        設定スキーマ取得
        
        Returns:
            Dict: JSONスキーマ形式の設定スキーマ
        """
        pass
    
    @abstractmethod
    async def reload_config(
        self,
        user_context: Optional[UserContext] = None
    ) -> bool:
        """
        設定再読み込み
        
        Args:
            user_context: 実行ユーザー
            
        Returns:
            bool: 再読み込み成功可否
        """
        pass


class EnvironmentPort(ABC):
    """
    環境別設定管理インターフェース
    
    役割：
    - 環境別設定分離
    - 環境間設定移行
    - 環境固有リソース管理
    
    Claude Code実装ガイダンス：
    - 環境別設定ファイル管理
    - 本番環境での設定保護
    - 開発環境での設定簡素化
    """
    
    @abstractmethod
    async def get_current_environment(self) -> Environment:
        """
        現在の環境取得
        
        Returns:
            Environment: 現在の環境
            
        Claude Code実装例：
        ```python
        async def get_current_environment(self):
            env_name = os.getenv('PAAS_ENVIRONMENT', 'development').lower()
            try:
                return Environment(env_name)
            except ValueError:
                return Environment.DEVELOPMENT
        ```
        """
        pass
    
    @abstractmethod
    async def switch_environment(
        self,
        target_environment: Environment,
        user_context: Optional[UserContext] = None
    ) -> bool:
        """
        環境切り替え
        
        Args:
            target_environment: 切り替え先環境
            user_context: 実行ユーザー
            
        Returns:
            bool: 切り替え成功可否
            
        Claude Code実装時の注意：
        - 本番環境への切り替えは特別な権限必須
        - 環境切り替え時のサービス再起動
        - 設定の検証と移行
        """
        pass
    
    @abstractmethod
    async def get_environment_config(
        self,
        environment: Environment
    ) -> Dict[str, Any]:
        """
        環境別設定取得
        
        Args:
            environment: 対象環境
            
        Returns:
            Dict: 環境別設定
        """
        pass
    
    @abstractmethod
    async def deploy_config_to_environment(
        self,
        source_environment: Environment,
        target_environment: Environment,
        config_keys: Optional[List[str]] = None,
        user_context: Optional[UserContext] = None
    ) -> bool:
        """
        環境間設定デプロイ
        
        Args:
            source_environment: コピー元環境
            target_environment: コピー先環境
            config_keys: コピーする設定キー（Noneの場合は全て）
            user_context: 実行ユーザー
            
        Returns:
            bool: デプロイ成功可否
        """
        pass
    
    @abstractmethod
    async def backup_environment_config(
        self,
        environment: Environment,
        backup_name: Optional[str] = None
    ) -> str:
        """
        環境設定バックアップ
        
        Args:
            environment: バックアップ対象環境
            backup_name: バックアップ名（自動生成可能）
            
        Returns:
            str: バックアップID
        """
        pass


class FeatureTogglePort(ABC):
    """
    機能切り替え管理インターフェース
    
    役割：
    - 機能のON/OFF制御
    - A/Bテスト支援
    - 段階的ロールアウト
    
    Claude Code実装ガイダンス：
    - リアルタイム機能切り替え
    - ユーザー別・環境別切り替え
    - 機能依存関係の管理
    """
    
    @abstractmethod
    async def is_feature_enabled(
        self,
        feature_name: str,
        user_context: Optional[UserContext] = None,
        environment: Optional[Environment] = None
    ) -> bool:
        """
        機能有効状態確認
        
        Args:
            feature_name: 機能名
            user_context: ユーザーコンテキスト
            environment: 環境（未指定時は現在環境）
            
        Returns:
            bool: 機能有効可否
            
        Claude Code実装例：
        ```python
        async def is_feature_enabled(self, feature_name, user_context=None, environment=None):
            # 環境レベルの設定確認
            if environment is None:
                environment = await self.env_port.get_current_environment()
            
            env_config = await self.config_port.get_config_value(
                f'features.{feature_name}.enabled',
                default=False,
                value_type=bool
            )
            
            if not env_config:
                return False
            
            # ユーザー別設定確認（A/Bテスト等）
            if user_context:
                user_override = await self._get_user_feature_override(
                    feature_name, user_context
                )
                if user_override is not None:
                    return user_override
            
            return env_config
        ```
        """
        pass
    
    @abstractmethod
    async def enable_feature(
        self,
        feature_name: str,
        scope: str = 'global',
        scope_value: Optional[str] = None,
        user_context: Optional[UserContext] = None
    ) -> bool:
        """
        機能有効化
        
        Args:
            feature_name: 機能名
            scope: 'global', 'environment', 'user', 'role'
            scope_value: スコープ固有値（ユーザーID、役割名等）
            user_context: 実行ユーザー
            
        Returns:
            bool: 有効化成功可否
            
        Claude Code実装時の注意：
        - 権限チェック（管理者のみ）
        - 機能依存関係のチェック
        - 変更の監査ログ記録
        """
        pass
    
    @abstractmethod
    async def disable_feature(
        self,
        feature_name: str,
        scope: str = 'global',
        scope_value: Optional[str] = None,
        user_context: Optional[UserContext] = None
    ) -> bool:
        """
        機能無効化
        
        Args:
            feature_name: 機能名
            scope: 'global', 'environment', 'user', 'role'
            scope_value: スコープ固有値
            user_context: 実行ユーザー
            
        Returns:
            bool: 無効化成功可否
        """
        pass
    
    @abstractmethod
    async def list_features(
        self,
        environment: Optional[Environment] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        機能一覧取得
        
        Args:
            environment: 対象環境
            
        Returns:
            Dict: {
                'google_drive': {
                    'enabled': True,
                    'description': 'Google Drive integration',
                    'dependencies': [],
                    'last_updated': '2025-07-03T10:00:00Z'
                },
                ...
            }
        """
        pass
    
    @abstractmethod
    async def create_feature_flag(
        self,
        feature_name: str,
        description: str,
        default_enabled: bool = False,
        dependencies: List[str] = None,
        user_context: Optional[UserContext] = None
    ) -> bool:
        """
        機能フラグ作成
        
        Args:
            feature_name: 機能名
            description: 機能説明
            default_enabled: デフォルト有効状態
            dependencies: 依存機能リスト
            user_context: 実行ユーザー
            
        Returns:
            bool: 作成成功可否
        """
        pass


# ========================================
# Implementation Helper Classes
# ========================================

class ConfigurationRegistry:
    """
    設定管理統合クラス
    
    Claude Code実装ガイダンス：
    - 各設定ポートの統合管理
    - 設定変更の一元制御
    - キャッシュとパフォーマンス最適化
    """
    
    def __init__(self):
        self.config_port: Optional[ConfigurationPort] = None
        self.env_port: Optional[EnvironmentPort] = None
        self.feature_port: Optional[FeatureTogglePort] = None
        self._config_cache: Dict[str, Any] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5分
    
    def register_configuration_port(self, port: ConfigurationPort):
        """設定管理ポート登録"""
        self.config_port = port
    
    def register_environment_port(self, port: EnvironmentPort):
        """環境管理ポート登録"""
        self.env_port = port
    
    def register_feature_toggle_port(self, port: FeatureTogglePort):
        """機能切り替えポート登録"""
        self.feature_port = port
    
    async def get_effective_config(
        self,
        user_context: Optional[UserContext] = None
    ) -> PaaSConfig:
        """
        実効設定取得（キャッシュ付き）
        
        Claude Code実装時の注意：
        - 設定変更時のキャッシュ無効化
        - ユーザー固有設定の適用
        - パフォーマンス最適化
        """
        now = datetime.now()
        
        # キャッシュ有効性チェック
        if (self._cache_timestamp and 
            (now - self._cache_timestamp).total_seconds() < self._cache_ttl_seconds and
            'base_config' in self._config_cache):
            
            base_config = self._config_cache['base_config']
        else:
            # 設定再読み込み
            if not self.env_port or not self.config_port:
                raise PaaSError("Configuration ports not registered")
            
            current_env = await self.env_port.get_current_environment()
            base_config = await self.config_port.load_config(current_env)
            
            # キャッシュ更新
            self._config_cache['base_config'] = base_config
            self._cache_timestamp = now
        
        # ユーザー固有設定適用
        if user_context and self.feature_port:
            # 機能切り替え状態を反映
            base_config.enable_google_drive = await self.feature_port.is_feature_enabled(
                'google_drive', user_context
            )
            base_config.enable_vector_search = await self.feature_port.is_feature_enabled(
                'vector_search', user_context
            )
            # その他の機能も同様に...
        
        return base_config
    
    async def invalidate_cache(self):
        """設定キャッシュ無効化"""
        self._config_cache.clear()
        self._cache_timestamp = None


# ========================================
# Default Configuration Templates
# ========================================

def create_development_config() -> Dict[str, Any]:
    """
    開発環境用デフォルト設定
    
    Claude Code実装時の注意：
    - 開発効率重視の設定
    - セキュリティは緩め
    - デバッグ機能有効
    """
    return {
        'environment': Environment.DEVELOPMENT.value,
        'debug': True,
        'api_host': '127.0.0.1',
        'api_port': 8000,
        'enable_google_drive': False,  # 開発時はローカルファイルのみ
        'enable_vector_search': True,   # 開発時はChromaDB使用
        'enable_authentication': False, # 開発時は認証なし
        'enable_monitoring': False,     # 開発時は軽量化
        'vector_search': {
            'provider': 'chroma',
            'host': 'localhost',
            'port': 8001,
            'collection_name': 'dev_research_documents',
            'persist_directory': './data/vector_db_dev'
        }
    }


def create_production_config() -> Dict[str, Any]:
    """
    本番環境用デフォルト設定
    
    Claude Code実装時の注意：
    - セキュリティ最優先
    - パフォーマンス最適化
    - 監視・ログ強化
    """
    return {
        'environment': Environment.PRODUCTION.value,
        'debug': False,
        'api_host': '0.0.0.0',
        'api_port': 443,
        'enable_google_drive': True,
        'enable_vector_search': True,
        'enable_authentication': True,  # 本番では認証必須
        'enable_monitoring': True,      # 本番では監視必須
        'auth': {
            'provider': 'google_oauth2',
            'allowed_domains': ['university.ac.jp'],
            'session_timeout_minutes': 480,
            'require_email_verification': True
        },
        'vector_search': {
            'provider': 'qdrant',  # 本番では高性能なQdrant
            'host': 'qdrant-cluster',
            'port': 6333,
            'collection_name': 'research_documents',
            'similarity_threshold': 0.8
        }
    }


# ========================================
# Utility Functions for Claude Code
# ========================================

async def setup_configuration_system(
    environment: Environment = Environment.DEVELOPMENT,
    config_file_path: Optional[Path] = None
) -> ConfigurationRegistry:
    """
    設定システムセットアップヘルパー
    
    Claude Code実装時の使用例：
    ```python
    config_registry = await setup_configuration_system(
        Environment.DEVELOPMENT,
        Path('./config/development.json')
    )
    
    config = await config_registry.get_effective_config()
    ```
    """
    registry = ConfigurationRegistry()
    
    # 各ポートの実装を作成・登録
    # (実際の実装は具体的なポート実装クラスで行う)
    
    return registry


def merge_configs(base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    設定のマージ
    
    Claude Code実装ガイダンス：
    - 深い階層の設定もマージ
    - リスト項目の適切な処理
    - None値の処理
    """
    result = base_config.copy()
    
    for key, value in override_config.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    
    return result


def validate_environment_transition(
    from_env: Environment,
    to_env: Environment,
    user_context: Optional[UserContext] = None
) -> List[str]:
    """
    環境遷移の検証
    
    Returns:
        List[str]: 警告・エラーメッセージリスト
        
    Claude Code実装ガイダンス：
    - 本番環境への遷移は特別な権限チェック
    - データ損失リスクの警告
    - バックアップ推奨の通知
    """
    warnings = []
    
    if to_env == Environment.PRODUCTION:
        if not user_context or not user_context.has_permission('system', 'admin'):
            warnings.append("Production environment requires admin permission")
        
        if from_env != Environment.STAGING:
            warnings.append("Direct deployment to production not recommended")
    
    if to_env == Environment.PRODUCTION and from_env == Environment.DEVELOPMENT:
        warnings.append("Consider testing in staging environment first")
    
    return warnings