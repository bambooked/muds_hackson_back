# Instance G: Google Drive実装完成 - 実装指示書

## 🎯 ミッション概要

**WHY**: 研究室のGoogle Driveとの連携がこのシステムの核心機能。現在70%実装済みだが、認証フローとAPIエンドポイントが未完成。これを完成させることで、研究データの自動取り込みが可能になり、手動でのファイル管理が不要になる。研究者は「Google Driveのこのフォルダを同期」するだけで、AIによる自動解析とRAG検索が利用できるようになる。

**WHAT**: GoogleDrivePortImplの完全実装、OAuth2認証フロー完成、APIエンドポイント追加、既存インデクサーとの統合により、Google Driveからの自動文書取り込みシステムを完成させる。

**HOW**: 既存の実装基盤（70%完成）を活用し、Google Drive API v3との連携、ファイルダウンロード、既存NewFileIndexerとの統合を段階的に実装する。

## 📋 実装タスク一覧

### **タスク G1: GoogleDrivePortImpl完全実装** [最優先]

#### 現在の状況
- `agent/source/interfaces/google_drive_impl.py` に基盤コード存在
- Google Drive API依存関係インストール済み
- 認証フローとファイル同期の具体実装が必要

#### 実装対象ファイル
`agent/source/interfaces/google_drive_impl.py`

#### 実装内容

**1. 認証機能の完成:**
```python
async def authenticate(
    self, 
    credentials: Dict[str, Any],
    user_context: Optional[UserContext] = None
) -> bool:
    """Google Drive認証実装"""
    if not GOOGLE_DRIVE_AVAILABLE:
        logging.warning("Google Drive API not available - authentication skipped")
        return False
    
    try:
        # Google OAuth2フロー実装
        client_config = {
            "web": {
                "client_id": credentials.get("client_id") or os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": credentials.get("client_secret") or os.getenv("GOOGLE_CLIENT_SECRET"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [credentials.get("redirect_uri", "http://localhost:8000/api/auth/callback")]
            }
        }
        
        flow = Flow.from_client_config(
            client_config,
            scopes=[
                'https://www.googleapis.com/auth/drive.readonly',
                'https://www.googleapis.com/auth/drive.metadata.readonly'
            ]
        )
        flow.redirect_uri = client_config["web"]["redirect_uris"][0]
        
        # 認証コードがある場合はトークン交換
        if "code" in credentials:
            flow.fetch_token(code=credentials["code"])
            self.credentials = flow.credentials
            
            # Google Drive APIサービス初期化
            self.service = build('drive', 'v3', credentials=self.credentials)
            
            logging.info("Google Drive認証成功")
            return True
        else:
            # 認証URL生成（初回認証時）
            auth_url, _ = flow.authorization_url(prompt='consent')
            raise InputError(f"認証が必要です。次のURLにアクセスしてください: {auth_url}")
            
    except Exception as e:
        logging.error(f"Google Drive認証エラー: {e}")
        raise InputError(f"Google Drive authentication failed: {e}")

def _ensure_authenticated(self):
    """認証状態確認"""
    if not self.service:
        raise InputError("Google Drive認証が必要です")
```

