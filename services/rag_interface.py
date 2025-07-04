"""
RAG機能のPaaS統合インターフェース

このモジュールは学部内データ管理PaaSとRAG機能の境界を定義します。
内部実装が変更されても、このインターフェースを通じて一貫したアクセスを提供します。
"""

from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from pathlib import Path
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class DocumentMetadata:
    """文書メタデータの標準化形式"""
    id: int
    title: str
    category: str  # 'dataset', 'paper', 'poster'
    summary: str
    keywords: List[str]
    authors: Optional[str] = None
    file_path: str = ""
    file_size: int = 0
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'category': self.category,
            'summary': self.summary,
            'keywords': self.keywords,
            'authors': self.authors,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


@dataclass
class SearchResult:
    """検索結果の標準化形式"""
    documents: List[DocumentMetadata]
    total_count: int
    query: str
    execution_time_ms: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'documents': [doc.to_dict() for doc in self.documents],
            'total_count': self.total_count,
            'query': self.query,
            'execution_time_ms': self.execution_time_ms
        }


@dataclass
class IngestionResult:
    """文書取り込み結果の標準化形式"""
    success: bool
    message: str
    processed_files: int
    failed_files: int
    details: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message,
            'processed_files': self.processed_files,
            'failed_files': self.failed_files,
            'details': self.details
        }


@dataclass
class SystemStats:
    """システム統計情報の標準化形式"""
    total_documents: int
    documents_by_category: Dict[str, int]
    analysis_completion_rate: float
    last_update: datetime
    storage_size_mb: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_documents': self.total_documents,
            'documents_by_category': self.documents_by_category,
            'analysis_completion_rate': self.analysis_completion_rate,
            'last_update': self.last_update.isoformat(),
            'storage_size_mb': self.storage_size_mb
        }


