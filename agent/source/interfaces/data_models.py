"""
共通データモデル定義

このモジュールは、全てのインターフェースで使用される共通データ型を定義します。
既存システムとの互換性を保ちながら、新機能用の拡張フィールドを追加します。

Claude Code実装ガイダンス：
- 全てのフィールドは型ヒント付き
- Optionalフィールドはデフォルト値設定済み
- dataclassを使用してシリアライゼーション対応
- 既存システムとの変換メソッド提供
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union, Any
from pathlib import Path


# ========================================
# Search Mode Definition (Fallback)
# ========================================

class SearchMode(Enum):
    """検索モード（フォールバック定義）"""
    KEYWORD_ONLY = "keyword"
    SEMANTIC_ONLY = "semantic"
    HYBRID = "hybrid"


class Permission(Enum):
    """権限定義（フォールバック）"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"


# ========================================
# Core Data Models
# ========================================

@dataclass
class DocumentContent:
    """
    文書コンテンツを表すデータモデル
    
    Claude Code実装時の注意：
    - raw_contentは必須、他は解析結果に応じて設定
    - file_pathは既存システムとの互換性のため必須
    - metadataは拡張情報格納用
    """
    file_path: str
    raw_content: str
    content_type: str  # 'pdf', 'csv', 'json', 'jsonl', 'txt'
    file_size: int
    content_hash: Optional[str] = None
    encoding: str = 'utf-8'
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_existing_format(self) -> Dict[str, Any]:
        """既存システム形式への変換"""
        return {
            'file_path': self.file_path,
            'content': self.raw_content,
            'file_size': self.file_size,
            'content_hash': self.content_hash,
            **self.metadata
        }


@dataclass  
class DocumentMetadata:
    """
    文書メタデータを表すデータモデル（既存RAGInterfaceと互換）
    
    Claude Code実装時の注意：
    - category必須: 'dataset', 'paper', 'poster'のいずれか
    - 既存システムのテーブル構造と完全互換
    - 新機能用フィールドはOptionalで追加
    """
    id: int
    category: str  # 'dataset', 'paper', 'poster'
    file_path: str
    file_name: str
    file_size: int
    created_at: datetime
    updated_at: datetime
    
    # Content fields (解析結果)
    title: Optional[str] = None
    summary: Optional[str] = None
    authors: Optional[str] = None
    abstract: Optional[str] = None
    keywords: Optional[str] = None
    
    # Extended fields (新機能用)
    content_hash: Optional[str] = None
    indexed_at: Optional[datetime] = None
    analysis_status: str = 'pending'  # 'pending', 'analyzed', 'failed'
    vector_id: Optional[str] = None  # ベクトル検索用ID
    source_type: str = 'local'  # 'local', 'google_drive', 'upload'
    external_id: Optional[str] = None  # Google Drive file ID等
    access_permissions: Dict[str, Any] = field(default_factory=dict)
    
    def to_existing_format(self) -> Dict[str, Any]:
        """既存システム形式への変換"""
        base_data = {
            'id': self.id,
            'file_path': self.file_path,
            'file_name': self.file_name,
            'file_size': self.file_size,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'title': self.title,
            'summary': self.summary,
            'authors': self.authors,
            'abstract': self.abstract,
            'keywords': self.keywords,
            'content_hash': self.content_hash,
            'indexed_at': self.indexed_at
        }
        return {k: v for k, v in base_data.items() if v is not None}


@dataclass
class SearchResult:
    """
    検索結果を表すデータモデル（既存RAGInterfaceと互換）
    
    Claude Code実装時の注意：
    - scoreとrelevance_typeで検索手法を区別
    - metadataに追加情報を格納
    - 既存システムとの完全互換性維持
    """
    document: DocumentMetadata
    score: float  # 関連度スコア (0.0-1.0)
    relevance_type: str  # 'keyword', 'semantic', 'hybrid'
    highlighted_content: Optional[str] = None
    explanation: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_existing_format(self) -> Dict[str, Any]:
        """既存システム形式への変換"""
        return {
            'id': self.document.id,
            'category': self.document.category,
            'file_name': self.document.file_name,
            'title': self.document.title,
            'summary': self.document.summary,
            'score': self.score,
            'highlighted_content': self.highlighted_content
        }