**2. フォルダ操作機能:**
```python
async def list_folders(
    self,
    parent_folder_id: Optional[str] = None,
    user_context: Optional[UserContext] = None
) -> List[Dict[str, Any]]:
    """Google Driveフォルダ一覧取得"""
    self._ensure_authenticated()
    
    try:
        # フォルダ検索クエリ
        query = "mimeType='application/vnd.google-apps.folder'"
        if parent_folder_id:
            query += f" and '{parent_folder_id}' in parents"
        else:
            query += " and 'root' in parents"
        
        # Google Drive API呼び出し
        results = self.service.files().list(
            q=query,
            pageSize=100,
            fields="nextPageToken, files(id, name, modifiedTime, size, parents)"
        ).execute()
        
        folders = []
        for item in results.get('files', []):
            folders.append({
                'id': item['id'],
                'name': item['name'],
                'type': 'folder',
                'modified_time': item.get('modifiedTime'),
                'parent_id': parent_folder_id
            })
        
        logging.info(f"フォルダ一覧取得成功: {len(folders)}件")
        return folders
        
    except Exception as e:
        logging.error(f"フォルダ一覧取得エラー: {e}")
        raise InputError(f"Failed to list folders: {e}")

async def get_file_metadata(
    self,
    file_id: str,
    user_context: Optional[UserContext] = None
) -> Dict[str, Any]:
    """ファイルメタデータ取得"""
    self._ensure_authenticated()
    
    try:
        file_metadata = self.service.files().get(
            fileId=file_id,
            fields="id, name, size, mimeType, modifiedTime, parents, webViewLink"
        ).execute()
        
        return {
            'id': file_metadata['id'],
            'name': file_metadata['name'],
            'size': int(file_metadata.get('size', 0)),
            'mimeType': file_metadata['mimeType'],
            'modified_time': file_metadata.get('modifiedTime'),
            'parents': file_metadata.get('parents', []),
            'web_view_link': file_metadata.get('webViewLink')
        }
        
    except Exception as e:
        logging.error(f"ファイルメタデータ取得エラー: {e}")
        raise InputError(f"Failed to get file metadata: {e}")
```

**3. ファイルダウンロード機能:**
```python
async def download_file(
    self,
    file_id: str,
    target_path: Path,
    user_context: Optional[UserContext] = None
) -> DocumentContent:
    """Google Driveファイルダウンロード"""
    self._ensure_authenticated()
    
    try:
        # ファイルメタデータ取得
        file_metadata = await self.get_file_metadata(file_id, user_context)
        
        # サポート形式チェック
        file_name = file_metadata['name']
        file_extension = Path(file_name).suffix.lower()
        supported_extensions = ['.pdf', '.csv', '.json', '.jsonl']
        
        if file_extension not in supported_extensions:
            raise InputError(f"サポートされていないファイル形式: {file_extension}")
        
        # ファイルダウンロード
        request = self.service.files().get_media(fileId=file_id)
        
        # ダウンロード実行
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(target_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                if status:
                    logging.info(f"ダウンロード進捗: {int(status.progress() * 100)}%")
        
        # DocumentContent作成
        file_stat = target_path.stat()
        
        return DocumentContent(
            file_id=file_id,
            file_name=file_name,
            file_path=str(target_path),
            file_size=file_stat.st_size,
            mime_type=file_metadata['mimeType'],
            source='google_drive',
            metadata={
                'google_drive_id': file_id,
                'modified_time': file_metadata.get('modified_time'),
                'web_view_link': file_metadata.get('web_view_link')
            }
        )
        
    except Exception as e:
        logging.error(f"ファイルダウンロードエラー: {e}")
        raise InputError(f"Failed to download file: {e}")
```

