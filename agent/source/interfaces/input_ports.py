"""
データ入力インターフェース定義

このモジュールは、外部データソースからの文書取り込み機能を抽象化します。
Google Drive連携、ファイルアップロード等の入力手段を統一インターフェースで提供。

Claude Code実装ガイダンス：
- 各ポートは完全に独立して実装可能
- 既存NewFileIndexerとの統合は必須
- 非同期処理でパフォーマンス最適化
- プログレス追跡でユーザー体験向上

実装優先順位：
1. GoogleDrivePort (デモ価値最大)
2. FileUploadPort (実用性高)
3. DocumentInputPort (統合レイヤー)
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, AsyncIterator
from pathlib import Path
import asyncio

from .data_models import (
    DocumentContent,
    DocumentMetadata, 
    IngestionResult,
    UserContext,
    JobStatus,
    GoogleDriveConfig,
    InputError
)


class DocumentInputPort(ABC):
    """
    文書入力の統一インターフェース
    
    役割：
    - 複数の入力ソースを統一的に処理
    - 既存NewFileIndexerとの橋渡し
    - バッチ処理とプログレス管理
    
    Claude Code実装時の注意：
    - このポートは他のInputPortを統合する役割
    - 実装時は既存のUserInterface.update_index()と連携
    - 自動解析機能(auto_analyze=True)は必須
    """
    
    @abstractmethod
    async def ingest_documents(
        self,
        source_type: str,
        source_config: Dict[str, Any],
        user_context: Optional[UserContext] = None
    ) -> IngestionResult:
        """
        指定ソースから文書を取り込み
        
        Args:
            source_type: 'google_drive', 'upload', 'local_scan'
            source_config: ソース固有の設定
            user_context: ユーザーコンテキスト（認証時）
            
        Returns:
            IngestionResult: 取り込み結果とジョブ情報
            
        Raises:
            InputError: 取り込み処理エラー
            
        Claude Code実装例：
        ```python
        async def ingest_documents(self, source_type, source_config, user_context=None):
            job_id = f"{source_type}_{datetime.now().isoformat()}"
            
            if source_type == 'google_drive':
                return await self.google_drive_port.sync_folder(
                    source_config['folder_id'], job_id, user_context
                )
            elif source_type == 'upload':
                return await self.upload_port.process_uploads(
                    source_config['files'], job_id, user_context
                )
            # ...
        ```
        """
        pass
    
    @abstractmethod
    async def get_ingestion_status(self, job_id: str) -> IngestionResult:
        """
        取り込みジョブの状況取得
        
        Args:
            job_id: ジョブID
            
        Returns:
            IngestionResult: 現在のジョブ状況
        
        Claude Code実装時の注意：
        - ジョブ情報はメモリorRedisに保存
        - プログレス情報をリアルタイム更新
        """
        pass
    
    @abstractmethod
    async def cancel_ingestion(self, job_id: str) -> bool:
        """
        取り込みジョブのキャンセル
        
        Args:
            job_id: キャンセルするジョブID
            
        Returns:
            bool: キャンセル成功可否
        """
        pass
    
    @abstractmethod
    async def list_available_sources(
        self, 
        user_context: Optional[UserContext] = None
    ) -> List[Dict[str, Any]]:
        """
        利用可能な入力ソース一覧
        
        Returns:
            List[Dict]: [{'type': 'google_drive', 'available': True, ...}, ...]
            
        Claude Code実装時の注意：
        - 設定によって利用可能性を判定
        - ユーザー権限も考慮
        """
        pass


class GoogleDrivePort(ABC):
    """
    Google Drive連携インターフェース
    
    役割：
    - Google Drive APIとの通信
    - フォルダ同期機能
    - 権限管理との連携
    
    Claude Code実装ガイダンス：
    - Google Drive API v3使用推奨
    - OAuth2認証実装必須
    - ファイル形式フィルタリング実装
    - 大容量ファイル対応（ストリーミング）
    
    実装パッケージ推奨：
    - google-api-python-client
    - google-auth-oauthlib
    """
    
    @abstractmethod
    async def authenticate(
        self, 
        credentials: Dict[str, Any],
        user_context: Optional[UserContext] = None
    ) -> bool:
        """
        Google Drive認証
        
        Args:
            credentials: OAuth2認証情報
            user_context: ユーザーコンテキスト
            
        Returns:
            bool: 認証成功可否
            
        Claude Code実装例：
        ```python
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import Flow
        
        async def authenticate(self, credentials, user_context=None):
            try:
                # OAuth2フロー実装
                flow = Flow.from_client_config(credentials, scopes)
                # ...
                return True
            except Exception as e:
                raise InputError(f"Google Drive authentication failed: {e}")
        ```
        """
        pass
    
    @abstractmethod  
    async def list_folders(
        self,
        parent_folder_id: Optional[str] = None,
        user_context: Optional[UserContext] = None
    ) -> List[Dict[str, Any]]:
        """
        フォルダ一覧取得
        
        Args:
            parent_folder_id: 親フォルダID（Noneの場合はルート）
            user_context: ユーザーコンテキスト
            
        Returns:
            List[Dict]: [{'id': '...', 'name': '...', 'type': 'folder'}, ...]
        """
        pass
    
    @abstractmethod
    async def sync_folder(
        self,
        folder_id: str,
        job_id: str,
        user_context: Optional[UserContext] = None,
        recursive: bool = True
    ) -> IngestionResult:
        """
        指定フォルダを同期
        
        Args:
            folder_id: Google DriveフォルダID
            job_id: ジョブ追跡用ID
            user_context: ユーザーコンテキスト  
            recursive: サブフォルダも同期するか
            
        Returns:
            IngestionResult: 同期結果
            
        Claude Code実装時の注意：
        - ファイル形式フィルタリング必須
        - 重複チェック実装（content_hash使用）
        - 既存NewFileIndexerとの連携必須
        - プログレス更新必須
        
        実装フロー：
        1. フォルダ内ファイル一覧取得
        2. サポート形式でフィルタリング
        3. 各ファイルダウンロード
        4. 一時ファイル作成
        5. NewFileIndexer.scan_and_index()呼び出し
        6. 一時ファイル削除
        7. プログレス更新
        """
        pass
    
    @abstractmethod
    async def download_file(
        self,
        file_id: str,
        target_path: Path,
        user_context: Optional[UserContext] = None
    ) -> DocumentContent:
        """
        ファイルダウンロード
        
        Args:
            file_id: Google DriveファイルID
            target_path: 保存先パス
            user_context: ユーザーコンテキスト
            
        Returns:
            DocumentContent: ダウンロードしたファイル情報
        """
        pass
    
    @abstractmethod
    async def get_file_metadata(
        self,
        file_id: str,
        user_context: Optional[UserContext] = None
    ) -> Dict[str, Any]:
        """
        ファイルメタデータ取得
        
        Returns:
            Dict: {'id': '...', 'name': '...', 'size': ..., 'mimeType': '...'}
        """
        pass


class FileUploadPort(ABC):
    """
    ファイルアップロード処理インターフェース
    
    役割：
    - Webアップロードファイルの処理
    - 一時ファイル管理
    - ウイルススキャン等のセキュリティ処理
    
    Claude Code実装ガイダンス：
    - FastAPIのUploadFileと連携
    - 一時ディレクトリでファイル処理
    - アップロード完了後は既存システムに転送
    """
    
    @abstractmethod
    async def process_uploads(
        self,
        uploaded_files: List[Any],  # FastAPI UploadFile等
        job_id: str,
        user_context: Optional[UserContext] = None,
        target_category: Optional[str] = None
    ) -> IngestionResult:
        """
        アップロードファイル群を処理
        
        Args:
            uploaded_files: アップロードされたファイル一覧
            job_id: ジョブ追跡用ID
            user_context: ユーザーコンテキスト
            target_category: 'dataset', 'paper', 'poster'
            
        Returns:
            IngestionResult: 処理結果
            
        Claude Code実装例：
        ```python
        async def process_uploads(self, uploaded_files, job_id, user_context=None, target_category=None):
            result = IngestionResult(
                job_id=job_id,
                status=JobStatus.RUNNING,
                total_files=len(uploaded_files),
                processed_files=0,
                successful_files=0,
                failed_files=0,
                start_time=datetime.now()
            )
            
            for file in uploaded_files:
                try:
                    # ファイル検証
                    await self._validate_file(file)
                    
                    # 一時保存
                    temp_path = await self._save_temporary(file)
                    
                    # 既存システムで処理
                    await self._process_with_existing_system(temp_path, target_category)
                    
                    result.successful_files += 1
                except Exception as e:
                    result.errors.append(f"{file.filename}: {e}")
                    result.failed_files += 1
                finally:
                    result.processed_files += 1
                    # プログレス更新
            
            result.status = JobStatus.COMPLETED
            result.end_time = datetime.now()
            return result
        ```
        """
        pass
    
    @abstractmethod
    async def validate_file(
        self,
        file: Any,
        user_context: Optional[UserContext] = None
    ) -> bool:
        """
        アップロードファイルの検証
        
        Args:
            file: アップロードファイル
            user_context: ユーザーコンテキスト
            
        Returns:
            bool: 検証通過可否
            
        Raises:
            InputError: 検証失敗時
            
        Claude Code実装時の検証項目：
        - ファイルサイズ制限
        - ファイル形式チェック
        - ウイルススキャン（可能であれば）
        - ユーザー権限チェック
        """
        pass
    
    @abstractmethod
    async def get_upload_progress(self, job_id: str) -> Dict[str, Any]:
        """
        アップロード進行状況取得
        
        Returns:
            Dict: {'total': 10, 'completed': 7, 'failed': 1, 'percentage': 70.0}
        """
        pass
    
    @abstractmethod
    async def cleanup_temporary_files(self, job_id: str) -> bool:
        """
        一時ファイルのクリーンアップ
        
        Claude Code実装時の注意：
        - 処理完了後の一時ファイル削除
        - エラー時のロールバック処理
        """
        pass


# ========================================
# Implementation Helper Classes
# ========================================

class InputPortRegistry:
    """
    入力ポートの統合管理クラス
    
    Claude Code実装時の注意：
    - 各ポートの実装を登録・管理
    - ファクトリーパターンで実装選択
    - 設定に基づく有効/無効切り替え
    """
    
    def __init__(self):
        self._ports: Dict[str, DocumentInputPort] = {}
        self._google_drive_port: Optional[GoogleDrivePort] = None
        self._upload_port: Optional[FileUploadPort] = None
    
    def register_google_drive_port(self, port: GoogleDrivePort):
        """Google Driveポート登録"""
        self._google_drive_port = port
    
    def register_upload_port(self, port: FileUploadPort):
        """アップロードポート登録"""
        self._upload_port = port
    
    def get_available_ports(self) -> List[str]:
        """利用可能ポート一覧"""
        ports = []
        if self._google_drive_port:
            ports.append('google_drive')
        if self._upload_port:
            ports.append('upload')
        return ports


# ========================================
# Utility Functions for Claude Code
# ========================================

async def integrate_with_existing_indexer(
    file_path: str,
    category: Optional[str] = None,
    target_name: Optional[str] = None
) -> bool:
    """
    既存NewFileIndexerとの連携ヘルパー
    
    Args:
        file_path: 処理対象ファイルパス（一時ファイル）
        category: 'dataset', 'paper', 'poster' または None（自動判定）
        target_name: ファイル名（Google Drive等での元ファイル名）
    
    Returns:
        bool: 統合成功可否
    
    Claude Code実装時の使用例：
    ```python
    # Google Driveからダウンロードしたファイルを既存システムで処理
    success = await integrate_with_existing_indexer(
        '/tmp/downloaded_file.pdf', 
        'paper',
        'research_paper.pdf'
    )
    ```
    """
    try:
        import shutil
        from pathlib import Path
        from ..indexer.new_indexer import NewFileIndexer
        
        source_path = Path(file_path)
        if not source_path.exists():
            raise InputError(f"Source file not found: {file_path}")
        
        # ファイル名決定
        final_filename = target_name or source_path.name
        
        # カテゴリ判定
        if not category:
            category = _determine_file_category(final_filename, source_path)
        
        # 適切なディレクトリにファイル配置
        target_path = _get_target_path(category, final_filename)
        
        # ディレクトリ作成
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # ファイル移動（同名ファイルがある場合は上書き回避）
        if target_path.exists():
            stem = target_path.stem
            suffix = target_path.suffix
            counter = 1
            while target_path.exists():
                target_path = target_path.parent / f"{stem}_{counter}{suffix}"
                counter += 1
        
        # ファイルコピー
        shutil.copy2(source_path, target_path)
        
        # NewFileIndexerで直接処理
        indexer = NewFileIndexer(auto_analyze=True)
        
        # 単一ファイルのスキャン・インデックス処理
        if category == "dataset":
            # データセットの場合は全体を再スキャン（データセット単位管理のため）
            results = indexer.index_all_files()
        else:
            # 論文・ポスターの場合は個別処理
            # 新構造用ファイルオブジェクト作成
            file_obj = _create_new_file_object(target_path, category)
            
            if category == "paper":
                success = indexer._process_paper(file_obj)
            elif category == "poster":
                success = indexer._process_poster(file_obj)
            else:
                raise InputError(f"Unsupported category: {category}")
            
            if not success:
                raise InputError(f"Failed to process {category} file")
        
        import logging
        logging.info(f"Successfully integrated file: {final_filename} -> {target_path} ({category})")
        return True
        
    except Exception as e:
        import logging
        logging.error(f"Failed to integrate with existing indexer: {e}")
        raise InputError(f"Failed to integrate with existing indexer: {e}")


def _determine_file_category(filename: str, file_path: Path) -> str:
    """
    ファイル名・パス・拡張子からカテゴリを自動判定
    
    Args:
        filename: ファイル名
        file_path: ファイルパス
        
    Returns:
        str: 'dataset', 'paper', 'poster'
    """
    filename_lower = filename.lower()
    extension = file_path.suffix.lower()
    
    # データセット判定（優先）
    dataset_keywords = ['dataset', 'data', 'csv', 'json', 'jsonl']
    if (extension in ['.csv', '.json', '.jsonl'] or 
        any(keyword in filename_lower for keyword in dataset_keywords)):
        return 'dataset'
    
    # ポスター判定
    poster_keywords = ['poster', 'presentation', 'slide']
    if any(keyword in filename_lower for keyword in poster_keywords):
        return 'poster'
    
    # 論文判定（PDFデフォルト）
    paper_keywords = ['paper', 'thesis', 'research', 'journal', 'conference']
    if (extension == '.pdf' or 
        any(keyword in filename_lower for keyword in paper_keywords)):
        return 'paper'
    
    # デフォルト判定
    if extension == '.pdf':
        return 'paper'
    else:
        return 'dataset'


def _get_target_path(category: str, filename: str) -> Path:
    """
    カテゴリに基づく配置先パス取得
    
    Args:
        category: ファイルカテゴリ
        filename: ファイル名
        
    Returns:
        Path: 配置先パス
    """
    from pathlib import Path
    import os
    
    # DATA_DIRを取得（既存config.pyと統合）
    data_dir = Path(os.getenv("DATA_DIR_PATH", "data"))
    
    if category == "dataset":
        # データセットは専用ディレクトリに配置
        # ファイル名からデータセット名を抽出
        dataset_name = _extract_dataset_name(filename)
        return data_dir / "datasets" / dataset_name / filename
    elif category == "paper":
        return data_dir / "paper" / filename
    elif category == "poster":
        return data_dir / "poster" / filename
    else:
        raise InputError(f"Unknown category: {category}")


def _extract_dataset_name(filename: str) -> str:
    """
    ファイル名からデータセット名を抽出
    
    Args:
        filename: ファイル名
        
    Returns:
        str: データセット名
    """
    # 拡張子を除去
    stem = Path(filename).stem
    
    # 一般的なデータセット命名パターンの処理
    # 例: "esg_data_2024.csv" -> "esg_data"
    # 例: "research_dataset_v1.json" -> "research_dataset" 
    
    # 数字・バージョン文字列を除去
    import re
    # _v1, _2024, -final などの末尾パターンを除去
    cleaned = re.sub(r'[_-](v?\d+|final|temp|test|sample)$', '', stem, flags=re.IGNORECASE)
    
    # 空になった場合は元の名前を使用
    if not cleaned:
        cleaned = stem
    
    # アンダースコアをハイフンに統一（ディレクトリ名として安全）
    dataset_name = cleaned.replace('_', '-').lower()
    
    return dataset_name


def _create_new_file_object(file_path: Path, category: str):
    """
    新構造のファイルオブジェクト作成
    
    Args:
        file_path: ファイルパス
        category: ファイルカテゴリ
        
    Returns:
        ファイルオブジェクト（既存のFile互換）
    """
    from datetime import datetime
    import hashlib
    
    try:
        stat = file_path.stat()
        
        # ファイルハッシュ計算
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        content_hash = sha256_hash.hexdigest()
        
        # 既存のFileクラス互換オブジェクト作成
        class FileObject:
            def __init__(self, file_path, file_name, file_size, created_at, updated_at, content_hash, category):
                self.file_path = str(file_path)
                self.file_name = file_name
                self.file_size = file_size
                self.created_at = created_at
                self.updated_at = updated_at
                self.content_hash = content_hash
                self.category = category
        
        return FileObject(
            file_path=str(file_path.absolute()),
            file_name=file_path.name,
            file_size=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            updated_at=datetime.fromtimestamp(stat.st_mtime),
            content_hash=content_hash,
            category=category
        )
        
    except Exception as e:
        import logging
        logging.error(f"Failed to create file object: {file_path}, error: {e}")
        raise InputError(f"Failed to create file object: {e}")


def create_temp_file_path(job_id: str, original_filename: str) -> Path:
    """
    一時ファイルパス生成
    
    Claude Code実装ガイダンス：
    - /tmp/paas_temp/{job_id}/ 配下に配置
    - 元ファイル名を保持
    - 重複回避のためのUUID追加
    """
    import uuid
    from pathlib import Path
    
    temp_dir = Path(f"/tmp/paas_temp/{job_id}")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # ファイル名の重複回避
    stem = Path(original_filename).stem
    suffix = Path(original_filename).suffix
    unique_filename = f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"
    
    return temp_dir / unique_filename