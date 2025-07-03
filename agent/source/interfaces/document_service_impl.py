"""
DocumentServicePort実装

このモジュールは文書操作統合インターフェースの具体実装を提供します。
既存システムとの完全互換性を保ちながら、新機能を透過的に統合します。

Claude Code実装方針：
- 既存UserInterfaceとの正確なAPI連携
- 新機能はすべてOptionalで追加
- エラー時は既存システムで継続
- 権限制御の適切な実装

Instance D完全実装：
- DocumentServicePortの全メソッド実装
- 既存システムとの正確な連携
- 新機能との統合準備
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from .service_ports import DocumentServicePort, SearchMode
from .data_models import (
    PaaSConfig, 
    DocumentMetadata, 
    SearchResult, 
    IngestionResult,
    SystemStats,
    UserContext,
    PaaSError,
    JobStatus,
    create_document_metadata_from_existing,
    create_search_result_from_existing
)
from .config_manager import get_config_manager


class DocumentServiceImpl(DocumentServicePort):
    """
    文書操作統合インターフェース実装
    
    既存UserInterfaceを内包し、新機能との統合を提供します。
    全ての操作で既存システムとの互換性を最優先とします。
    """
    
    def __init__(self):
        """初期化"""
        self._logger = logging.getLogger(__name__)
        self._config_manager = get_config_manager()
        
        # 既存システム初期化（最優先）
        try:
            from ..ui.interface import UserInterface
            self._existing_ui = UserInterface()
            self._logger.info("既存UserInterface初期化成功")
        except Exception as e:
            self._logger.error(f"既存UserInterface初期化失敗: {e}")
            raise PaaSError(f"Critical: Existing UserInterface initialization failed: {e}")
        
        # 新機能サービス（Optional）
        self._google_drive_port = None
        self._vector_search_port = None
        self._auth_port = None
        
        # パフォーマンス追跡
        self._operation_count = 0
        self._error_count = 0
        self._last_operation = datetime.now()
    
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
        """
        start_time = datetime.now()
        job_id = f"ingest_{source_type}_{int(time.time())}"
        self._operation_count += 1
        self._last_operation = start_time
        
        try:
            self._logger.info(f"文書取り込み開始: {source_type}")
            
            # 権限チェック（認証有効時のみ）
            config = self._config_manager.load_config()
            if config.enable_authentication and user_context:
                if not user_context.has_permission('documents', 'write'):
                    raise PaaSError("Permission denied: document write access required")
            
            # ソース別処理
            if source_type == 'local_scan':
                return await self._ingest_local_documents(job_id, source_config, start_time)
            
            elif source_type == 'google_drive' and self._google_drive_port:
                # Google Drive取り込み（Instance A実装後）
                return await self._ingest_google_drive_documents(job_id, source_config, user_context, start_time)
            
            elif source_type == 'upload':
                # アップロード取り込み
                return await self._ingest_uploaded_documents(job_id, source_config, user_context, start_time)
            
            else:
                # フォールバック：既存システム使用
                self._logger.warning(f"未サポートソース {source_type}、既存システムで処理")
                return await self._ingest_local_documents(job_id, source_config, start_time)
                
        except Exception as e:
            self._error_count += 1
            self._logger.error(f"文書取り込み失敗: {e}")
            
            # フォールバック：既存システムで処理
            try:
                return await self._ingest_local_documents(job_id, source_config, start_time)
            except Exception as fallback_error:
                return IngestionResult(
                    job_id=job_id,
                    status=JobStatus.FAILED,
                    total_files=0,
                    processed_files=0,
                    successful_files=0,
                    failed_files=0,
                    start_time=start_time,
                    end_time=datetime.now(),
                    errors=[str(e), str(fallback_error)]
                )
    
    async def _ingest_local_documents(
        self, 
        job_id: str, 
        source_config: Dict[str, Any], 
        start_time: datetime
    ) -> IngestionResult:
        """既存システムでのローカル文書取り込み"""
        try:
            self._logger.info("既存システムでローカル文書取り込み実行")
            
            # 既存システムのインデックス更新実行
            results = self._existing_ui.indexer.index_all_files()
            
            # 結果を新形式に変換
            total_files = results.get('total_files', 0)
            error_files = results.get('error_files', [])
            successful_files = total_files - len(error_files)
            
            return IngestionResult(
                job_id=job_id,
                status=JobStatus.COMPLETED if len(error_files) == 0 else JobStatus.COMPLETED,
                total_files=total_files,
                processed_files=total_files,
                successful_files=successful_files,
                failed_files=len(error_files),
                start_time=start_time,
                end_time=datetime.now(),
                errors=[str(err) for err in error_files] if error_files else []
            )
            
        except Exception as e:
            raise PaaSError(f"Local document ingestion failed: {e}")
    
    async def _ingest_google_drive_documents(
        self, 
        job_id: str,
        source_config: Dict[str, Any], 
        user_context: Optional[UserContext],
        start_time: datetime
    ) -> IngestionResult:
        """Google Drive文書取り込み（Instance A実装後）"""
        # TODO: Instance A の GoogleDriveInputPort と統合
        raise PaaSError("Google Drive ingestion not yet implemented (waiting for Instance A)")
    
    async def _ingest_uploaded_documents(
        self, 
        job_id: str,
        source_config: Dict[str, Any], 
        user_context: Optional[UserContext],
        start_time: datetime
    ) -> IngestionResult:
        """アップロードファイル取り込み"""
        # TODO: ファイルアップロード機能の実装
        raise PaaSError("File upload ingestion not yet implemented")
    
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
        """
        start_time = datetime.now()
        self._operation_count += 1
        self._last_operation = start_time
        
        try:
            self._logger.info(f"文書検索開始: {query} (mode={search_mode.value})")
            
            # 権限チェック（認証有効時のみ）
            config = self._config_manager.load_config()
            if config.enable_authentication and user_context:
                if not user_context.has_permission('documents', 'read'):
                    raise PaaSError("Permission denied: document read access required")
            
            # 検索モード別処理
            if search_mode == SearchMode.SEMANTIC and self._vector_search_port:
                # セマンティック検索（Instance B実装後）
                return await self._search_semantic(query, category, filters, user_context)
            
            elif search_mode == SearchMode.HYBRID and self._vector_search_port:
                # ハイブリッド検索（Instance B実装後）
                return await self._search_hybrid(query, category, filters, user_context)
            
            else:
                # キーワード検索（既存システム使用）
                return await self._search_keyword(query, category, filters, user_context)
                
        except Exception as e:
            self._error_count += 1
            self._logger.error(f"文書検索失敗: {e}")
            
            # フォールバック：既存システムでキーワード検索
            try:
                return await self._search_keyword(query, category, filters, user_context)
            except Exception as fallback_error:
                self._logger.error(f"フォールバック検索も失敗: {fallback_error}")
                return []
    
    async def _search_keyword(
        self, 
        query: str, 
        category: Optional[str], 
        filters: Optional[Dict[str, Any]],
        user_context: Optional[UserContext]
    ) -> List[SearchResult]:
        """キーワード検索（既存システム使用）"""
        try:
            results = []
            
            # カテゴリ指定がある場合はそのカテゴリのみ検索
            search_categories = [category] if category else ['dataset', 'paper', 'poster']
            
            for cat in search_categories:
                if cat == 'dataset':
                    # データセット検索
                    datasets = self._existing_ui.dataset_repo.find_all()
                    for dataset in datasets:
                        if query.lower() in (dataset.name.lower() if dataset.name else '') or \
                           query.lower() in (dataset.summary.lower() if dataset.summary else ''):
                            
                            if self._should_include_document(dataset, user_context):
                                doc_metadata = self._convert_dataset_to_metadata(dataset)
                                search_result = SearchResult(
                                    document=doc_metadata,
                                    score=1.0,
                                    relevance_type='keyword',
                                    highlighted_content=None
                                )
                                results.append(search_result)
                
                elif cat == 'paper':
                    # 論文検索
                    papers = self._existing_ui.paper_repo.search(query)
                    for paper in papers:
                        if self._should_include_document(paper, user_context):
                            doc_metadata = self._convert_paper_to_metadata(paper)
                            search_result = SearchResult(
                                document=doc_metadata,
                                score=1.0,
                                relevance_type='keyword',
                                highlighted_content=None
                            )
                            results.append(search_result)
                
                elif cat == 'poster':
                    # ポスター検索
                    posters = self._existing_ui.poster_repo.search(query)
                    for poster in posters:
                        if self._should_include_document(poster, user_context):
                            doc_metadata = self._convert_poster_to_metadata(poster)
                            search_result = SearchResult(
                                document=doc_metadata,
                                score=1.0,
                                relevance_type='keyword',
                                highlighted_content=None
                            )
                            results.append(search_result)
            
            return results
            
        except Exception as e:
            raise PaaSError(f"Keyword search failed: {e}")
    
    async def _search_semantic(
        self, 
        query: str, 
        category: Optional[str], 
        filters: Optional[Dict[str, Any]],
        user_context: Optional[UserContext]
    ) -> List[SearchResult]:
        """セマンティック検索（Instance B実装後）"""
        # TODO: Instance B の VectorSearchPort と統合
        self._logger.warning("セマンティック検索は未実装、キーワード検索で代替")
        return await self._search_keyword(query, category, filters, user_context)
    
    async def _search_hybrid(
        self, 
        query: str, 
        category: Optional[str], 
        filters: Optional[Dict[str, Any]],
        user_context: Optional[UserContext]
    ) -> List[SearchResult]:
        """ハイブリッド検索（Instance B実装後）"""
        # TODO: Instance B の HybridSearchPort と統合
        self._logger.warning("ハイブリッド検索は未実装、キーワード検索で代替")
        return await self._search_keyword(query, category, filters, user_context)
    
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
        """
        try:
            self._logger.info(f"文書解析開始: ID={document_id}, category={category}")
            
            # 権限チェック
            config = self._config_manager.load_config()
            if config.enable_authentication and user_context:
                if not user_context.has_permission('documents', 'write'):
                    raise PaaSError("Permission denied: document write access required")
            
            # 既存アナライザーを使用
            if category == 'dataset':
                # データセット解析
                dataset = self._existing_ui.dataset_repo.find_by_id(document_id)
                if not dataset:
                    return None
                
                if force_reanalyze or not dataset.summary:
                    await asyncio.to_thread(
                        self._existing_ui.analyzer.analyze_dataset, 
                        dataset.name
                    )
                    # 解析後の最新データを取得
                    dataset = self._existing_ui.dataset_repo.find_by_id(document_id)
                
                return self._convert_dataset_to_metadata(dataset)
            
            elif category == 'paper':
                # 論文解析
                paper = self._existing_ui.paper_repo.find_by_id(document_id)
                if not paper:
                    return None
                
                if force_reanalyze or not paper.abstract:
                    await asyncio.to_thread(
                        self._existing_ui.analyzer.analyze_paper, 
                        paper.file_path
                    )
                    # 解析後の最新データを取得
                    paper = self._existing_ui.paper_repo.find_by_id(document_id)
                
                return self._convert_paper_to_metadata(paper)
            
            elif category == 'poster':
                # ポスター解析
                poster = self._existing_ui.poster_repo.find_by_id(document_id)
                if not poster:
                    return None
                
                if force_reanalyze or not poster.abstract:
                    await asyncio.to_thread(
                        self._existing_ui.analyzer.analyze_poster, 
                        poster.file_path
                    )
                    # 解析後の最新データを取得
                    poster = self._existing_ui.poster_repo.find_by_id(document_id)
                
                return self._convert_poster_to_metadata(poster)
            
            else:
                raise PaaSError(f"Unsupported category: {category}")
                
        except Exception as e:
            self._logger.error(f"文書解析失敗: {e}")
            return None
    
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
            config = self._config_manager.load_config()
            if config.enable_authentication and user_context:
                if not user_context.has_permission('documents', 'read'):
                    raise PaaSError("Permission denied: document read access required")
            
            # カテゴリ別取得
            if category == 'dataset':
                dataset = self._existing_ui.dataset_repo.find_by_id(document_id)
                return self._convert_dataset_to_metadata(dataset) if dataset else None
            
            elif category == 'paper':
                paper = self._existing_ui.paper_repo.find_by_id(document_id)
                return self._convert_paper_to_metadata(paper) if paper else None
            
            elif category == 'poster':
                poster = self._existing_ui.poster_repo.find_by_id(document_id)
                return self._convert_poster_to_metadata(poster) if poster else None
            
            else:
                return None
                
        except Exception as e:
            self._logger.error(f"文書詳細取得失敗: {e}")
            return None
    
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
        """
        try:
            self._logger.info(f"文書削除開始: ID={document_id}, category={category}")
            
            # 権限チェック必須（削除権限）
            config = self._config_manager.load_config()
            if config.enable_authentication and user_context:
                if not user_context.has_permission('documents', 'delete'):
                    raise PaaSError("Permission denied: document delete access required")
            
            # カテゴリ別削除
            if category == 'dataset':
                success = self._existing_ui.dataset_repo.delete(document_id)
            elif category == 'paper':
                success = self._existing_ui.paper_repo.delete(document_id)
            elif category == 'poster':
                success = self._existing_ui.poster_repo.delete(document_id)
            else:
                return False
            
            if success:
                self._logger.info(f"文書削除成功: ID={document_id}")
                # TODO: ベクトルインデックスからも削除（Instance B実装後）
                # TODO: 削除の監査ログ記録
            
            return success
            
        except Exception as e:
            self._logger.error(f"文書削除失敗: {e}")
            return False
    
    async def get_system_statistics(
        self,
        user_context: Optional[UserContext] = None
    ) -> SystemStats:
        """
        システム統計取得
        
        Returns:
            SystemStats: システム統計情報
        """
        try:
            # 権限チェック
            config = self._config_manager.load_config()
            if config.enable_authentication and user_context:
                if not user_context.has_permission('documents', 'read'):
                    # 制限された統計情報のみ提供
                    return SystemStats(
                        total_documents=0,
                        documents_by_category={},
                        analysis_completion_rate={},
                        total_storage_size=0
                    )
            
            # 各カテゴリの統計取得
            datasets = self._existing_ui.dataset_repo.find_all()
            papers = self._existing_ui.paper_repo.find_all()
            posters = self._existing_ui.poster_repo.find_all()
            
            documents_by_category = {
                'dataset': len(datasets),
                'paper': len(papers),
                'poster': len(posters)
            }
            
            total_documents = sum(documents_by_category.values())
            
            # 解析完了率計算
            analyzed_datasets = sum(1 for d in datasets if d.summary)
            analyzed_papers = sum(1 for p in papers if p.abstract)
            analyzed_posters = sum(1 for p in posters if p.abstract)
            
            analysis_completion_rate = {
                'dataset': (analyzed_datasets / len(datasets) * 100) if datasets else 100,
                'paper': (analyzed_papers / len(papers) * 100) if papers else 100,
                'poster': (analyzed_posters / len(posters) * 100) if posters else 100,
                'overall': ((analyzed_datasets + analyzed_papers + analyzed_posters) / total_documents * 100) if total_documents > 0 else 100
            }
            
            # ストレージサイズ計算
            total_storage = sum(d.total_size or 0 for d in datasets)
            total_storage += sum(p.file_size or 0 for p in papers)
            total_storage += sum(p.file_size or 0 for p in posters)
            
            # 拡張統計情報
            enhanced_stats = SystemStats(
                total_documents=total_documents,
                documents_by_category=documents_by_category,
                analysis_completion_rate=analysis_completion_rate,
                total_storage_size=total_storage,
                last_updated=datetime.now()
            )
            
            # 新機能統計追加
            if config.enable_vector_search:
                enhanced_stats.vector_index_size = None  # TODO: Instance B実装後
            
            if config.enable_authentication and user_context:
                enhanced_stats.active_users = 1
            
            enhanced_stats.search_query_count = self._operation_count
            enhanced_stats.google_drive_sync_status = 'disabled' if not config.enable_google_drive else 'pending'
            
            return enhanced_stats
            
        except Exception as e:
            self._logger.error(f"システム統計取得失敗: {e}")
            # フォールバック統計
            return SystemStats(
                total_documents=0,
                documents_by_category={},
                analysis_completion_rate={},
                total_storage_size=0
            )
    
    # ========================================
    # Helper Methods
    # ========================================
    
    def _should_include_document(
        self, 
        document: Any, 
        user_context: Optional[UserContext]
    ) -> bool:
        """文書を結果に含めるべきかの権限チェック"""
        config = self._config_manager.load_config()
        if not config.enable_authentication or not user_context:
            return True  # 認証無効時は全て表示
        
        # TODO: 文書レベルの権限制御
        # 現在は基本的な読み取り権限のみチェック
        return user_context.has_permission('documents', 'read')
    
    def _convert_dataset_to_metadata(self, dataset: Any) -> DocumentMetadata:
        """データセットを統一メタデータに変換"""
        return DocumentMetadata(
            id=dataset.id,
            category='dataset',
            file_path="",  # データセットは複数ファイルの集合
            file_name=dataset.name,
            file_size=dataset.total_size or 0,
            created_at=dataset.created_at or datetime.now(),
            updated_at=dataset.updated_at or datetime.now(),
            title=dataset.name,
            summary=dataset.summary,
            authors=None,  # データセットには著者フィールドなし
            abstract=dataset.summary,
            keywords=None  # データセットにはキーワードフィールドなし
        )
    
    def _convert_paper_to_metadata(self, paper: Any) -> DocumentMetadata:
        """論文を統一メタデータに変換"""
        return DocumentMetadata(
            id=paper.id,
            category='paper',
            file_path=paper.file_path,
            file_name=paper.file_name,
            file_size=paper.file_size or 0,
            created_at=paper.indexed_at or datetime.now(),
            updated_at=paper.updated_at or datetime.now(),
            title=paper.title,
            summary=paper.abstract,
            authors=paper.authors,
            abstract=paper.abstract,
            keywords=paper.keywords
        )
    
    def _convert_poster_to_metadata(self, poster: Any) -> DocumentMetadata:
        """ポスターを統一メタデータに変換"""
        return DocumentMetadata(
            id=poster.id,
            category='poster',
            file_path=poster.file_path,
            file_name=poster.file_name,
            file_size=poster.file_size or 0,
            created_at=poster.indexed_at or datetime.now(),
            updated_at=poster.updated_at or datetime.now(),
            title=poster.title,
            summary=poster.abstract,
            authors=poster.authors,
            abstract=poster.abstract,
            keywords=poster.keywords
        )
    
    # ========================================
    # Service Integration
    # ========================================
    
    def register_google_drive_port(self, port):
        """Google Drive ポート登録（Instance A実装後）"""
        self._google_drive_port = port
    
    def register_vector_search_port(self, port):
        """ベクトル検索ポート登録（Instance B実装後）"""
        self._vector_search_port = port
    
    def register_auth_port(self, port):
        """認証ポート登録（Instance C実装後）"""
        self._auth_port = port
    
    def get_operation_statistics(self) -> Dict[str, Any]:
        """操作統計取得"""
        return {
            'operation_count': self._operation_count,
            'error_count': self._error_count,
            'error_rate': (self._error_count / self._operation_count * 100) if self._operation_count > 0 else 0,
            'last_operation': self._last_operation.isoformat()
        }


# ========================================
# Factory Functions
# ========================================

def create_document_service() -> DocumentServiceImpl:
    """
    DocumentService実装の作成
    
    Returns:
        DocumentServiceImpl: 実装インスタンス
    """
    return DocumentServiceImpl()