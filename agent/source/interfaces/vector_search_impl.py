"""
ChromaDBベクトル検索実装

Instance B: VectorSearchPort実装
- ChromaDB統合によるセマンティック検索
- sentence-transformersによる埋め込み生成
- 既存システムとの完全互換性維持
"""

import os
import json
import asyncio
import hashlib
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path

# Third-party imports (実装時に必要)
try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    VECTOR_SEARCH_AVAILABLE = True
except ImportError:
    chromadb = None
    SentenceTransformer = None
    VECTOR_SEARCH_AVAILABLE = False

from .search_ports import VectorSearchPort
from .data_models import (
    DocumentMetadata, SearchResult, UserContext, VectorSearchConfig, SearchError,
    create_document_metadata_from_existing, create_search_result_from_existing
)
from ..database.new_repository import DatasetRepository, PaperRepository, PosterRepository

logger = logging.getLogger(__name__)


class ChromaVectorSearchPort(VectorSearchPort):
    """
    ChromaDBを使用したベクトル検索実装
    
    既存システム保護：
    - ベクトル検索失敗時は既存システムで継続
    - 新機能は設定でON/OFF可能
    - 既存データベース構造は未変更
    """
    
    def __init__(self, config: Optional[VectorSearchConfig] = None):
        self.config = config or self._load_config_from_env()
        self.client = None
        self.collection = None
        self.embedding_model = None
        self.is_initialized = False
        
        # 既存repositoryとの連携
        self.dataset_repo = DatasetRepository()
        self.paper_repo = PaperRepository()
        self.poster_repo = PosterRepository()
    
    def _load_config_from_env(self) -> VectorSearchConfig:
        """環境変数からVectorSearchConfig作成"""
        return VectorSearchConfig(
            provider=os.getenv('VECTOR_DB_PROVIDER', 'chroma'),
            host=os.getenv('VECTOR_DB_HOST', 'localhost'),
            port=int(os.getenv('VECTOR_DB_PORT', '8000')),
            collection_name=os.getenv('VECTOR_COLLECTION_NAME', 'research_documents'),
            embedding_model=os.getenv('VECTOR_EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2'),
            similarity_threshold=float(os.getenv('VECTOR_SIMILARITY_THRESHOLD', '0.7')),
            max_results=int(os.getenv('VECTOR_MAX_RESULTS', '50')),
            persist_directory=os.getenv('VECTOR_PERSIST_DIRECTORY', 'agent/vector_db')
        )
    
    async def initialize_index(
        self, 
        config: VectorSearchConfig,
        force_recreate: bool = False
    ) -> bool:
        """ベクトルインデックス初期化"""
        try:
            if not VECTOR_SEARCH_AVAILABLE:
                logger.warning("Vector search dependencies not available. Skipping initialization.")
                return False
            
            self.config = config
            
            # ChromaDB初期化
            persist_path = Path(config.persist_directory)
            persist_path.mkdir(parents=True, exist_ok=True)
            
            self.client = chromadb.PersistentClient(
                path=str(persist_path),
                settings=Settings(anonymized_telemetry=False)
            )
            
            # 埋め込みモデル初期化
            logger.info(f"Loading embedding model: {config.embedding_model}")
            self.embedding_model = SentenceTransformer(config.embedding_model)
            
            # コレクション作成/取得
            if force_recreate:
                try:
                    self.client.delete_collection(config.collection_name)
                    logger.info(f"Deleted existing collection: {config.collection_name}")
                except:
                    pass
            
            self.collection = self.client.get_or_create_collection(
                name=config.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            
            self.is_initialized = True
            logger.info(f"Vector search initialized successfully. Collection: {config.collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Vector index initialization failed: {e}")
            raise SearchError(f"Vector index initialization failed: {e}")
    
    async def index_document(
        self,
        document: DocumentMetadata,
        content: str,
        user_context: Optional[UserContext] = None
    ) -> bool:
        """文書をベクトル化してインデックス"""
        try:
            if not self.is_initialized:
                logger.warning("Vector search not initialized. Skipping document indexing.")
                return False
            
            # 内容前処理
            cleaned_content = self._preprocess_content(content, document)
            
            # ベクトル化
            embedding = self.embedding_model.encode([cleaned_content])
            
            # ベクトルID生成
            vector_id = self._generate_vector_id(document)
            
            # メタデータ準備
            metadata = {
                "document_id": document.id,
                "category": document.category,
                "file_path": document.file_path,
                "file_name": document.file_name,
                "title": document.title or "",
                "authors": document.authors or "",
                "keywords": document.keywords or "",
                "created_at": document.created_at.isoformat() if document.created_at else "",
                "file_size": document.file_size,
                "content_preview": cleaned_content[:500]  # 最初の500文字
            }
            
            # ChromaDBに保存
            self.collection.upsert(
                embeddings=[embedding[0].tolist()],
                documents=[cleaned_content],
                metadatas=[metadata],
                ids=[vector_id]
            )
            
            # documentのvector_idを更新（将来的な拡張用）
            document.vector_id = vector_id
            
            logger.info(f"Document indexed successfully: {document.file_name} (vector_id: {vector_id})")
            return True
            
        except Exception as e:
            logger.error(f"Document indexing failed for {document.file_name}: {e}")
            return False
    
    async def search_similar(
        self,
        query: str,
        top_k: int = 10,
        similarity_threshold: float = 0.7,
        filter_metadata: Optional[Dict[str, Any]] = None,
        user_context: Optional[UserContext] = None
    ) -> List[SearchResult]:
        """類似文書検索"""
        try:
            if not self.is_initialized:
                logger.warning("Vector search not initialized. Returning empty results.")
                return []
            
            # クエリベクトル化
            query_embedding = self.embedding_model.encode([query])
            
            # ChromaDB検索実行
            search_params = {
                "query_embeddings": [query_embedding[0].tolist()],
                "n_results": min(top_k, self.config.max_results)
            }
            
            # フィルタ適用
            if filter_metadata:
                search_params["where"] = filter_metadata
            
            results = self.collection.query(**search_params)
            
            # SearchResultに変換
            search_results = []
            if results['ids'] and results['ids'][0]:
                for i, (doc_id, distance, metadata) in enumerate(zip(
                    results['ids'][0], 
                    results['distances'][0], 
                    results['metadatas'][0]
                )):
                    # コサイン距離を類似度に変換
                    similarity = 1.0 - distance
                    
                    if similarity >= similarity_threshold:
                        # DocumentMetadataを復元
                        document = await self._restore_document_metadata(metadata)
                        if document:
                            search_results.append(SearchResult(
                                document=document,
                                score=similarity,
                                relevance_type='semantic',
                                explanation=f"Vector similarity: {similarity:.3f}",
                                highlighted_content=metadata.get('content_preview', '')
                            ))
            
            # スコア順でソート
            search_results.sort(key=lambda x: x.score, reverse=True)
            
            logger.info(f"Vector search completed: {len(search_results)} results for query '{query}'")
            return search_results
            
        except Exception as e:
            logger.error(f"Vector search failed for query '{query}': {e}")
            raise SearchError(f"Vector search failed: {e}")
    
    async def batch_index_documents(
        self,
        documents: List[Tuple[DocumentMetadata, str]],
        batch_size: int = 10,
        user_context: Optional[UserContext] = None
    ) -> Dict[str, Any]:
        """文書群の一括インデックス"""
        results = {"successful": 0, "failed": 0, "errors": []}
        
        try:
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                batch_tasks = []
                
                for document, content in batch:
                    task = self.index_document(document, content, user_context)
                    batch_tasks.append(task)
                
                # バッチ実行
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                for j, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        results["failed"] += 1
                        results["errors"].append(f"Document {batch[j][0].file_name}: {str(result)}")
                    elif result:
                        results["successful"] += 1
                    else:
                        results["failed"] += 1
                        results["errors"].append(f"Document {batch[j][0].file_name}: Unknown error")
                
                logger.info(f"Batch {i//batch_size + 1} completed: {results['successful']} successful, {results['failed']} failed")
        
        except Exception as e:
            logger.error(f"Batch indexing failed: {e}")
            results["errors"].append(f"Batch processing error: {str(e)}")
        
        return results
    
    async def delete_document(
        self,
        vector_id: str,
        user_context: Optional[UserContext] = None
    ) -> bool:
        """ベクトルインデックスから文書削除"""
        try:
            if not self.is_initialized:
                return False
            
            self.collection.delete(ids=[vector_id])
            logger.info(f"Document deleted from vector index: {vector_id}")
            return True
            
        except Exception as e:
            logger.error(f"Document deletion failed for vector_id {vector_id}: {e}")
            return False
    
    async def get_index_stats(self) -> Dict[str, Any]:
        """インデックス統計情報取得"""
        try:
            if not self.is_initialized:
                return {"status": "not_initialized", "total_documents": 0}
            
            count = self.collection.count()
            
            # ディスク使用量計算
            persist_path = Path(self.config.persist_directory)
            index_size_mb = 0
            if persist_path.exists():
                index_size_mb = sum(f.stat().st_size for f in persist_path.rglob('*') if f.is_file()) / (1024 * 1024)
            
            return {
                "status": "healthy",
                "total_documents": count,
                "index_size_mb": round(index_size_mb, 2),
                "last_updated": datetime.now().isoformat(),
                "collection_name": self.config.collection_name,
                "embedding_model": self.config.embedding_model,
                "persist_directory": str(self.config.persist_directory)
            }
            
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return {"status": "error", "error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """ベクトル検索システムヘルスチェック"""
        try:
            start_time = datetime.now()
            
            health_status = {
                "status": "healthy",
                "initialized": self.is_initialized,
                "dependencies_available": VECTOR_SEARCH_AVAILABLE,
                "response_time_ms": 0,
                "errors": []
            }
            
            if not VECTOR_SEARCH_AVAILABLE:
                health_status["status"] = "degraded"
                health_status["errors"].append("Vector search dependencies not available")
            
            if not self.is_initialized:
                health_status["status"] = "degraded"
                health_status["errors"].append("Vector search not initialized")
            
            if self.is_initialized:
                # 簡単なテストクエリ実行
                try:
                    test_results = await self.search_similar("test query", top_k=1)
                    health_status["test_query_results"] = len(test_results)
                except Exception as e:
                    health_status["status"] = "unhealthy"
                    health_status["errors"].append(f"Test query failed: {str(e)}")
            
            # レスポンス時間計算
            end_time = datetime.now()
            health_status["response_time_ms"] = int((end_time - start_time).total_seconds() * 1000)
            
            return health_status
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": 0
            }
    
    # Private helper methods
    
    def _preprocess_content(self, content: str, document: DocumentMetadata) -> str:
        """文書内容の前処理"""
        # タイトル、要約、キーワードを組み合わせた検索対象テキスト作成
        parts = []
        
        if document.title:
            parts.append(f"Title: {document.title}")
        
        if document.abstract:
            parts.append(f"Abstract: {document.abstract}")
        elif document.summary:
            parts.append(f"Summary: {document.summary}")
        
        if document.keywords:
            parts.append(f"Keywords: {document.keywords}")
        
        if document.authors:
            parts.append(f"Authors: {document.authors}")
        
        # 内容の最初の部分を追加（ファイルサイズに応じて調整）
        content_preview = content[:2000] if len(content) > 2000 else content
        parts.append(f"Content: {content_preview}")
        
        return " ".join(parts)
    
    def _generate_vector_id(self, document: DocumentMetadata) -> str:
        """ベクトルID生成"""
        unique_string = f"{document.category}_{document.id}_{document.file_path}"
        return hashlib.md5(unique_string.encode()).hexdigest()
    
    async def _restore_document_metadata(self, metadata: Dict[str, Any]) -> Optional[DocumentMetadata]:
        """メタデータからDocumentMetadataを復元"""
        try:
            # データベースから最新情報を取得
            category = metadata.get('category')
            doc_id = metadata.get('document_id')
            
            if not category or not doc_id:
                return None
            
            # カテゴリ別に適切なRepositoryから取得
            if category == 'dataset':
                dataset = self.dataset_repo.find_by_id(doc_id)
                if dataset:
                    return DocumentMetadata(
                        id=dataset.id,
                        category='dataset',
                        file_path='',  # データセットはディレクトリ
                        file_name=dataset.name,
                        file_size=dataset.total_size,
                        created_at=dataset.created_at,
                        updated_at=dataset.updated_at,
                        title=dataset.name,
                        summary=dataset.summary
                    )
            
            elif category == 'paper':
                paper = self.paper_repo.find_by_id(doc_id)
                if paper:
                    return DocumentMetadata(
                        id=paper.id,
                        category='paper',
                        file_path=paper.file_path,
                        file_name=paper.file_name,
                        file_size=paper.file_size,
                        created_at=paper.created_at,
                        updated_at=paper.updated_at,
                        title=paper.title,
                        summary=paper.abstract,
                        authors=paper.authors,
                        abstract=paper.abstract,
                        keywords=paper.keywords
                    )
            
            elif category == 'poster':
                poster = self.poster_repo.find_by_id(doc_id)
                if poster:
                    return DocumentMetadata(
                        id=poster.id,
                        category='poster',
                        file_path=poster.file_path,
                        file_name=poster.file_name,
                        file_size=poster.file_size,
                        created_at=poster.created_at,
                        updated_at=poster.updated_at,
                        title=poster.title,
                        summary=poster.abstract,
                        authors=poster.authors,
                        abstract=poster.abstract,
                        keywords=poster.keywords
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to restore document metadata: {e}")
            return None


# Utility function for easy instantiation
def create_vector_search_port(config: Optional[VectorSearchConfig] = None) -> ChromaVectorSearchPort:
    """ChromaVectorSearchPortインスタンス作成ヘルパー"""
    return ChromaVectorSearchPort(config)


# Configuration loading helper
def load_vector_search_config_from_env() -> VectorSearchConfig:
    """環境変数からVectorSearchConfig作成"""
    return VectorSearchConfig(
        provider=os.getenv('VECTOR_DB_PROVIDER', 'chroma'),
        host=os.getenv('VECTOR_DB_HOST', 'localhost'),
        port=int(os.getenv('VECTOR_DB_PORT', '8000')),
        collection_name=os.getenv('VECTOR_COLLECTION_NAME', 'research_documents'),
        embedding_model=os.getenv('VECTOR_EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2'),
        similarity_threshold=float(os.getenv('VECTOR_SIMILARITY_THRESHOLD', '0.7')),
        max_results=int(os.getenv('VECTOR_MAX_RESULTS', '50')),
        persist_directory=os.getenv('VECTOR_PERSIST_DIRECTORY', 'agent/vector_db')
    )