class JobStatus(Enum):
    """ジョブ実行状況"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class IngestionResult:
    """
    データ取り込み結果を表すデータモデル
    
    Claude Code実装時の注意：
    - job_idで非同期処理追跡
    - statusでジョブ進行状況を管理
    - errorsに詳細なエラー情報を格納
    """
    job_id: str
    status: JobStatus
    total_files: int
    processed_files: int
    successful_files: int
    failed_files: int
    start_time: datetime
    end_time: Optional[datetime] = None
    processed_documents: List[DocumentMetadata] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def progress_percentage(self) -> float:
        """進行率計算（0.0-100.0）"""
        if self.total_files == 0:
            return 100.0
        return (self.processed_files / self.total_files) * 100.0
    
    @property
    def is_completed(self) -> bool:
        """完了判定"""
        return self.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]


@dataclass
class UserContext:
    """
    ユーザーコンテキスト情報
    
    Claude Code実装時の注意：
    - user_idは必須（認証システムで設定）
    - permissionsで細かいアクセス制御
    - metadataに追加情報格納
    """
    user_id: str
    email: str
    display_name: str
    domain: str  # 'university.ac.jp'等
    roles: List[str]  # ['student', 'faculty', 'admin', 'guest']
    permissions: Dict[str, List[str]]  # {'documents': ['read', 'write'], ...}
    session_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def has_permission(self, resource: str, action: str) -> bool:
        """権限チェック"""
        return action in self.permissions.get(resource, [])
    
    def is_faculty(self) -> bool:
        """教員判定"""
        return 'faculty' in self.roles or 'admin' in self.roles


@dataclass
class SystemStats:
    """
    システム統計情報（既存interface.pyと互換）
    
    Claude Code実装時の注意：
    - 既存システムの統計情報を拡張
    - 新機能の統計も追加
    - ダッシュボード表示用
    """
    total_documents: int
    documents_by_category: Dict[str, int]
    analysis_completion_rate: Dict[str, float]
    total_storage_size: int
    
    # Extended stats (新機能用)
    vector_index_size: Optional[int] = None
    active_users: Optional[int] = None
    search_query_count: Optional[int] = None
    google_drive_sync_status: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.now)
    
    def to_existing_format(self) -> Dict[str, Any]:
        """既存システム形式への変換"""
        return {
            'total_documents': self.total_documents,
            'documents_by_category': self.documents_by_category,
            'analysis_completion_rate': self.analysis_completion_rate,
            'total_storage_size': self.total_storage_size
        }


# ========================================
# Configuration Models
# ========================================

@dataclass
class GoogleDriveConfig:
    """Google Drive設定"""
    credentials_path: str
    scopes: List[str] = field(default_factory=lambda: ['https://www.googleapis.com/auth/drive.readonly'])
    max_file_size_mb: int = 100
    supported_mime_types: List[str] = field(default_factory=lambda: [
        'application/pdf',
        'text/csv', 
        'application/json',
        'text/plain'
    ])
    sync_interval_minutes: int = 60
    batch_size: int = 10


@dataclass  
class VectorSearchConfig:
    """ベクトル検索設定"""
    provider: str  # 'chroma', 'qdrant', 'pinecone'
    host: str = 'localhost'
    port: int = 8000
    collection_name: str = 'research_documents'
    embedding_model: str = 'sentence-transformers/all-MiniLM-L6-v2'
    similarity_threshold: float = 0.7
    max_results: int = 50
    persist_directory: Optional[str] = None


@dataclass
class AuthConfig:
    """認証設定"""
    provider: str  # 'google_oauth2', 'saml', 'local'
    client_id: str
    client_secret: str
    redirect_uri: str
    allowed_domains: List[str] = field(default_factory=list)
    session_timeout_minutes: int = 480  # 8 hours
    require_email_verification: bool = True


@dataclass
class PaaSConfig:
    """PaaS全体設定"""
    environment: str  # 'development', 'staging', 'production'
    api_host: str = '0.0.0.0'
    api_port: int = 8000
    debug: bool = False
    
    # Feature toggles
    enable_google_drive: bool = False
    enable_vector_search: bool = False  
    enable_authentication: bool = False
    enable_monitoring: bool = False
    
    # Component configs
    google_drive: Optional[GoogleDriveConfig] = None
    vector_search: Optional[VectorSearchConfig] = None
    auth: Optional[AuthConfig] = None


# ========================================
# Error Models  
# ========================================

class PaaSError(Exception):
    """PaaSシステム基底例外"""
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


class InputError(PaaSError):
    """データ入力関連エラー"""
    pass


class SearchError(PaaSError):
    """検索関連エラー"""
    pass


class AuthError(PaaSError):
    """認証・認可関連エラー"""
    pass


# ========================================
# Utility Functions
# ========================================

def create_document_metadata_from_existing(existing_data: Dict[str, Any]) -> DocumentMetadata:
    """
    既存システムのデータからDocumentMetadataを作成
    
    Claude Code実装時の注意：
    - 既存システムとの橋渡し用
    - 必須フィールドのみ設定、他はデフォルト値
    """
    return DocumentMetadata(
        id=existing_data.get('id', 0),
        category=existing_data.get('category', 'unknown'),
        file_path=existing_data['file_path'],
        file_name=existing_data['file_name'],
        file_size=existing_data.get('file_size', 0),
        created_at=existing_data.get('created_at', datetime.now()),
        updated_at=existing_data.get('updated_at', datetime.now()),
        title=existing_data.get('title'),
        summary=existing_data.get('summary'),
        authors=existing_data.get('authors'),
        abstract=existing_data.get('abstract'),
        keywords=existing_data.get('keywords'),
        content_hash=existing_data.get('content_hash'),
        indexed_at=existing_data.get('indexed_at')
    )


def create_search_result_from_existing(existing_data: Dict[str, Any], score: float = 1.0) -> SearchResult:
    """
    既存システムの検索結果からSearchResultを作成
    
    Claude Code実装時の注意：
    - 既存システムとの橋渡し用
    - scoreはキーワード検索の場合1.0でOK
    """
    document = create_document_metadata_from_existing(existing_data)
    return SearchResult(
        document=document,
        score=score,
        relevance_type='keyword',
        highlighted_content=existing_data.get('highlighted_content')
    )