**4. フォルダ同期機能（メイン機能）:**
```python
async def sync_folder(
    self,
    folder_id: str,
    job_id: str,
    user_context: Optional[UserContext] = None,
    recursive: bool = True
) -> IngestionResult:
    """指定フォルダの同期実行"""
    self._ensure_authenticated()
    
    start_time = datetime.now()
    result = IngestionResult(
        job_id=job_id,
        status=JobStatus.RUNNING,
        total_files=0,
        processed_files=0,
        successful_files=0,
        failed_files=0,
        start_time=start_time,
        errors=[]
    )
    
    try:
        logging.info(f"Google Drive同期開始: フォルダID={folder_id}")
        
        # フォルダ内ファイル一覧取得
        files_to_sync = await self._get_folder_files(folder_id, recursive)
        result.total_files = len(files_to_sync)
        
        logging.info(f"同期対象ファイル: {result.total_files}件")
        
        # ジョブレジストリに登録
        self.job_registry[job_id] = result
        
        # 各ファイルを処理
        for file_info in files_to_sync:
            try:
                await self._process_single_file(file_info, job_id, result)
                result.successful_files += 1
                
            except Exception as file_error:
                error_msg = f"ファイル処理エラー [{file_info['name']}]: {file_error}"
                result.errors.append(error_msg)
                result.failed_files += 1
                logging.error(error_msg)
                
            finally:
                result.processed_files += 1
                
                # プログレス更新
                progress_percentage = (result.processed_files / result.total_files) * 100
                logging.info(f"同期進捗: {result.processed_files}/{result.total_files} ({progress_percentage:.1f}%)")
        
        # 完了処理
        result.status = JobStatus.COMPLETED
        result.end_time = datetime.now()
        
        logging.info(f"Google Drive同期完了: 成功={result.successful_files}, 失敗={result.failed_files}")
        
        return result
        
    except Exception as e:
        result.status = JobStatus.FAILED
        result.end_time = datetime.now()
        result.errors.append(f"同期処理エラー: {e}")
        logging.error(f"Google Drive同期失敗: {e}")
        
        return result

async def _get_folder_files(self, folder_id: str, recursive: bool = True) -> List[Dict[str, Any]]:
    """フォルダ内ファイル一覧取得（再帰対応）"""
    files = []
    
    # サポートファイル形式のクエリ
    mime_types = [
        "mimeType='application/pdf'",
        "mimeType='text/csv'", 
        "mimeType='application/json'",
        "name contains '.jsonl'"
    ]
    
    query = f"(({' or '.join(mime_types)}) and '{folder_id}' in parents and trashed=false)"
    
    try:
        results = self.service.files().list(
            q=query,
            pageSize=1000,
            fields="nextPageToken, files(id, name, size, mimeType, modifiedTime, parents)"
        ).execute()
        
        for item in results.get('files', []):
            files.append({
                'id': item['id'],
                'name': item['name'],
                'size': int(item.get('size', 0)),
                'mime_type': item['mimeType'],
                'modified_time': item.get('modifiedTime'),
                'parent_folder_id': folder_id
            })
        
        # 再帰的にサブフォルダも処理
        if recursive:
            subfolders = await self.list_folders(folder_id)
            for subfolder in subfolders:
                subfolder_files = await self._get_folder_files(subfolder['id'], recursive)
                files.extend(subfolder_files)
        
        return files
        
    except Exception as e:
        logging.error(f"フォルダファイル一覧取得エラー: {e}")
        raise InputError(f"Failed to get folder files: {e}")

async def _process_single_file(self, file_info: Dict[str, Any], job_id: str, result: IngestionResult):
    """単一ファイルの処理"""
    from .input_ports import integrate_with_existing_indexer, create_temp_file_path
    
    file_id = file_info['id']
    file_name = file_info['name']
    
    try:
        # 一時ファイルパス生成
        temp_path = create_temp_file_path(job_id, file_name)
        
        # ファイルダウンロード
        document_content = await self.download_file(file_id, temp_path)
        
        # 既存システムとの統合（自動解析実行）
        success = await integrate_with_existing_indexer(
            file_path=str(temp_path),
            target_name=file_name
        )
        
        if success:
            logging.info(f"ファイル処理成功: {file_name}")
        else:
            raise Exception("既存システムとの統合に失敗")
            
        # 一時ファイル削除
        if temp_path.exists():
            temp_path.unlink()
            
    except Exception as e:
        # 一時ファイルクリーンアップ
        temp_path = create_temp_file_path(job_id, file_name)
        if temp_path.exists():
            temp_path.unlink()
        raise e
```

### **タスク G2: APIエンドポイント実装** [高優先度]

#### 実装対象ファイル
`services/api/paas_api.py`

#### 実装内容

