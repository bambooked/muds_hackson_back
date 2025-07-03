"""
サービス統合インターフェース定義

このモジュールは、各ポートを統合してPaaSシステム全体のオーケストレーションを提供します。
既存システムと新機能の橋渡し、ヘルスチェック、監視機能等を統一的に管理。

Claude Code実装ガイダンス：
- 既存UserInterfaceとの完全互換性維持
- 新機能は全てOptionalで段階的統合
- エラー時のフォールバック機能必須
- 設定による機能の有効/無効切り替え

実装優先順位：
1. DocumentServicePort (文書操作統合)
2. PaaSOrchestrationPort (システム統合)
3. HealthCheckPort (監視・運用)

既存システム連携：
- UserInterface: メイン操作インターフェース
- RAGInterface: 外部API用抽象化レイヤー
- paas_api.py: FastAPI エンドポイント
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime
from enum import Enum
import asyncio

from .data_models import (
    DocumentContent,
    DocumentMetadata,
    SearchResult,
    IngestionResult,
    UserContext,
    SystemStats,
    PaaSConfig,
    PaaSError
)

from .input_ports import DocumentInputPort
from .search_ports import VectorSearchPort, HybridSearchPort, SearchMode
from .auth_ports import AuthPortRegistry, Permission


class ServiceStatus(Enum):
    """サービス状態"""
    HEALTHY = "healthy"          # 正常
    DEGRADED = "degraded"        # 一部機能制限
    UNHEALTHY = "unhealthy"      # 異常
    UNKNOWN = "unknown"          # 不明


class FeatureToggle(Enum):
    """機能切り替え"""
    GOOGLE_DRIVE = "google_drive"
    VECTOR_SEARCH = "vector_search"
    AUTHENTICATION = "authentication"
    MONITORING = "monitoring"


class DocumentServicePort(ABC):
    """
    文書操作統合インターフェース
    
    役割：
    - 既存文書操作の拡張
    - 新機能との統合
    - 一貫したAPI提供
    
    Claude Code実装ガイダンス：
    - 既存UserInterfaceを内包してラップ
    - 新機能（Google Drive, ベクトル検索）をOptionalで追加
    - エラー時は既存機能で継続
    - 全メソッドで既存形式との互換性維持
    """
    
    @abstractmethod
    async def ingest_documents(
        self,
        source_type: str,
        source_config: Dict[str, Any],
        user_context: Optional[UserContext] = None
    ) -> IngestionResult:
        """
        文書取り込み（統合）
        
        Args:
            source_type: 'local_scan', 'google_drive', 'upload'
            source_config: ソース固有設定
            user_context: ユーザーコンテキスト
            
        Returns:
            IngestionResult: 取り込み結果
            
        Claude Code実装例：
        ```python
        async def ingest_documents(self, source_type, source_config, user_context=None):
            # 権限チェック（認証有効時のみ）
            if self.auth_registry._auth_enabled:
                authorized = await self.auth_registry.authorize_action(
                    user_context, 'documents', Permission.WRITE
                )
                if not authorized:
                    raise PaaSError("Permission denied")
            
            # ソース別処理
            if source_type == 'local_scan':
                # 既存システムでのローカルスキャン
                return await self._existing_local_scan(source_config, user_context)
            elif source_type == 'google_drive' and self.input_port:
                # Google Drive取り込み
                return await self.input_port.ingest_documents(source_type, source_config, user_context)
            else:
                # フォールバック：既存システム
                return await self._existing_local_scan(source_config, user_context)
        ```
        """
        pass
    
    @abstractmethod
    async def search_documents(
        self,
        query: str,
        search_mode: SearchMode = SearchMode.KEYWORD_ONLY,
        category: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        user_context: Optional[UserContext] = None
    ) -> List[SearchResult]:
        """
        文書検索（統合）
        
        Args:
            query: 検索クエリ
            search_mode: 検索モード
            category: カテゴリフィルタ
            filters: 追加フィルタ
            user_context: ユーザーコンテキスト
            
        Returns:
            List[SearchResult]: 検索結果
            
        Claude Code実装時の注意：
        - 既存search_documentsとの完全互換性
        - 新しい検索モードはOptionalで追加
        - 権限フィルタリング（ユーザー依存）
        - フォールバック機能必須
        """
        pass
    
    @abstractmethod
    async def analyze_document(
        self,
        document_id: int,
        category: str,
        force_reanalyze: bool = False,
        user_context: Optional[UserContext] = None
    ) -> Optional[DocumentMetadata]:
        """
        文書解析（統合）
        
        Args:
            document_id: 文書ID
            category: カテゴリ ('dataset', 'paper', 'poster')
            force_reanalyze: 強制再解析
            user_context: ユーザーコンテキスト
            
        Returns:
            Optional[DocumentMetadata]: 解析結果
            
        Claude Code実装時の注意：
        - 既存NewFileAnalyzerとの統合
        - ベクトル化処理の自動実行（設定有効時）
        - 解析結果の自動インデックス更新
        """
        pass
    
    @abstractmethod
    async def get_document_details(
        self,
        document_id: int,
        category: str,
        user_context: Optional[UserContext] = None
    ) -> Optional[DocumentMetadata]:
        """
        文書詳細取得
        
        Args:
            document_id: 文書ID
            category: カテゴリ
            user_context: ユーザーコンテキスト
            
        Returns:
            Optional[DocumentMetadata]: 文書詳細
        """
        pass
    
    @abstractmethod
    async def delete_document(
        self,
        document_id: int,
        category: str,
        user_context: Optional[UserContext] = None
    ) -> bool:
        """
        文書削除
        
        Args:
            document_id: 文書ID
            category: カテゴリ
            user_context: ユーザーコンテキスト
            
        Returns:
            bool: 削除成功可否
            
        Claude Code実装時の注意：
        - 権限チェック必須（削除権限）
        - ベクトルインデックスからも削除
        - 関連ファイルの物理削除
        - 削除の監査ログ記録
        """
        pass
    
    @abstractmethod
    async def get_system_statistics(
        self,
        user_context: Optional[UserContext] = None
    ) -> SystemStats:
        """
        システム統計取得
        
        Returns:
            SystemStats: システム統計情報
            
        Claude Code実装時の注意：
        - 既存統計情報の拡張
        - 新機能の統計も追加
        - ユーザー権限に応じた情報フィルタリング
        """
        pass


class PaaSOrchestrationPort(ABC):
    """
    PaaSシステム統合オーケストレーションインターフェース
    
    役割：
    - 全サービスの統合管理
    - 機能の有効/無効制御
    - システム全体の初期化・終了処理
    
    Claude Code実装ガイダンス：
    - 各ポートの実装を統合管理
    - 設定に基づく機能切り替え
    - 既存システムとの段階的統合
    - エラー時の適切なフォールバック
    """
    
    @abstractmethod
    async def initialize_system(
        self,
        config: PaaSConfig
    ) -> Dict[str, ServiceStatus]:
        """
        システム初期化
        
        Args:
            config: PaaS設定
            
        Returns:
            Dict[str, ServiceStatus]: サービス別初期化結果
            
        Claude Code実装例：
        ```python
        async def initialize_system(self, config):
            status = {}
            
            # 既存システム初期化（必須）
            try:
                self.existing_system = UserInterface()
                status['existing_system'] = ServiceStatus.HEALTHY
            except Exception as e:
                status['existing_system'] = ServiceStatus.UNHEALTHY
                raise PaaSError(f"Failed to initialize existing system: {e}")
            
            # Google Drive（オプション）
            if config.enable_google_drive and config.google_drive:
                try:
                    # Google Drive初期化
                    status['google_drive'] = ServiceStatus.HEALTHY
                except Exception as e:
                    status['google_drive'] = ServiceStatus.UNHEALTHY
            
            # ベクトル検索（オプション）
            if config.enable_vector_search and config.vector_search:
                try:
                    # ベクトル検索初期化
                    status['vector_search'] = ServiceStatus.HEALTHY
                except Exception as e:
                    status['vector_search'] = ServiceStatus.UNHEALTHY
            
            return status
        ```
        """
        pass
    
    @abstractmethod
    async def enable_feature(
        self,
        feature: FeatureToggle,
        config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        機能有効化
        
        Args:
            feature: 有効化する機能
            config: 機能固有設定
            
        Returns:
            bool: 有効化成功可否
        """
        pass
    
    @abstractmethod
    async def disable_feature(
        self,
        feature: FeatureToggle
    ) -> bool:
        """
        機能無効化
        
        Args:
            feature: 無効化する機能
            
        Returns:
            bool: 無効化成功可否
        """
        pass
    
    @abstractmethod
    async def get_feature_status(self) -> Dict[FeatureToggle, bool]:
        """
        機能状態取得
        
        Returns:
            Dict[FeatureToggle, bool]: 機能別有効/無効状態
        """
        pass
    
    @abstractmethod
    async def migrate_existing_data(
        self,
        migration_type: str,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        既存データの移行・拡張
        
        Args:
            migration_type: 'vector_indexing', 'metadata_update', etc.
            dry_run: 実行前確認モード
            
        Returns:
            Dict: 移行結果
            
        Claude Code実装例（ベクトル化移行）：
        ```python
        async def migrate_existing_data(self, migration_type, dry_run=True):
            if migration_type == 'vector_indexing':
                # 既存文書の自動ベクトル化
                documents = self.existing_system.get_all_documents()
                
                result = {
                    'total_documents': len(documents),
                    'processed': 0,
                    'errors': []
                }
                
                if not dry_run and self.vector_search_port:
                    for doc in documents:
                        try:
                            content = self._extract_content(doc)
                            await self.vector_search_port.index_document(doc, content)
                            result['processed'] += 1
                        except Exception as e:
                            result['errors'].append(f"Doc {doc.id}: {e}")
                
                return result
        ```
        """
        pass
    
    @abstractmethod
    async def backup_system_state(
        self,
        backup_type: str = 'full'
    ) -> Dict[str, Any]:
        """
        システム状態バックアップ
        
        Args:
            backup_type: 'full', 'metadata_only', 'config_only'
            
        Returns:
            Dict: バックアップ結果
        """
        pass
    
    @abstractmethod
    async def shutdown_gracefully(self) -> bool:
        """
        システム正常終了
        
        Returns:
            bool: 終了処理成功可否
            
        Claude Code実装時の注意：
        - 実行中のジョブ完了待ち
        - リソースの適切な解放
        - 状態の永続化
        """
        pass


class HealthCheckPort(ABC):
    """
    ヘルスチェック・監視インターフェース
    
    役割：
    - システム全体の健全性監視
    - パフォーマンス測定
    - アラート・通知
    
    Claude Code実装ガイダンス：
    - 各コンポーネントの個別監視
    - レスポンス時間・スループット測定
    - 異常検知とアラート機能
    """
    
    @abstractmethod
    async def check_system_health(self) -> Dict[str, Any]:
        """
        システム全体ヘルスチェック
        
        Returns:
            Dict: {
                'overall_status': ServiceStatus,
                'components': {
                    'database': {'status': 'healthy', 'response_time_ms': 10},
                    'vector_search': {'status': 'healthy', 'response_time_ms': 50},
                    'google_drive': {'status': 'degraded', 'error': 'Rate limit'},
                    ...
                },
                'timestamp': '2025-07-03T10:00:00Z'
            }
            
        Claude Code実装例：
        ```python
        async def check_system_health(self):
            components = {}
            overall_healthy = True
            
            # データベースチェック
            try:
                start_time = time.time()
                # 簡単なクエリ実行
                result = await self._test_database_connection()
                response_time = (time.time() - start_time) * 1000
                components['database'] = {
                    'status': ServiceStatus.HEALTHY.value,
                    'response_time_ms': round(response_time, 2)
                }
            except Exception as e:
                components['database'] = {
                    'status': ServiceStatus.UNHEALTHY.value,
                    'error': str(e)
                }
                overall_healthy = False
            
            # 各サービスも同様にチェック...
            
            return {
                'overall_status': ServiceStatus.HEALTHY.value if overall_healthy else ServiceStatus.UNHEALTHY.value,
                'components': components,
                'timestamp': datetime.now().isoformat()
            }
        ```
        """
        pass
    
    @abstractmethod
    async def measure_performance(
        self,
        operation: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        パフォーマンス測定
        
        Args:
            operation: 'search', 'ingest', 'analyze'
            params: 操作固有パラメータ
            
        Returns:
            Dict: {
                'operation': 'search',
                'response_time_ms': 150,
                'throughput': 100,  # ops/sec
                'success_rate': 0.95,
                'error_count': 2
            }
        """
        pass
    
    @abstractmethod
    async def get_system_metrics(
        self,
        time_range: Optional[Tuple[datetime, datetime]] = None
    ) -> Dict[str, Any]:
        """
        システムメトリクス取得
        
        Args:
            time_range: 取得期間（開始、終了）
            
        Returns:
            Dict: メトリクス情報
        """
        pass
    
    @abstractmethod
    async def create_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = 'warning',
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        アラート作成
        
        Args:
            alert_type: 'performance', 'error', 'security'
            message: アラートメッセージ
            severity: 'info', 'warning', 'error', 'critical'
            metadata: 追加情報
            
        Returns:
            str: アラートID
        """
        pass


# ========================================
# Implementation Helper Classes
# ========================================

class ServiceRegistry:
    """
    サービス統合管理クラス
    
    Claude Code実装ガイダンス：
    - 全サービスポートの統合管理
    - 設定に基づく機能制御
    - エラー処理とフォールバック
    """
    
    def __init__(self, config: PaaSConfig):
        self.config = config
        self.document_service: Optional[DocumentServicePort] = None
        self.orchestration_service: Optional[PaaSOrchestrationPort] = None
        self.health_service: Optional[HealthCheckPort] = None
        
        # 既存システム統合
        self.existing_system = None
        self._initialized = False
    
    async def initialize(self) -> bool:
        """
        サービスレジストリ初期化
        
        Claude Code実装時の注意：
        - 既存システム初期化を最優先
        - 新機能は段階的初期化
        - エラー時のロールバック処理
        """
        try:
            # 既存システム初期化（必須）
            from ..ui.interface import UserInterface
            self.existing_system = UserInterface()
            
            # 各サービス初期化
            if self.orchestration_service:
                await self.orchestration_service.initialize_system(self.config)
            
            self._initialized = True
            return True
        except Exception as e:
            raise PaaSError(f"Service registry initialization failed: {e}")
    
    def register_document_service(self, service: DocumentServicePort):
        """文書サービス登録"""
        self.document_service = service
    
    def register_orchestration_service(self, service: PaaSOrchestrationPort):
        """オーケストレーションサービス登録"""
        self.orchestration_service = service
    
    def register_health_service(self, service: HealthCheckPort):
        """ヘルスチェックサービス登録"""
        self.health_service = service
    
    async def get_unified_interface(self):
        """
        統一インターフェース取得
        
        Returns:
            統合されたサービスインターフェース
            
        Claude Code実装時の注意：
        - 既存システムとの完全互換性
        - 新機能の透過的統合
        - エラー時のフォールバック
        """
        if not self._initialized:
            await self.initialize()
        
        return UnifiedPaaSInterface(
            document_service=self.document_service,
            existing_system=self.existing_system,
            config=self.config
        )


class UnifiedPaaSInterface:
    """
    統一PaaSインターフェース
    
    既存システムと新機能を統合した単一インターフェース
    FastAPI エンドポイントから利用される
    """
    
    def __init__(
        self,
        document_service: Optional[DocumentServicePort],
        existing_system,
        config: PaaSConfig
    ):
        self.document_service = document_service
        self.existing_system = existing_system
        self.config = config
    
    async def search_documents(
        self,
        query: str,
        category: Optional[str] = None,
        search_mode: str = 'keyword',
        user_context: Optional[UserContext] = None
    ) -> List[Dict[str, Any]]:
        """
        統合文書検索
        
        Claude Code実装時の注意：
        - 既存検索との完全互換性
        - 新しい検索モードの透過的追加
        - 結果形式の統一
        """
        try:
            if self.document_service and search_mode != 'keyword':
                # 新しい検索機能使用
                search_mode_enum = SearchMode(search_mode)
                results = await self.document_service.search_documents(
                    query, search_mode_enum, category, user_context=user_context
                )
                return [result.to_existing_format() for result in results]
            else:
                # 既存検索機能使用
                return self.existing_system.search_documents(query, category)
        except Exception:
            # フォールバック：既存検索
            return self.existing_system.search_documents(query, category)
    
    async def ingest_documents(
        self,
        source_type: str = 'local_scan',
        source_config: Optional[Dict[str, Any]] = None,
        user_context: Optional[UserContext] = None
    ) -> Dict[str, Any]:
        """
        統合文書取り込み
        """
        if self.document_service and source_type != 'local_scan':
            # 新機能使用
            result = await self.document_service.ingest_documents(
                source_type, source_config or {}, user_context
            )
            return {
                'job_id': result.job_id,
                'status': result.status.value,
                'processed_files': result.processed_files,
                'total_files': result.total_files
            }
        else:
            # 既存機能使用
            self.existing_system.update_index()
            return {
                'job_id': f"local_scan_{datetime.now().isoformat()}",
                'status': 'completed',
                'message': 'Local scan completed'
            }
    
    async def get_statistics(
        self,
        user_context: Optional[UserContext] = None
    ) -> Dict[str, Any]:
        """統合統計情報取得"""
        if self.document_service:
            stats = await self.document_service.get_system_statistics(user_context)
            return stats.to_existing_format()
        else:
            # 既存統計使用
            return self.existing_system.get_system_statistics()


# ========================================
# Utility Functions for Claude Code
# ========================================

async def create_paas_system(config: PaaSConfig) -> UnifiedPaaSInterface:
    """
    PaaSシステム作成ヘルパー
    
    Claude Code実装時の使用例：
    ```python
    config = PaaSConfig(
        environment='development',
        enable_google_drive=True,
        enable_vector_search=True,
        enable_authentication=False
    )
    
    paas_system = await create_paas_system(config)
    results = await paas_system.search_documents("機械学習")
    ```
    """
    registry = ServiceRegistry(config)
    
    # 各サービスの実装を作成・登録
    # (具体的な実装は各ポートの実装クラスで行う)
    
    await registry.initialize()
    return await registry.get_unified_interface()


def create_backward_compatible_wrapper(existing_system):
    """
    既存システムの後方互換ラッパー作成
    
    Claude Code実装時の注意：
    - 既存メソッドの完全互換性維持
    - 新機能への段階的移行支援
    """
    class BackwardCompatibleWrapper:
        def __init__(self, existing_system):
            self.existing_system = existing_system
        
        def __getattr__(self, name):
            """既存メソッドへの透過的転送"""
            return getattr(self.existing_system, name)
    
    return BackwardCompatibleWrapper(existing_system)