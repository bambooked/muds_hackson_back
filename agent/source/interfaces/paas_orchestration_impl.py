"""
PaaSOrchestrationPort具体実装

このモジュールはPaaSシステム全体のオーケストレーション機能を提供します。
既存システムとの完全互換性を保ちながら、新機能の段階的統合を実現します。

Claude Code実装方針：
- 既存システムは絶対に変更しない
- 新機能はすべてOptionalで追加
- エラー時は既存システムで継続
- 設定による機能のON/OFF制御

Instance D実装担当：
- PaaSOrchestrationPort: システム統合オーケストレーション
- 設定管理との統合
- サービス間連携制御
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from .service_ports import (
    PaaSOrchestrationPort,
    ServiceStatus,
    FeatureToggle,
    DocumentServicePort,
    HealthCheckPort
)
from .data_models import PaaSConfig, PaaSError, UserContext
from .config_manager import get_config_manager, PaaSConfigManager


class PaaSOrchestrationImpl(PaaSOrchestrationPort):
    """
    PaaSシステム統合オーケストレーション実装
    
    役割：
    - 全サービスの統合管理
    - 機能の有効/無効制御
    - システム全体の初期化・終了処理
    - 既存システムとの橋渡し
    """
    
    def __init__(self):
        """初期化"""
        self._logger = logging.getLogger(__name__)
        self._config_manager: PaaSConfigManager = get_config_manager()
        self._services: Dict[str, Any] = {}
        self._feature_status: Dict[FeatureToggle, bool] = {}
        self._existing_system = None
        self._initialized = False
        
        # サービス登録用レジストリ
        self._document_service: Optional[DocumentServicePort] = None
        self._health_service: Optional[HealthCheckPort] = None
        
        # 初期化状態追跡
        self._initialization_time: Optional[datetime] = None
        self._initialization_errors: List[str] = []
    
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
        """
        self._logger.info("PaaSシステム初期化開始")
        start_time = time.time()
        status = {}
        
        try:
            # 既存システム初期化（最優先・必須）
            await self._initialize_existing_system(status)
            
            # 新機能の段階的初期化
            await self._initialize_optional_features(config, status)
            
            # 初期化完了記録
            self._initialized = True
            self._initialization_time = datetime.now()
            
            elapsed_time = time.time() - start_time
            self._logger.info(f"PaaSシステム初期化完了 ({elapsed_time:.2f}秒)")
            
            return status
            
        except Exception as e:
            self._logger.error(f"PaaSシステム初期化失敗: {e}")
            self._initialization_errors.append(str(e))
            raise PaaSError(f"System initialization failed: {e}")
    
    async def _initialize_existing_system(self, status: Dict[str, ServiceStatus]):
        """既存システム初期化（必須）"""
        try:
            self._logger.info("既存システム初期化中...")
            
            # 既存UserInterfaceの初期化
            from ..ui.interface import UserInterface
            self._existing_system = UserInterface()
            
            # 基本動作確認（正確なAPI使用）
            datasets = self._existing_system.dataset_repo.find_all()
            papers = self._existing_system.paper_repo.find_all()
            posters = self._existing_system.poster_repo.find_all()
            total_docs = len(datasets) + len(papers) + len(posters)
            
            status['existing_system'] = ServiceStatus.HEALTHY
            self._logger.info(f"既存システム初期化成功: {total_docs}件の文書")
                
        except Exception as e:
            status['existing_system'] = ServiceStatus.UNHEALTHY
            self._logger.error(f"既存システム初期化失敗: {e}")
            raise PaaSError(f"Critical: Existing system initialization failed: {e}")
    
    async def _initialize_optional_features(self, config: PaaSConfig, status: Dict[str, ServiceStatus]):
        """新機能の段階的初期化"""
        
        # Google Drive機能初期化（オプション）
        if config.enable_google_drive:
            await self._initialize_google_drive(config, status)
        else:
            status['google_drive'] = ServiceStatus.UNKNOWN
            self._feature_status[FeatureToggle.GOOGLE_DRIVE] = False
        
        # ベクトル検索機能初期化（オプション）
        if config.enable_vector_search:
            await self._initialize_vector_search(config, status)
        else:
            status['vector_search'] = ServiceStatus.UNKNOWN
            self._feature_status[FeatureToggle.VECTOR_SEARCH] = False
        
        # 認証機能初期化（オプション）
        if config.enable_authentication:
            await self._initialize_authentication(config, status)
        else:
            status['authentication'] = ServiceStatus.UNKNOWN
            self._feature_status[FeatureToggle.AUTHENTICATION] = False
        
        # 監視機能初期化（オプション）
        if config.enable_monitoring:
            await self._initialize_monitoring(config, status)
        else:
            status['monitoring'] = ServiceStatus.UNKNOWN
            self._feature_status[FeatureToggle.MONITORING] = False
    
    async def _initialize_google_drive(self, config: PaaSConfig, status: Dict[str, ServiceStatus]):
        """Google Drive機能初期化"""
        try:
            self._logger.info("Google Drive機能初期化中...")
            
            # Google Drive設定確認
            if not config.google_drive or not config.google_drive.credentials_path:
                status['google_drive'] = ServiceStatus.DEGRADED
                self._feature_status[FeatureToggle.GOOGLE_DRIVE] = False
                self._logger.warning("Google Drive設定不完全")
                return
            
            # 認証ファイル存在確認
            creds_path = Path(config.google_drive.credentials_path)
            if not creds_path.exists():
                status['google_drive'] = ServiceStatus.UNHEALTHY
                self._feature_status[FeatureToggle.GOOGLE_DRIVE] = False
                self._logger.error(f"Google Drive認証ファイル未発見: {creds_path}")
                return
            
            # TODO: 実際のGoogle Drive API接続テスト
            # 現在は設定確認のみ
            status['google_drive'] = ServiceStatus.HEALTHY
            self._feature_status[FeatureToggle.GOOGLE_DRIVE] = True
            self._logger.info("Google Drive機能初期化成功")
            
        except Exception as e:
            status['google_drive'] = ServiceStatus.UNHEALTHY
            self._feature_status[FeatureToggle.GOOGLE_DRIVE] = False
            self._logger.error(f"Google Drive初期化失敗: {e}")
    
    async def _initialize_vector_search(self, config: PaaSConfig, status: Dict[str, ServiceStatus]):
        """ベクトル検索機能初期化"""
        try:
            self._logger.info("ベクトル検索機能初期化中...")
            
            # ベクトル検索設定確認
            if not config.vector_search:
                status['vector_search'] = ServiceStatus.DEGRADED
                self._feature_status[FeatureToggle.VECTOR_SEARCH] = False
                self._logger.warning("ベクトル検索設定不完全")
                return
            
            # プロバイダー確認
            if config.vector_search.provider not in ['chroma', 'qdrant', 'pinecone']:
                status['vector_search'] = ServiceStatus.UNHEALTHY
                self._feature_status[FeatureToggle.VECTOR_SEARCH] = False
                self._logger.error(f"未サポートのベクトル検索プロバイダー: {config.vector_search.provider}")
                return
            
            # TODO: 実際のベクトル検索サービス接続テスト
            # 現在は設定確認のみ
            status['vector_search'] = ServiceStatus.HEALTHY
            self._feature_status[FeatureToggle.VECTOR_SEARCH] = True
            self._logger.info("ベクトル検索機能初期化成功")
            
        except Exception as e:
            status['vector_search'] = ServiceStatus.UNHEALTHY
            self._feature_status[FeatureToggle.VECTOR_SEARCH] = False
            self._logger.error(f"ベクトル検索初期化失敗: {e}")
    
    async def _initialize_authentication(self, config: PaaSConfig, status: Dict[str, ServiceStatus]):
        """認証機能初期化"""
        try:
            self._logger.info("認証機能初期化中...")
            
            # 認証設定確認
            if not config.auth or not config.auth.client_id or not config.auth.client_secret:
                status['authentication'] = ServiceStatus.DEGRADED
                self._feature_status[FeatureToggle.AUTHENTICATION] = False
                self._logger.warning("認証設定不完全")
                return
            
            # TODO: 実際のOAuth2接続テスト
            # 現在は設定確認のみ
            status['authentication'] = ServiceStatus.HEALTHY
            self._feature_status[FeatureToggle.AUTHENTICATION] = True
            self._logger.info("認証機能初期化成功")
            
        except Exception as e:
            status['authentication'] = ServiceStatus.UNHEALTHY
            self._feature_status[FeatureToggle.AUTHENTICATION] = False
            self._logger.error(f"認証初期化失敗: {e}")
    
    async def _initialize_monitoring(self, config: PaaSConfig, status: Dict[str, ServiceStatus]):
        """監視機能初期化"""
        try:
            self._logger.info("監視機能初期化中...")
            
            # TODO: 実際の監視システム初期化
            # 現在は基本初期化のみ
            status['monitoring'] = ServiceStatus.HEALTHY
            self._feature_status[FeatureToggle.MONITORING] = True
            self._logger.info("監視機能初期化成功")
            
        except Exception as e:
            status['monitoring'] = ServiceStatus.UNHEALTHY
            self._feature_status[FeatureToggle.MONITORING] = False
            self._logger.error(f"監視初期化失敗: {e}")
    
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
        try:
            self._logger.info(f"機能有効化: {feature.value}")
            
            if feature == FeatureToggle.GOOGLE_DRIVE:
                return await self._enable_google_drive(config)
            elif feature == FeatureToggle.VECTOR_SEARCH:
                return await self._enable_vector_search(config)
            elif feature == FeatureToggle.AUTHENTICATION:
                return await self._enable_authentication(config)
            elif feature == FeatureToggle.MONITORING:
                return await self._enable_monitoring(config)
            else:
                self._logger.warning(f"未知の機能: {feature}")
                return False
                
        except Exception as e:
            self._logger.error(f"機能有効化失敗 {feature.value}: {e}")
            return False
    
    async def _enable_google_drive(self, config: Optional[Dict[str, Any]]) -> bool:
        """Google Drive機能有効化"""
        # TODO: Google Drive機能の動的有効化
        self._feature_status[FeatureToggle.GOOGLE_DRIVE] = True
        return True
    
    async def _enable_vector_search(self, config: Optional[Dict[str, Any]]) -> bool:
        """ベクトル検索機能有効化"""
        # TODO: ベクトル検索機能の動的有効化
        self._feature_status[FeatureToggle.VECTOR_SEARCH] = True
        return True
    
    async def _enable_authentication(self, config: Optional[Dict[str, Any]]) -> bool:
        """認証機能有効化"""
        # TODO: 認証機能の動的有効化
        self._feature_status[FeatureToggle.AUTHENTICATION] = True
        return True
    
    async def _enable_monitoring(self, config: Optional[Dict[str, Any]]) -> bool:
        """監視機能有効化"""
        # TODO: 監視機能の動的有効化
        self._feature_status[FeatureToggle.MONITORING] = True
        return True
    
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
        try:
            self._logger.info(f"機能無効化: {feature.value}")
            
            # 機能を無効化（既存システムには影響しない）
            self._feature_status[feature] = False
            
            # TODO: 各機能の適切な無効化処理
            return True
            
        except Exception as e:
            self._logger.error(f"機能無効化失敗 {feature.value}: {e}")
            return False
    
    async def get_feature_status(self) -> Dict[FeatureToggle, bool]:
        """
        機能状態取得
        
        Returns:
            Dict[FeatureToggle, bool]: 機能別有効/無効状態
        """
        return self._feature_status.copy()
    
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
        """
        try:
            self._logger.info(f"データ移行開始: {migration_type} (dry_run={dry_run})")
            
            if migration_type == 'vector_indexing':
                return await self._migrate_vector_indexing(dry_run)
            elif migration_type == 'metadata_update':
                return await self._migrate_metadata_update(dry_run)
            else:
                return {
                    'error': f'Unsupported migration type: {migration_type}',
                    'supported_types': ['vector_indexing', 'metadata_update']
                }
                
        except Exception as e:
            self._logger.error(f"データ移行失敗: {e}")
            return {
                'error': str(e),
                'migration_type': migration_type,
                'dry_run': dry_run
            }
    
    async def _migrate_vector_indexing(self, dry_run: bool) -> Dict[str, Any]:
        """既存文書のベクトル化移行"""
        if not self._existing_system:
            return {'error': 'Existing system not initialized'}
        
        try:
            # 既存文書の取得
            datasets = self._existing_system.dataset_repo.find_all()
            papers = self._existing_system.paper_repo.find_all()
            posters = self._existing_system.poster_repo.find_all()
            total_docs = len(datasets) + len(papers) + len(posters)
            
            result = {
                'migration_type': 'vector_indexing',
                'total_documents': total_docs,
                'processed': 0,
                'errors': [],
                'dry_run': dry_run
            }
            
            if dry_run:
                result['message'] = f'Dry run: {total_docs}件の文書をベクトル化対象として検出'
            else:
                # TODO: 実際のベクトル化処理
                result['message'] = 'ベクトル化処理は未実装（他Instanceと連携後に実装予定）'
                result['processed'] = 0
            
            return result
            
        except Exception as e:
            return {
                'error': f'Vector indexing migration failed: {e}',
                'migration_type': 'vector_indexing',
                'dry_run': dry_run
            }
    
    async def _migrate_metadata_update(self, dry_run: bool) -> Dict[str, Any]:
        """既存メタデータの更新・拡張"""
        if not self._existing_system:
            return {'error': 'Existing system not initialized'}
        
        try:
            result = {
                'migration_type': 'metadata_update',
                'total_documents': 0,
                'processed': 0,
                'errors': [],
                'dry_run': dry_run
            }
            
            # TODO: メタデータ更新処理の実装
            result['message'] = 'メタデータ更新処理は未実装'
            
            return result
            
        except Exception as e:
            return {
                'error': f'Metadata update migration failed: {e}',
                'migration_type': 'metadata_update',
                'dry_run': dry_run
            }
    
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
        try:
            self._logger.info(f"システムバックアップ開始: {backup_type}")
            
            backup_id = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            result = {
                'backup_id': backup_id,
                'backup_type': backup_type,
                'timestamp': datetime.now().isoformat(),
                'success': False,
                'details': {}
            }
            
            if backup_type in ['full', 'config_only']:
                # 設定バックアップ
                config = self._config_manager.load_config()
                backup_path = Path(f"./backups/{backup_id}_config.json")
                backup_path.parent.mkdir(exist_ok=True)
                self._config_manager.save_config_to_file(str(backup_path))
                result['details']['config_backup'] = str(backup_path)
            
            if backup_type in ['full', 'metadata_only']:
                # TODO: データベースバックアップ
                result['details']['database_backup'] = 'Database backup not implemented'
            
            result['success'] = True
            self._logger.info(f"システムバックアップ完了: {backup_id}")
            return result
            
        except Exception as e:
            self._logger.error(f"システムバックアップ失敗: {e}")
            return {
                'error': str(e),
                'backup_type': backup_type,
                'success': False
            }
    
    async def shutdown_gracefully(self) -> bool:
        """
        システム正常終了
        
        Returns:
            bool: 終了処理成功可否
        """
        try:
            self._logger.info("PaaSシステム正常終了開始")
            
            # 実行中ジョブの完了待ち
            # TODO: 実際のジョブ管理システムとの連携
            
            # リソース解放
            self._services.clear()
            self._feature_status.clear()
            
            # 状態永続化
            if self._config_manager:
                self._config_manager.save_config_to_file("./last_session_config.json")
            
            self._initialized = False
            self._logger.info("PaaSシステム正常終了完了")
            return True
            
        except Exception as e:
            self._logger.error(f"システム終了処理エラー: {e}")
            return False
    
    # ========================================
    # Service Registry Integration
    # ========================================
    
    def register_document_service(self, service: DocumentServicePort):
        """文書サービス登録"""
        self._document_service = service
        self._services['document'] = service
    
    def register_health_service(self, service: HealthCheckPort):
        """ヘルスチェックサービス登録"""
        self._health_service = service
        self._services['health'] = service
    
    def get_existing_system(self):
        """既存システムへのアクセス"""
        return self._existing_system
    
    def is_initialized(self) -> bool:
        """初期化状態確認"""
        return self._initialized
    
    def get_initialization_time(self) -> Optional[datetime]:
        """初期化時刻取得"""
        return self._initialization_time
    
    def get_initialization_errors(self) -> List[str]:
        """初期化エラー一覧取得"""
        return self._initialization_errors.copy()


# ========================================
# Factory Functions
# ========================================

def create_paas_orchestration() -> PaaSOrchestrationImpl:
    """
    PaaSオーケストレーション実装の作成
    
    Returns:
        PaaSOrchestrationImpl: 実装インスタンス
    """
    return PaaSOrchestrationImpl()


async def initialize_paas_system() -> PaaSOrchestrationImpl:
    """
    PaaSシステムの完全初期化
    
    Returns:
        PaaSOrchestrationImpl: 初期化済みインスタンス
    """
    orchestration = create_paas_orchestration()
    config_manager = get_config_manager()
    config = config_manager.load_config()
    
    await orchestration.initialize_system(config)
    return orchestration