**必要なインポート追加:**
```python
from agent.source.interfaces.google_drive_impl import GoogleDrivePortImpl
from agent.source.interfaces.data_models import GoogleDriveConfig, IngestionResult, JobStatus
```

**Google Drive設定とサービス初期化:**
```python
# Google Drive設定（アプリケーション起動時）
google_drive_service = None

@app.on_event("startup")
async def initialize_google_drive():
    """Google Drive サービス初期化"""
    global google_drive_service
    
    google_drive_enabled = os.getenv('PAAS_ENABLE_GOOGLE_DRIVE', 'false').lower() == 'true'
    
    if google_drive_enabled:
        try:
            config = GoogleDriveConfig(
                enabled=True,
                client_id=os.getenv('GOOGLE_CLIENT_ID'),
                client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
                scopes=[
                    'https://www.googleapis.com/auth/drive.readonly',
                    'https://www.googleapis.com/auth/drive.metadata.readonly'
                ]
            )
            
            google_drive_service = GoogleDrivePortImpl(config)
            logger.info("Google Drive サービス初期化完了")
            
        except Exception as e:
            logger.error(f"Google Drive サービス初期化失敗: {e}")
    else:
        logger.info("Google Drive機能は無効化されています")

def get_google_drive_service():
    """Google Drive サービス取得"""
    if not google_drive_service:
        raise HTTPException(status_code=503, detail="Google Drive service not available")
    return google_drive_service
```

**Google Drive認証エンドポイント:**
```python
@app.get("/api/google-drive/auth/start", tags=["google-drive"])
async def start_google_drive_auth(
    redirect_uri: str = "http://localhost:8000/api/google-drive/auth/callback",
    current_user = Depends(get_current_user)
):
    """
    Google Drive認証開始
    
    Args:
        redirect_uri: 認証完了後のリダイレクトURI
        current_user: 認証済みユーザー
    """
    try:
        service = get_google_drive_service()
        
        # 認証URL生成のため、一時的に例外をキャッチ
        credentials = {
            "client_id": os.getenv('GOOGLE_CLIENT_ID'),
            "client_secret": os.getenv('GOOGLE_CLIENT_SECRET'),
            "redirect_uri": redirect_uri
        }
        
        try:
            await service.authenticate(credentials, current_user)
        except InputError as e:
            # 認証URLが含まれている場合は返却
            if "次のURLにアクセス" in str(e):
                auth_url = str(e).split(": ")[-1]
                return {
                    "auth_url": auth_url,
                    "redirect_uri": redirect_uri,
                    "message": "Google Drive認証が必要です"
                }
            raise HTTPException(status_code=400, detail=str(e))
        
        return {"message": "Google Drive認証済み"}
        
    except Exception as e:
        logger.error(f"Google Drive認証開始エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/google-drive/auth/callback", tags=["google-drive"])
async def google_drive_auth_callback(
    code: str,
    current_user = Depends(get_current_user)
):
    """
    Google Drive認証コールバック
    
    Args:
        code: Google OAuth2認証コード
        current_user: 認証済みユーザー
    """
    try:
        service = get_google_drive_service()
        
        credentials = {
            "code": code,
            "client_id": os.getenv('GOOGLE_CLIENT_ID'),
            "client_secret": os.getenv('GOOGLE_CLIENT_SECRET'),
            "redirect_uri": "http://localhost:8000/api/google-drive/auth/callback"
        }
        
        success = await service.authenticate(credentials, current_user)
        
        if success:
            return {
                "message": "Google Drive認証成功",
                "user": current_user["email"],
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=400, detail="認証に失敗しました")
            
    except Exception as e:
        logger.error(f"Google Drive認証コールバックエラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**フォルダ操作エンドポイント:**
```python
@app.get("/api/google-drive/folders", tags=["google-drive"])
async def list_google_drive_folders(
    parent_id: Optional[str] = None,
    current_user = Depends(get_current_user)
):
    """
    Google Drive フォルダ一覧取得
    
    Args:
        parent_id: 親フォルダID（Noneの場合はルート）
        current_user: 認証済みユーザー
    """
    try:
        service = get_google_drive_service()
        folders = await service.list_folders(parent_id, current_user)
        
        return {
            "folders": folders,
            "parent_id": parent_id,
            "count": len(folders),
            "user": current_user["email"]
        }
        
    except InputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"フォルダ一覧取得エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/google-drive/folders/{folder_id}/files", tags=["google-drive"])
