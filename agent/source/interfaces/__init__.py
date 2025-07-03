"""
インターフェースパッケージ - 並行開発用抽象化レイヤー

このパッケージは、複数のClaude Codeインスタンスが並行して開発できるよう、
明確なインターフェース境界を定義します。

設計原則：
1. 非破壊的拡張: 既存システムは変更しない
2. 完全独立性: 各ポートは他に依存しない  
3. テスト容易性: モック実装が簡単
4. 型安全性: 完全な型ヒント
5. Claude Code最適化: 実装ガイダンス充実

パッケージ構成：
- data_models: 共通データ型定義
- input_ports: データ入力インターフェース
- search_ports: 検索機能インターフェース
- auth_ports: 認証・認可インターフェース
- service_ports: サービス統合インターフェース
- config_ports: 設定管理インターフェース
"""

from .data_models import (
    # Core Data Models
    DocumentContent,
    DocumentMetadata,
    SearchResult,
    IngestionResult,
    UserContext,
    JobStatus,
    SystemStats,
    
    # Configuration Models
    GoogleDriveConfig,
    VectorSearchConfig,
    AuthConfig,
    PaaSConfig,
    
    # Error Models
    PaaSError,
    InputError,
    SearchError,
    AuthError,
)

from .input_ports import (
    DocumentInputPort,
    FileUploadPort,
    GoogleDrivePort,
)

from .search_ports import (
    VectorSearchPort,
    SemanticSearchPort,
    HybridSearchPort,
)

from .auth_ports import (
    AuthenticationPort,
    AuthorizationPort,
    UserManagementPort,
)

from .service_ports import (
    DocumentServicePort,
    PaaSOrchestrationPort,
    HealthCheckPort,
)

from .config_ports import (
    ConfigurationPort,
    EnvironmentPort,
    FeatureTogglePort,
)

__all__ = [
    # Data Models
    "DocumentContent",
    "DocumentMetadata", 
    "SearchResult",
    "IngestionResult",
    "UserContext",
    "JobStatus",
    "SystemStats",
    "GoogleDriveConfig",
    "VectorSearchConfig", 
    "AuthConfig",
    "PaaSConfig",
    "PaaSError",
    "InputError",
    "SearchError",
    "AuthError",
    
    # Input Ports
    "DocumentInputPort",
    "FileUploadPort",
    "GoogleDrivePort",
    
    # Search Ports
    "VectorSearchPort",
    "SemanticSearchPort", 
    "HybridSearchPort",
    
    # Auth Ports
    "AuthenticationPort",
    "AuthorizationPort",
    "UserManagementPort",
    
    # Service Ports
    "DocumentServicePort",
    "PaaSOrchestrationPort",
    "HealthCheckPort",
    
    # Config Ports
    "ConfigurationPort",
    "EnvironmentPort",
    "FeatureTogglePort",
]

# Version info for Claude Code compatibility tracking
__version__ = "1.0.0"
__claude_code_optimized__ = True
__parallel_development_ready__ = True