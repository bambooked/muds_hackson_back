"""
ベクトル検索エンジン連携機能
Chroma、Pinecone、Weaviateなどのベクトルデータベースとの統合
"""

import os
import json
import numpy as np
from typing import List, Dict, Optional, Any, Tuple
import logging
from datetime import datetime

try:
    # Chroma
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

try:
    # Sentence Transformers for embeddings
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    # Pinecone
    import pinecone
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False

logger = logging.getLogger(__name__)

class VectorSearchEngine:
    """ベクトル検索エンジン統合クラス"""
    
    def __init__(self):
        self.enabled = os.getenv('ENABLE_VECTOR_SEARCH', 'false').lower() == 'true'
        self.provider = os.getenv('VECTOR_SEARCH_PROVIDER', 'chroma').lower()
        self.host = os.getenv('VECTOR_SEARCH_HOST', 'localhost')
        self.port = int(os.getenv('VECTOR_SEARCH_PORT', '8000'))
        self.api_key = os.getenv('VECTOR_SEARCH_API_KEY', '')
        self.embedding_model_name = os.getenv('VECTOR_EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
        self.vector_dimension = int(os.getenv('VECTOR_DIMENSION', '384'))
        
        self.client = None
        self.collection = None
        self.embedding_model = None
        
        if self.enabled:
            self._initialize_provider()
            self._initialize_embedding_model()
    
    def _initialize_provider(self) -> bool:
        """ベクトル検索プロバイダーを初期化"""
        try:
            if self.provider == 'chroma':
                return self._initialize_chroma()
            elif self.provider == 'pinecone':
                return self._initialize_pinecone()
            else:
                logger.error(f"Unsupported vector search provider: {self.provider}")
                self.enabled = False
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize vector search provider {self.provider}: {e}")
            self.enabled = False
            return False
    
    def _initialize_chroma(self) -> bool:
        """Chromaクライアントを初期化"""
        if not CHROMA_AVAILABLE:
            logger.warning("ChromaDB not installed. Install with: pip install chromadb")
            self.enabled = False
            return False
        
        try:
            # ローカルまたはリモートクライアント
            if self.host == 'localhost':
                self.client = chromadb.Client(Settings(
                    chroma_db_impl="duckdb+parquet",
                    persist_directory="./chroma_db"
                ))
            else:
                self.client = chromadb.HttpClient(host=self.host, port=self.port)
            
            # コレクションを取得または作成
            try:
                self.collection = self.client.get_collection("research_documents")
            except:
                self.collection = self.client.create_collection(
                    name="research_documents",
                    metadata={"description": "Research documents and datasets"}
                )
            
            logger.info("ChromaDB client initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            return False
    
    def _initialize_pinecone(self) -> bool:
        """Pineconeクライアントを初期化"""
        if not PINECONE_AVAILABLE:
            logger.warning("Pinecone not installed. Install with: pip install pinecone-client")
            self.enabled = False
            return False
        
        if not self.api_key:
            logger.error("Pinecone API key not configured")
            self.enabled = False
            return False
        
        try:
            pinecone.init(api_key=self.api_key)
            
            # インデックス名
            index_name = "research-documents"
            
            # インデックスが存在しない場合は作成
            if index_name not in pinecone.list_indexes():
                pinecone.create_index(
                    index_name,
                    dimension=self.vector_dimension,
                    metric="cosine"
                )
            
            self.client = pinecone.Index(index_name)
            logger.info("Pinecone client initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            return False
    
    def _initialize_embedding_model(self) -> bool:
        """埋め込みモデルを初期化"""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("Sentence Transformers not installed. Install with: pip install sentence-transformers")
            return False
        
        try:
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
            logger.info(f"Embedding model loaded: {self.embedding_model_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            return False
    
    def is_enabled(self) -> bool:
        """ベクトル検索が有効かどうか"""
        return (self.enabled and 
                self.client is not None and 
                self.embedding_model is not None)
    
    def create_embedding(self, text: str) -> Optional[List[float]]:
        """テキストの埋め込みベクトルを生成"""
        if not self.embedding_model:
            return None
        
        try:
            embedding = self.embedding_model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Failed to create embedding: {e}")
            return None
    
    def add_document(self, doc_id: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """文書をベクトルデータベースに追加"""
        if not self.is_enabled():
            return False
        
        try:
            # 埋め込みベクトルを生成
            embedding = self.create_embedding(text)
            if not embedding:
                return False
            
            # メタデータ準備
            doc_metadata = metadata or {}
            doc_metadata.update({
                'timestamp': datetime.now().isoformat(),
                'text_length': len(text)
            })
            
            if self.provider == 'chroma':
                self.collection.add(
                    documents=[text],
                    embeddings=[embedding],
                    metadatas=[doc_metadata],
                    ids=[doc_id]
                )
            elif self.provider == 'pinecone':
                self.client.upsert([(doc_id, embedding, doc_metadata)])
            
            logger.info(f"Document added to vector database: {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add document {doc_id}: {e}")
            return False
    
    def search_similar(self, query_text: str, limit: int = 5, 
                      threshold: float = 0.7) -> List[Dict[str, Any]]:
        """類似文書を検索"""
        if not self.is_enabled():
            return []
        
        try:
            # クエリの埋め込みベクトルを生成
            query_embedding = self.create_embedding(query_text)
            if not query_embedding:
                return []
            
            results = []
            
            if self.provider == 'chroma':
                chroma_results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=limit
                )
                
                for i in range(len(chroma_results['ids'][0])):
                    doc_id = chroma_results['ids'][0][i]
                    distance = chroma_results['distances'][0][i]
                    similarity = 1 - distance  # Convert distance to similarity
                    
                    if similarity >= threshold:
                        results.append({
                            'id': doc_id,
                            'similarity': similarity,
                            'document': chroma_results['documents'][0][i],
                            'metadata': chroma_results['metadatas'][0][i]
                        })
            
            elif self.provider == 'pinecone':
                pinecone_results = self.client.query(
                    vector=query_embedding,
                    top_k=limit,
                    include_metadata=True
                )
                
                for match in pinecone_results['matches']:
                    if match['score'] >= threshold:
                        results.append({
                            'id': match['id'],
                            'similarity': match['score'],
                            'metadata': match.get('metadata', {})
                        })
            
            # 類似度でソート
            results.sort(key=lambda x: x['similarity'], reverse=True)
            logger.info(f"Vector search found {len(results)} similar documents")
            return results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    def delete_document(self, doc_id: str) -> bool:
        """文書をベクトルデータベースから削除"""
        if not self.is_enabled():
            return False
        
        try:
            if self.provider == 'chroma':
                self.collection.delete(ids=[doc_id])
            elif self.provider == 'pinecone':
                self.client.delete(ids=[doc_id])
            
            logger.info(f"Document deleted from vector database: {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return False
    
    def update_document(self, doc_id: str, text: str, 
                       metadata: Optional[Dict[str, Any]] = None) -> bool:
        """文書を更新"""
        # 削除してから再追加
        self.delete_document(doc_id)
        return self.add_document(doc_id, text, metadata)
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """コレクション統計を取得"""
        if not self.is_enabled():
            return {}
        
        try:
            if self.provider == 'chroma':
                count = self.collection.count()
                return {
                    'document_count': count,
                    'provider': self.provider,
                    'collection_name': self.collection.name
                }
            elif self.provider == 'pinecone':
                stats = self.client.describe_index_stats()
                return {
                    'document_count': stats.get('total_vector_count', 0),
                    'provider': self.provider,
                    'dimension': stats.get('dimension', self.vector_dimension)
                }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            
        return {}
    
    def batch_add_documents(self, documents: List[Dict[str, Any]]) -> int:
        """文書を一括追加"""
        if not self.is_enabled():
            return 0
        
        success_count = 0
        
        for doc in documents:
            doc_id = doc.get('id')
            text = doc.get('text', '')
            metadata = doc.get('metadata', {})
            
            if doc_id and text:
                if self.add_document(doc_id, text, metadata):
                    success_count += 1
        
        logger.info(f"Batch added {success_count}/{len(documents)} documents")
        return success_count
    
    def hybrid_search(self, query_text: str, traditional_results: List[Dict[str, Any]], 
                     vector_weight: float = 0.7, limit: int = 5) -> List[Dict[str, Any]]:
        """ハイブリッド検索（ベクトル検索 + 従来検索）"""
        if not self.is_enabled():
            return traditional_results[:limit]
        
        # ベクトル検索結果を取得
        vector_results = self.search_similar(query_text, limit * 2)
        
        # スコアを正規化してマージ
        combined_results = {}
        
        # ベクトル検索結果
        for result in vector_results:
            doc_id = result['id']
            combined_results[doc_id] = {
                'id': doc_id,
                'vector_score': result['similarity'] * vector_weight,
                'traditional_score': 0,
                'metadata': result.get('metadata', {}),
                'document': result.get('document', '')
            }
        
        # 従来検索結果
        traditional_weight = 1 - vector_weight
        max_traditional_score = max([r.get('score', 0) for r in traditional_results]) if traditional_results else 1
        
        for result in traditional_results:
            doc_id = result.get('id', '')
            normalized_score = (result.get('score', 0) / max_traditional_score) * traditional_weight
            
            if doc_id in combined_results:
                combined_results[doc_id]['traditional_score'] = normalized_score
            else:
                combined_results[doc_id] = {
                    'id': doc_id,
                    'vector_score': 0,
                    'traditional_score': normalized_score,
                    'metadata': result,
                    'document': result.get('content', '')
                }
        
        # 総合スコアでソート
        for result in combined_results.values():
            result['total_score'] = result['vector_score'] + result['traditional_score']
        
        sorted_results = sorted(
            combined_results.values(), 
            key=lambda x: x['total_score'], 
            reverse=True
        )
        
        return sorted_results[:limit]

# グローバルインスタンス
vector_search = VectorSearchEngine()