async def list_folder_files(
    folder_id: str,
    recursive: bool = False,
    current_user = Depends(get_current_user)
):
    """
    指定フォルダ内のファイル一覧取得
    
    Args:
        folder_id: フォルダID
        recursive: サブフォルダも含めるか
        current_user: 認証済みユーザー
    """
    try:
        service = get_google_drive_service()
        files = await service._get_folder_files(folder_id, recursive)
        
        return {
            "files": files,
            "folder_id": folder_id,
            "count": len(files),
            "recursive": recursive,
            "user": current_user["email"]
        }
        
    except Exception as e:
        logger.error(f"フォルダファイル一覧取得エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**同期機能エンドポイント:**
```python
# グローバル変数（ジョブ管理）
sync_jobs: Dict[str, IngestionResult] = {}

@app.post("/api/google-drive/sync/start", tags=["google-drive"])
async def start_google_drive_sync(
    folder_id: str,
    recursive: bool = True,
    current_user = Depends(get_current_user)
):
    """
    Google Drive フォルダ同期開始
    
    Args:
        folder_id: 同期するフォルダID
        recursive: サブフォルダも同期するか
        current_user: 認証済みユーザー
    """
    try:
        service = get_google_drive_service()
        
        # ジョブID生成
        job_id = f"gdrive_sync_{current_user['user_id']}_{int(datetime.now().timestamp())}"
        
        # バックグラウンドで同期実行
        import asyncio
        
        async def run_sync():
            try:
                result = await service.sync_folder(
                    folder_id=folder_id,
                    job_id=job_id,
                    user_context=current_user,
                    recursive=recursive
                )
                sync_jobs[job_id] = result
                
            except Exception as e:
                # エラー結果をジョブに記録
                error_result = IngestionResult(
                    job_id=job_id,
                    status=JobStatus.FAILED,
                    total_files=0,
                    processed_files=0,
                    successful_files=0,
                    failed_files=0,
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    errors=[str(e)]
                )
                sync_jobs[job_id] = error_result
        
        # 非同期実行開始
        asyncio.create_task(run_sync())
        
        # 初期ジョブ状態を作成
        initial_result = IngestionResult(
            job_id=job_id,
            status=JobStatus.RUNNING,
            total_files=0,
            processed_files=0,
            successful_files=0,
            failed_files=0,
            start_time=datetime.now(),
            errors=[]
        )
        sync_jobs[job_id] = initial_result
        
        return {
            "job_id": job_id,
            "status": "started",
            "folder_id": folder_id,
            "recursive": recursive,
            "user": current_user["email"],
            "message": "同期を開始しました。進捗はjob_idで確認できます。"
        }
        
    except Exception as e:
        logger.error(f"Google Drive同期開始エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sync/jobs/{job_id}", tags=["google-drive"])
async def get_sync_job_status(
    job_id: str,
    current_user = Depends(get_current_user_optional)
):
    """
    同期ジョブの状態取得
    
    Args:
        job_id: ジョブID
        current_user: 認証済みユーザー（オプション）
    """
    if job_id not in sync_jobs:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    
    result = sync_jobs[job_id]
    
    # 進捗計算
    progress_percentage = 0
    if result.total_files > 0:
        progress_percentage = (result.processed_files / result.total_files) * 100
    
    return {
        "job_id": job_id,
        "status": result.status.value,
        "progress": {
            "total_files": result.total_files,
            "processed_files": result.processed_files,
            "successful_files": result.successful_files,
            "failed_files": result.failed_files,
            "percentage": round(progress_percentage, 1)
        },
        "timing": {
            "start_time": result.start_time.isoformat() if result.start_time else None,
            "end_time": result.end_time.isoformat() if result.end_time else None,
            "duration_seconds": (
                (result.end_time - result.start_time).total_seconds()
                if result.end_time and result.start_time else None
            )
        },
        "errors": result.errors[-5:] if result.errors else [],  # 最新5件のエラー
        "user": current_user["email"] if current_user else "anonymous"
    }

@app.delete("/api/sync/jobs/{job_id}", tags=["google-drive"])
async def cancel_sync_job(
    job_id: str,
    current_user = Depends(get_current_user)
):
    """
    同期ジョブのキャンセル
    
    Args:
        job_id: キャンセルするジョブID
        current_user: 認証済みユーザー
    """
    if job_id not in sync_jobs:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    
    result = sync_jobs[job_id]
    
    if result.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
        raise HTTPException(status_code=400, detail="既に完了したジョブはキャンセルできません")
    
    # ジョブキャンセル（簡易実装）
    result.status = JobStatus.FAILED
    result.end_time = datetime.now()
    result.errors.append("ユーザーによりキャンセルされました")
    
    return {
        "job_id": job_id,
        "status": "cancelled",
        "message": "ジョブをキャンセルしました",
        "user": current_user["email"]
    }
```

### **タスク G3: 統合テスト機能** [中優先度]

#### 実装対象ファイル
`services/api/paas_api.py`

#### 実装内容

**Google Drive テスト用エンドポイント:**
```python
@app.get("/api/google-drive/test/connection", tags=["google-drive"])
async def test_google_drive_connection(
    current_user = Depends(get_current_user)
):
    """
    Google Drive接続テスト
    
    認証状態とAPI接続をテストします
    """
    try:
        service = get_google_drive_service()
        
        # 基本的な接続テスト（ルートフォルダ取得）
        folders = await service.list_folders(None, current_user)
        
        return {
            "status": "success",
            "message": "Google Drive接続正常",
            "root_folders_count": len(folders),
            "user": current_user["email"],
            "timestamp": datetime.now().isoformat()
        }
        
    except InputError as e:
        if "認証が必要" in str(e):
            return {
                "status": "authentication_required",
                "message": "Google Drive認証が必要です",
                "auth_endpoint": "/api/google-drive/auth/start"
            }
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        logger.error(f"Google Drive接続テストエラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/google-drive/test/small-sync", tags=["google-drive"])
async def test_small_sync(
    folder_id: str,
    max_files: int = 3,
    current_user = Depends(get_current_user)
):
    """
    小規模同期テスト
    
    指定フォルダから最大3ファイルのテスト同期を実行
    """
    try:
        service = get_google_drive_service()
        
        # ファイル一覧取得
        files = await service._get_folder_files(folder_id, recursive=False)
        
        if not files:
            return {
                "status": "no_files",
                "message": "同期対象ファイルが見つかりません",
                "folder_id": folder_id
            }
        
        # 最大ファイル数制限
        test_files = files[:max_files]
        
        # テスト用ジョブID
        job_id = f"test_sync_{current_user['user_id']}_{int(datetime.now().timestamp())}"
        
        # 小規模同期実行
        result = IngestionResult(
            job_id=job_id,
            status=JobStatus.RUNNING,
            total_files=len(test_files),
            processed_files=0,
            successful_files=0,
            failed_files=0,
            start_time=datetime.now(),
            errors=[]
        )
        
        # 各ファイルを順次処理
        for file_info in test_files:
            try:
                await service._process_single_file(file_info, job_id, result)
                result.successful_files += 1
                
            except Exception as file_error:
                result.errors.append(f"ファイル処理エラー [{file_info['name']}]: {file_error}")
                result.failed_files += 1
                
            finally:
                result.processed_files += 1
        
        result.status = JobStatus.COMPLETED
        result.end_time = datetime.now()
        
        return {
            "status": "completed",
            "message": "テスト同期完了",
            "result": {
                "total_files": result.total_files,
                "successful_files": result.successful_files,
                "failed_files": result.failed_files,
                "errors": result.errors
            },
            "processed_files": [f["name"] for f in test_files],
            "user": current_user["email"]
        }
        
    except Exception as e:
        logger.error(f"テスト同期エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

## 🧪 テスト手順

### **段階1: Google Drive API設定**
```bash
# 環境変数設定
export PAAS_ENABLE_GOOGLE_DRIVE=true
export GOOGLE_CLIENT_ID="your_google_client_id"
export GOOGLE_CLIENT_SECRET="your_google_client_secret"

# サーバー起動
uv run python services/api/paas_api.py
```

### **段階2: 認証テスト**
1. `http://localhost:8000/docs` にアクセス
2. `/api/auth/dev-login` で認証
3. `/api/google-drive/test/connection` で接続テスト
4. 認証が必要な場合は `/api/google-drive/auth/start` を実行

### **段階3: フォルダ操作テスト**
```bash
# フォルダ一覧取得
curl -X GET "http://localhost:8000/api/google-drive/folders" \
     -H "Authorization: Bearer $JWT_TOKEN"

# 特定フォルダのファイル一覧
curl -X GET "http://localhost:8000/api/google-drive/folders/FOLDER_ID/files" \
     -H "Authorization: Bearer $JWT_TOKEN"
```

### **段階4: 同期機能テスト**
```bash
# 小規模テスト同期
curl -X POST "http://localhost:8000/api/google-drive/test/small-sync" \
     -H "Authorization: Bearer $JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"folder_id": "FOLDER_ID", "max_files": 2}'

# 本格同期開始
curl -X POST "http://localhost:8000/api/google-drive/sync/start" \
     -H "Authorization: Bearer $JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"folder_id": "FOLDER_ID", "recursive": true}'

# 同期状況確認
curl -X GET "http://localhost:8000/api/sync/jobs/JOB_ID" \
     -H "Authorization: Bearer $JWT_TOKEN"
```

## ⚠️ 重要な注意事項

### **1. Google Cloud Console設定**
- OAuth2 アプリケーションの登録が必要
- 適切なスコープ設定（drive.readonly）
- リダイレクトURIの正確な設定

### **2. セキュリティ**
- Google API認証情報の適切な管理
- ユーザーごとの認証状態分離
- ファイルアクセス権限の確認

### **3. エラーハンドリング**
- Google API制限への対応
- 大容量ファイルのタイムアウト処理
- 一時ファイルのクリーンアップ

### **4. パフォーマンス**
- 大量ファイル同期時の進捗追跡
- 非同期処理による応答性確保
- メモリ使用量の最適化

## 📊 成功基準

✅ **認証機能**: Google OAuth2認証が正常動作  
✅ **フォルダ操作**: フォルダ一覧・ファイル一覧取得が動作  
✅ **ファイルダウンロード**: Google Driveから正常にダウンロード  
✅ **既存システム統合**: ダウンロードファイルが自動解析される  
✅ **同期機能**: フォルダ全体の自動同期が動作  
✅ **プログレス追跡**: 同期進捗がリアルタイムで確認可能  

## ⏱️ 推定工数

- **G1 (GoogleDrivePortImpl実装)**: 6-8時間
- **G2 (APIエンドポイント)**: 4-6時間  
- **G3 (テスト機能)**: 2-3時間

**合計**: 約1.5日（12-17時間）

---

**Instance G完了により、研究室のGoogle Driveとの完全連携が実現し、手動ファイル管理が不要になります。**