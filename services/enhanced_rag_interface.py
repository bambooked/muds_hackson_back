"""
Enhanced RAG Interface - 新機能統合版

このモジュールは既存のRAGInterfaceを拡張し、新機能との透過的統合を提供します。
既存システムとの完全互換性を保ちながら、段階的に新機能を追加します。

Claude Code実装方針：
- 既存RAGInterfaceは絶対に変更しない
- 新機能はすべてOptionalで追加
- エラー時は既存システムで継続
- 設定による機能のON/OFF制御

Instance D実装担当：
- 既存システムとの橋渡し強化
- PaaS設定統合
- 新機能の透過的統合
- フォールバック機能実装
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from pathlib import Path

# 既存システムのインポート
from rag_interface import (
    RAGInterface, 
    DocumentMetadata as LegacyDocumentMetadata,
    SearchResult as LegacySearchResult,
    IngestionResult as LegacyIngestionResult,
    SystemStats as LegacySystemStats
)

# 新機能のインポート
from agent.source.interfaces.data_models import (
    PaaSConfig, 
    DocumentMetadata, 
    SearchResult, 
    IngestionResult, 
    SystemStats,
    UserContext,
    PaaSError,
    create_document_metadata_from_existing,
    create_search_result_from_existing
)
from agent.source.interfaces.config_manager import get_config_manager
from agent.source.interfaces.paas_orchestration_impl import create_paas_orchestration


class EnhancedRAGInterface:
    """
    拡張RAGインターフェース
    
    既存RAGInterfaceを内包し、新機能との統合を提供します。
    FastAPI エンドポイントからはこのクラスを使用し、
    既存機能が使いたい場合は内包されたlegacy_ragを直接利用可能。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        拡張RAGインターフェース初期化
        
        Args:
            config: 追加設定（既存システムの設定とマージ）
        """
        self._logger = logging.getLogger(__name__)
        
        # 既存システムの初期化（最優先）
        try:
            self.legacy_rag = RAGInterface(config)
            self._logger.info("既存RAGInterface初期化成功")
        except Exception as e:
            self._logger.error(f"既存RAGInterface初期化失敗: {e}")
            raise PaaSError(f"Critical: Legacy RAG system initialization failed: {e}")
        
        # PaaS設定管理
        self._config_manager = get_config_manager()
        self._paas_config: Optional[PaaSConfig] = None
        
        # オーケストレーション機能
        self._orchestration = None
        self._orchestration_initialized = False
        
        # 新機能サービス
        self._google_drive_service = None
        self._vector_search_service = None
        self._auth_service = None
        
        # パフォーマンス追跡
        self._request_count = 0
        self._error_count = 0
        self._last_activity = datetime.now()
    
    async def initialize_enhanced_features(self) -> Dict[str, Any]:
        """
        拡張機能の初期化
        
        Returns:
            Dict: 初期化結果
        """
        try:
            self._logger.info("拡張機能初期化開始")
            
            # PaaS設定読み込み
            self._paas_config = self._config_manager.load_config()
            
            # オーケストレーション初期化
            if not self._orchestration_initialized:
                self._orchestration = create_paas_orchestration()
                await self._orchestration.initialize_system(self._paas_config)
                self._orchestration_initialized = True
            
            # 各機能の条件付き初期化
            initialization_result = {
                'existing_system': True,  # 既に初期化済み
                'google_drive': await self._initialize_google_drive(),
                'vector_search': await self._initialize_vector_search(),
                'authentication': await self._initialize_authentication()
            }
            
            self._logger.info(f"拡張機能初期化完了: {initialization_result}")
            return initialization_result
            
        except Exception as e:
            self._logger.error(f"拡張機能初期化失敗: {e}")
            return {
                'error': str(e),
                'existing_system': True,  # 既存システムは動作継続
                'enhanced_features': False
            }
    
    async def _initialize_google_drive(self) -> bool:
        """Google Drive機能初期化"""
        if not self._paas_config.enable_google_drive:
            return False
        
        try:
            # TODO: Google Drive サービス初期化
            # Instance A の実装完了後に統合
            self._logger.info("Google Drive機能は待機中（Instance A実装待ち）")
            return False
        except Exception as e:
            self._logger.warning(f"Google Drive初期化失敗: {e}")
            return False
    
    async def _initialize_vector_search(self) -> bool:
        """ベクトル検索機能初期化"""
        if not self._paas_config.enable_vector_search:
            return False
        
        try:
            # TODO: ベクトル検索サービス初期化
            # Instance B の実装完了後に統合
            self._logger.info("ベクトル検索機能は待機中（Instance B実装待ち）")
            return False
        except Exception as e:
            self._logger.warning(f"ベクトル検索初期化失敗: {e}")
            return False
    
    async def _initialize_authentication(self) -> bool:
        """認証機能初期化"""
        if not self._paas_config.enable_authentication:
            return False
        
        try:
            # TODO: 認証サービス初期化
            # Instance C の実装完了後に統合
            self._logger.info("認証機能は待機中（Instance C実装待ち）")
            return False
        except Exception as e:
            self._logger.warning(f"認証初期化失敗: {e}")
            return False
    
    # ========================================
    # Enhanced Document Operations
    # ========================================
    
    async def ingest_documents(
        self,
        source_type: str = 'local_scan',
        source_config: Optional[Dict[str, Any]] = None,
        user_context: Optional[UserContext] = None
    ) -> IngestionResult:
        """
        統合文書取り込み
        
        Args:
            source_type: 'local_scan', 'google_drive', 'upload'
            source_config: ソース固有設定
            user_context: ユーザーコンテキスト
            
        Returns:
            IngestionResult: 取り込み結果
        """
        start_time = datetime.now()
        self._request_count += 1
        self._last_activity = start_time
        
        try:
            self._logger.info(f"文書取り込み開始: {source_type}")
            
            # 権限チェック（認証有効時のみ）
            if self._paas_config and self._paas_config.enable_authentication and user_context:
                if not user_context.has_permission('documents', 'write'):
                    raise PaaSError("Permission denied: document write access required")
            
            # ソース別処理
            if source_type == 'local_scan':
                # 既存システムでのローカルスキャン
                return await self._ingest_local_documents(source_config)
            
            elif source_type == 'google_drive' and self._google_drive_service:
                # Google Drive取り込み（Instance A実装後）
                return await self._ingest_google_drive_documents(source_config, user_context)
            
            elif source_type == 'upload':
                # アップロード取り込み
                return await self._ingest_uploaded_documents(source_config, user_context)
            
            else:
                # フォールバック：既存システム使用
                self._logger.warning(f"未サポートソース {source_type}、既存システムで処理")
                return await self._ingest_local_documents(source_config)
                
        except Exception as e:
            self._error_count += 1
            self._logger.error(f"文書取り込み失敗: {e}")
            
            # フォールバック：既存システムで処理
            try:
                return await self._ingest_local_documents(source_config)
            except Exception as fallback_error:
                return IngestionResult(
                    job_id=f"failed_{int(time.time())}",
                    status='failed',
                    total_files=0,
                    processed_files=0,
                    successful_files=0,
                    failed_files=0,
                    start_time=start_time,
                    end_time=datetime.now(),
                    errors=[str(e), str(fallback_error)]
                )
    
    async def _ingest_local_documents(self, source_config: Optional[Dict[str, Any]]) -> IngestionResult:
        """既存システムでのローカル文書取り込み"""
        try:
            start_time = datetime.now()
            
            # 既存システムの取り込み実行
            legacy_result = self.legacy_rag.ingest_documents()
            
            # 結果を新形式に変換
            return IngestionResult(
                job_id=f"local_scan_{int(time.time())}",
                status='completed' if legacy_result.success else 'failed',
                total_files=legacy_result.processed_files + legacy_result.failed_files,
                processed_files=legacy_result.processed_files + legacy_result.failed_files,
                successful_files=legacy_result.processed_files,
                failed_files=legacy_result.failed_files,
                start_time=start_time,
                end_time=datetime.now(),
                errors=[legacy_result.message] if not legacy_result.success else []
            )
            
        except Exception as e:
            raise PaaSError(f"Local document ingestion failed: {e}")
    
    async def _ingest_google_drive_documents(
        self, 
        source_config: Optional[Dict[str, Any]], 
        user_context: Optional[UserContext]
    ) -> IngestionResult:
        """Google Drive文書取り込み（Instance A実装後）"""
        # TODO: Instance A の GoogleDriveInputPort と統合
        raise PaaSError("Google Drive ingestion not yet implemented (waiting for Instance A)")
    
    async def _ingest_uploaded_documents(
        self, 
        source_config: Optional[Dict[str, Any]], 
        user_context: Optional[UserContext]
    ) -> IngestionResult:
        """アップロードファイル取り込み"""
        # TODO: ファイルアップロード機能の実装
        raise PaaSError("File upload ingestion not yet implemented")
    
    async def search_documents(
        self,
        query: str,
        search_mode: str = 'keyword',
        category: Optional[str] = None,
        limit: int = 10,
        user_context: Optional[UserContext] = None
    ) -> List[SearchResult]:
        """
        統合文書検索
        
        Args:
            query: 検索クエリ
            search_mode: 'keyword', 'semantic', 'hybrid'
            category: カテゴリ絞り込み
            limit: 結果制限数
            user_context: ユーザーコンテキスト
            
        Returns:
            List[SearchResult]: 検索結果
        """
        start_time = datetime.now()
        self._request_count += 1
        self._last_activity = start_time
        
        try:
            self._logger.info(f"文書検索開始: {query} (mode={search_mode})")
            
            # 権限チェック（認証有効時のみ）
            if self._paas_config and self._paas_config.enable_authentication and user_context:
                if not user_context.has_permission('documents', 'read'):
                    raise PaaSError("Permission denied: document read access required")
            
            # 検索モード別処理
            if search_mode == 'semantic' and self._vector_search_service:
                # セマンティック検索（Instance B実装後）
                return await self._search_semantic(query, category, limit, user_context)
            
            elif search_mode == 'hybrid' and self._vector_search_service:
                # ハイブリッド検索（Instance B実装後）
                return await self._search_hybrid(query, category, limit, user_context)
            
            else:
                # キーワード検索（既存システム使用）
                return await self._search_keyword(query, category, limit, user_context)
                
        except Exception as e:
            self._error_count += 1
            self._logger.error(f"文書検索失敗: {e}")
            
            # フォールバック：既存システムでキーワード検索
            try:
                return await self._search_keyword(query, category, limit, user_context)
            except Exception as fallback_error:
                self._logger.error(f"フォールバック検索も失敗: {fallback_error}")
                return []
    
    async def _search_keyword(
        self, 
        query: str, 
        category: Optional[str], 
        limit: int,
        user_context: Optional[UserContext]
    ) -> List[SearchResult]:
        """キーワード検索（既存システム使用）"""
        try:
            # 既存システムでの検索実行
            legacy_result = self.legacy_rag.search_documents(query, limit, category)
            
            # 結果を新形式に変換
            results = []
            for doc in legacy_result.documents:
                # 権限フィルタリング（認証有効時のみ）
                if self._should_include_document(doc, user_context):
                    search_result = SearchResult(
                        document=self._convert_legacy_metadata(doc),
                        score=1.0,  # キーワード検索は固定スコア
                        relevance_type='keyword',
                        highlighted_content=None  # TODO: ハイライト機能
                    )
                    results.append(search_result)
            
            return results[:limit]
            
        except Exception as e:
            raise PaaSError(f"Keyword search failed: {e}")
    
    async def _search_semantic(
        self, 
        query: str, 
        category: Optional[str], 
        limit: int,
        user_context: Optional[UserContext]
    ) -> List[SearchResult]:
        """セマンティック検索（Instance B実装後）"""
        # TODO: Instance B の VectorSearchPort と統合
        self._logger.warning("セマンティック検索は未実装、キーワード検索で代替")
        return await self._search_keyword(query, category, limit, user_context)
    
    async def _search_hybrid(
        self, 
        query: str, 
        category: Optional[str], 
        limit: int,
        user_context: Optional[UserContext]
    ) -> List[SearchResult]:
        """ハイブリッド検索（Instance B実装後）"""
        # TODO: Instance B の HybridSearchPort と統合
        self._logger.warning("ハイブリッド検索は未実装、キーワード検索で代替")
        return await self._search_keyword(query, category, limit, user_context)
    
    def _should_include_document(
        self, 
        document: LegacyDocumentMetadata, 
        user_context: Optional[UserContext]
    ) -> bool:
        """文書を結果に含めるべきかの権限チェック"""
        if not self._paas_config or not self._paas_config.enable_authentication or not user_context:
            return True  # 認証無効時は全て表示
        
        # TODO: 文書レベルの権限制御
        # 現在は基本的な読み取り権限のみチェック
        return user_context.has_permission('documents', 'read')
    
    def _convert_legacy_metadata(self, legacy_doc: LegacyDocumentMetadata) -> DocumentMetadata:
        """既存メタデータを新形式に変換"""
        return DocumentMetadata(
            id=legacy_doc.id,
            category=legacy_doc.category,
            file_path=legacy_doc.file_path,
            file_name=legacy_doc.title or f"document_{legacy_doc.id}",
            file_size=legacy_doc.file_size,
            created_at=legacy_doc.created_at or datetime.now(),
            updated_at=datetime.now(),
            title=legacy_doc.title,
            summary=legacy_doc.summary,
            authors=legacy_doc.authors,
            keywords=', '.join(legacy_doc.keywords) if legacy_doc.keywords else None
        )
    
    # ========================================
    # System Operations
    # ========================================
    
    async def get_system_statistics(
        self, 
        user_context: Optional[UserContext] = None
    ) -> SystemStats:
        """
        拡張システム統計取得
        
        Args:
            user_context: ユーザーコンテキスト
            
        Returns:
            SystemStats: 拡張統計情報
        """
        try:
            # 既存システムの統計取得
            legacy_stats = self.legacy_rag.get_system_stats()
            
            # 拡張統計情報を追加
            enhanced_stats = SystemStats(
                total_documents=legacy_stats.total_documents,
                documents_by_category=legacy_stats.documents_by_category,
                analysis_completion_rate={
                    'overall': legacy_stats.analysis_completion_rate
                },
                total_storage_size=int(legacy_stats.storage_size_mb * 1024 * 1024),
                last_updated=legacy_stats.last_update
            )
            
            # 新機能の統計を追加
            if self._paas_config:
                enhanced_stats.vector_index_size = None  # TODO: Instance B実装後
                enhanced_stats.active_users = 1 if user_context else 0
                enhanced_stats.search_query_count = self._request_count
                enhanced_stats.google_drive_sync_status = 'disabled' if not self._paas_config.enable_google_drive else 'pending'
            
            return enhanced_stats
            
        except Exception as e:
            self._logger.error(f"統計取得失敗: {e}")
            # フォールバック統計
            return SystemStats(
                total_documents=0,
                documents_by_category={},
                analysis_completion_rate={},
                total_storage_size=0
            )
    
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
        try:
            # 権限チェック
            if self._paas_config and self._paas_config.enable_authentication and user_context:
                if not user_context.has_permission('documents', 'read'):
                    raise PaaSError("Permission denied: document read access required")
            
            # 既存システムから取得
            legacy_doc = self.legacy_rag.get_document_detail(document_id, category)
            if legacy_doc:
                return self._convert_legacy_metadata(legacy_doc)
            return None
            
        except Exception as e:
            self._logger.error(f"文書詳細取得失敗: {e}")
            return None
    
    # ========================================
    # Backward Compatibility
    # ========================================
    
    def get_legacy_interface(self) -> RAGInterface:
        """既存インターフェースへの直接アクセス"""
        return self.legacy_rag
    
    async def migrate_to_enhanced_features(self) -> Dict[str, Any]:
        """既存データの新機能移行"""
        if not self._orchestration:
            return {'error': 'Orchestration not initialized'}
        
        try:
            # ベクトル化移行（Instance B実装後）
            vector_result = await self._orchestration.migrate_existing_data('vector_indexing', dry_run=False)
            
            # メタデータ更新
            metadata_result = await self._orchestration.migrate_existing_data('metadata_update', dry_run=False)
            
            return {
                'vector_indexing': vector_result,
                'metadata_update': metadata_result,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def get_enhanced_status(self) -> Dict[str, Any]:
        """拡張機能ステータス取得"""
        return {
            'enhanced_features_available': bool(self._orchestration_initialized),
            'config_loaded': bool(self._paas_config),
            'google_drive_enabled': bool(self._paas_config and self._paas_config.enable_google_drive),
            'vector_search_enabled': bool(self._paas_config and self._paas_config.enable_vector_search),
            'authentication_enabled': bool(self._paas_config and self._paas_config.enable_authentication),
            'request_count': self._request_count,
            'error_count': self._error_count,
            'last_activity': self._last_activity.isoformat()
        }


# ========================================
# Factory Functions
# ========================================

async def create_enhanced_rag_interface(config: Optional[Dict[str, Any]] = None) -> EnhancedRAGInterface:
    """
    拡張RAGインターフェースの作成・初期化
    
    Args:
        config: 追加設定
        
    Returns:
        EnhancedRAGInterface: 初期化済みインスタンス
    """
    interface = EnhancedRAGInterface(config)
    await interface.initialize_enhanced_features()
    return interface


def create_backward_compatible_interface(config: Optional[Dict[str, Any]] = None) -> RAGInterface:
    """
    既存システムとの完全互換インターフェース作成
    
    Args:
        config: 設定
        
    Returns:
        RAGInterface: 既存互換インスタンス
    """
    return RAGInterface(config)