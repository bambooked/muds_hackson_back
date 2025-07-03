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
    category: Optional[str] = None
) -> bool:
    """
    既存NewFileIndexerとの連携ヘルパー
    
    Claude Code実装時の使用例：
    ```python
    # Google Driveからダウンロードしたファイルを既存システムで処理
    success = await integrate_with_existing_indexer('/tmp/downloaded_file.pdf', 'paper')
    ```
    """
    try:
        # 既存システムへの橋渡し
        from ..ui.interface import UserInterface
        ui = UserInterface()
        
        # ファイルのカテゴリ自動判定または指定カテゴリ使用
        if category:
            # 指定カテゴリでの処理実装
            pass
        else:
            # 自動判定処理実装
            pass
        
        # インデックス更新実行
        ui.update_index()
        return True
        
    except Exception as e:
        raise InputError(f"Failed to integrate with existing indexer: {e}")


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