class RAGInterface:
    """
    RAG機能のPaaS統合インターフェース
    
    このクラスは内部実装の詳細を隠蔽し、
    PaaS側に安定したAPIを提供します。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        RAGインターフェースを初期化
        
        Args:
            config: 設定辞書（API keys, paths等）
        """
        self._config = config or {}
        self._internal_components = None
        self._initialize_components()
    
    def _initialize_components(self):
        """内部コンポーネントの初期化（実装の詳細を隠蔽）"""
        try:
            # 実際の実装はここで既存コンポーネントを読み込み
            from agent.source.ui.interface import UserInterface
            from agent.source.indexer.new_indexer import NewFileIndexer
            from agent.source.analyzer.new_analyzer import NewFileAnalyzer
            from agent.source.database.new_repository import (
                DatasetRepository, PaperRepository, PosterRepository
            )
            
            self._ui = UserInterface()
            self._indexer = NewFileIndexer(auto_analyze=True)
            self._analyzer = NewFileAnalyzer()
            self._repos = {
                'dataset': DatasetRepository(),
                'paper': PaperRepository(),
                'poster': PosterRepository()
            }
            
            logger.info("RAG components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG components: {e}")
            raise RuntimeError(f"RAG initialization failed: {e}")
    
    def ingest_documents(self, source_path: Optional[str] = None) -> IngestionResult:
        """
        文書を取り込み、自動解析を実行
        
        Args:
            source_path: 取り込み元パス（Noneの場合はデフォルトのdataディレクトリ）
            
        Returns:
            IngestionResult: 取り込み結果
        """
        try:
            start_time = datetime.now()
            
            # 既存のインデクサーを使用して取り込み実行
            results = self._indexer.index_all_files()
            
            # 結果を標準化形式に変換
            return IngestionResult(
                success=True,
                message="Document ingestion completed successfully",
                processed_files=results.get('total_files', 0),
                failed_files=results.get('failed_files', 0),
                details={
                    'datasets': results.get('datasets', {}),
                    'papers': results.get('papers', {}),
                    'posters': results.get('posters', {}),
                    'execution_time': str(datetime.now() - start_time)
                }
            )
            
        except Exception as e:
            logger.error(f"Document ingestion failed: {e}")
            return IngestionResult(
                success=False,
                message=f"Ingestion failed: {str(e)}",
                processed_files=0,
                failed_files=0,
                details={'error': str(e)}
            )
    
    def search_documents(
        self, 
        query: str, 
        limit: int = 10,
        category: Optional[str] = None
    ) -> SearchResult:
        """
        文書を検索
        
        Args:
            query: 検索クエリ
            limit: 結果の最大件数
            category: カテゴリ絞り込み（'dataset', 'paper', 'poster'）
            
        Returns:
            SearchResult: 検索結果
        """
        try:
            start_time = datetime.now()
            documents = []
            
            # カテゴリ指定がある場合はそのカテゴリのみ検索
            search_categories = [category] if category else ['dataset', 'paper', 'poster']
            
            for cat in search_categories:
                if cat in self._repos:
                    repo_results = self._repos[cat].search_by_keyword(query)
                    for result in repo_results[:limit]:
                        documents.append(self._convert_to_metadata(result, cat))
            
            # 結果を制限数に合わせて調整
            documents = documents[:limit]
            
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return SearchResult(
                documents=documents,
                total_count=len(documents),
                query=query,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return SearchResult(
                documents=[],
                total_count=0,
                query=query,
                execution_time_ms=0
            )
    
    def get_document_detail(self, document_id: int, category: str) -> Optional[DocumentMetadata]:
        """
        特定の文書の詳細情報を取得
        
        Args:
            document_id: 文書ID
            category: カテゴリ（'dataset', 'paper', 'poster'）
            
        Returns:
            DocumentMetadata: 文書詳細（見つからない場合はNone）
        """
        try:
            if category not in self._repos:
                return None
                
            document = self._repos[category].find_by_id(document_id)
            if document:
                return self._convert_to_metadata(document, category)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get document detail: {e}")
            return None
    
    def get_system_stats(self) -> SystemStats:
        """
        システム統計情報を取得
        
        Returns:
            SystemStats: システム統計情報
        """
        try:
            stats_by_category = {}
            total_docs = 0
            
            for category, repo in self._repos.items():
                count = repo.count_all()
                stats_by_category[category] = count
                total_docs += count
            
            # 解析完了率の計算（既存のアナライザーを使用）
            analysis_summary = self._analyzer.get_analysis_summary()
            completion_rate = 0.0
            if analysis_summary:
                total_analyzed = sum(cat_stats.get('analyzed', 0) for cat_stats in analysis_summary.values())
                total_files = sum(cat_stats.get('total', 0) for cat_stats in analysis_summary.values())
                completion_rate = (total_analyzed / total_files * 100) if total_files > 0 else 0.0
            
            return SystemStats(
                total_documents=total_docs,
                documents_by_category=stats_by_category,
                analysis_completion_rate=completion_rate,
                last_update=datetime.now(),
                storage_size_mb=0.0  # TODO: 実装が必要な場合
            )
            
        except Exception as e:
            logger.error(f"Failed to get system stats: {e}")
            return SystemStats(
                total_documents=0,
                documents_by_category={},
                analysis_completion_rate=0.0,
                last_update=datetime.now(),
                storage_size_mb=0.0
            )
    
    def _convert_to_metadata(self, document, category: str) -> DocumentMetadata:
        """内部文書オブジェクトを標準化メタデータに変換"""
        try:
            # カテゴリによって異なるフィールドを処理
            if category == 'dataset':
                return DocumentMetadata(
                    id=document.id,
                    title=document.name,
                    category=category,
                    summary=document.summary or "",
                    keywords=[],  # データセットにはキーワードフィールドがない
                    file_path="",  # データセットは複数ファイルの集合
                    file_size=document.total_size or 0,
                    created_at=document.created_at
                )
            else:  # paper, poster
                keywords = []
                if hasattr(document, 'keywords') and document.keywords:
                    try:
                        keywords = json.loads(document.keywords) if isinstance(document.keywords, str) else document.keywords
                    except:
                        keywords = [document.keywords] if document.keywords else []
                
                return DocumentMetadata(
                    id=document.id,
                    title=document.title or document.file_name,
                    category=category,
                    summary=document.abstract or "",
                    keywords=keywords,
                    authors=document.authors,
                    file_path=document.file_path,
                    file_size=document.file_size or 0,
                    created_at=document.created_at
                )
                
        except Exception as e:
            logger.error(f"Failed to convert document to metadata: {e}")
            # フォールバック用のデフォルト値
            return DocumentMetadata(
                id=getattr(document, 'id', 0),
                title=getattr(document, 'name', getattr(document, 'title', getattr(document, 'file_name', 'Unknown'))),
                category=category,
                summary="",
                keywords=[],
                created_at=getattr(document, 'created_at', None)
            )


# 使用例とテスト関数
def example_usage():
    """RAGインターフェースの使用例"""
    
    # RAGインターフェースの初期化
    rag = RAGInterface()
    
    # 文書の取り込み
    ingestion_result = rag.ingest_documents()
    print(f"Ingestion: {ingestion_result.to_dict()}")
    
    # 文書検索
    search_result = rag.search_documents("機械学習", limit=5)
    print(f"Search results: {search_result.to_dict()}")
    
    # システム統計
    stats = rag.get_system_stats()
    print(f"System stats: {stats.to_dict()}")


if __name__ == "__main__":
    example_usage()