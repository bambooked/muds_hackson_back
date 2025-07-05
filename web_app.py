"""
研究データ管理システム Webアプリケーション
Google Drive連携、AI検索・研究相談機能付き
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.requests import Request
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import asyncio
import logging
from datetime import datetime

# 既存のコンポーネントをインポート
import sys
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv()

from agent.source.integrations.google_drive import GoogleDriveIntegration
from agent.source.integrations.auth import AuthenticationManager
from agent.source.database.connection import db_connection
from agent.source.database.new_repository import DatasetRepository, PaperRepository, PosterRepository
from agent.source.database.new_models import Dataset, Paper, Poster
from agent.source.advisor.enhanced_research_advisor import EnhancedResearchAdvisor
from agent.source.advisor.dataset_advisor import DatasetAdvisor
from agent.source.integrations.looker_export import LookerDataExporter

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPIアプリケーション初期化
app = FastAPI(
    title="研究データ管理システム",
    description="Google Drive連携とAI研究相談機能を備えた研究データ管理システム",
    version="1.0.0"
)

# 静的ファイルとテンプレート設定
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# グローバルインスタンス
google_drive = GoogleDriveIntegration()
auth_manager = AuthenticationManager()
enhanced_advisor = EnhancedResearchAdvisor()
dataset_advisor = DatasetAdvisor()
looker_exporter = LookerDataExporter(google_drive)

# リポジトリ
dataset_repo = DatasetRepository()
paper_repo = PaperRepository()
poster_repo = PosterRepository()

# リクエスト/レスポンスモデル
class GoogleDriveSyncRequest(BaseModel):
    folder_type: str  # "all", "datasets", "papers", "posters"

class SearchRequest(BaseModel):
    query: str
    search_type: str = "all"  # "all", "papers", "posters", "datasets"

class ResearchConsultationRequest(BaseModel):
    query: str
    consultation_type: str = "general"  # "general", "database", "planning"

class SyncResponse(BaseModel):
    success: bool
    message: str
    files_processed: int
    errors: List[str] = []

class SearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    total: int
    query: str

class ConsultationResponse(BaseModel):
    advice: str
    related_documents: List[Dict[str, Any]] = []
    relevant_datasets: List[Dict[str, Any]] = []
    next_actions: List[str] = []

class LookerExportRequest(BaseModel):
    """Looker Studio用エクスポートリクエスト"""
    export_type: str = "summary"  # Phase 1では"summary"のみ

class LookerExportResponse(BaseModel):
    """Looker Studio用エクスポートレスポンス"""
    success: bool
    message: str
    file_id: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None

# データベース初期化
@app.on_event("startup")
async def startup_event():
    """アプリケーション起動時の初期化"""
    logger.info("研究データ管理システム Webアプリ起動中...")
    
    # データベース初期化
    db_connection.initialize_database()
    logger.info("データベース初期化完了")
    
    # 統合機能確認
    integrations = []
    if google_drive.is_enabled():
        integrations.append("Google Drive")
    if auth_manager.is_enabled():
        integrations.append("認証システム")
    
    if integrations:
        logger.info(f"統合機能が有効: {', '.join(integrations)}")
    
    logger.info("研究データ管理システム Webアプリ起動完了")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """メインページ"""
    # システム状態確認
    system_status = {
        "google_drive": google_drive.is_enabled(),
        "auth": auth_manager.is_enabled(),
        "database": True
    }
    
    # 統計情報取得
    stats = {
        "papers": len(paper_repo.find_all()),
        "posters": len(poster_repo.find_all()),
        "datasets": len(dataset_repo.find_all())
    }
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "system_status": system_status,
        "stats": stats
    })

@app.get("/api/status")
async def get_system_status():
    """システム状態API"""
    return JSONResponse({
        "google_drive": google_drive.is_enabled(),
        "auth": auth_manager.is_enabled(),
        "database": True,
        "stats": {
            "papers": len(paper_repo.find_all()),
            "posters": len(poster_repo.find_all()),
            "datasets": len(dataset_repo.find_all())
        }
    })

@app.post("/api/sync/google-drive", response_model=SyncResponse)
async def sync_google_drive(request: GoogleDriveSyncRequest, background_tasks: BackgroundTasks):
    """Google Drive同期API"""
    if not google_drive.is_enabled():
        raise HTTPException(status_code=503, detail="Google Drive連携が無効です")
    
    try:
        # バックグラウンドで同期実行
        background_tasks.add_task(perform_google_drive_sync, request.folder_type)
        
        return SyncResponse(
            success=True,
            message="Google Drive同期を開始しました",
            files_processed=0
        )
    except Exception as e:
        logger.error(f"Google Drive同期エラー: {e}")
        raise HTTPException(status_code=500, detail=f"同期エラー: {str(e)}")

async def perform_google_drive_sync(folder_type: str):
    """Google Drive同期の実際の処理"""
    try:
        logger.info(f"Google Drive同期開始: {folder_type}")
        
        # フォルダ内のファイルを取得
        folders = google_drive.list_files()
        files_processed = 0
        errors = []
        
        for folder in folders:
            if folder.get('mimeType') == 'application/vnd.google-apps.folder':
                folder_name = folder['name']
                folder_id = folder['id']
                
                # フォルダタイプでフィルタ
                if folder_type != "all" and folder_name not in [folder_type, f"{folder_type}s"]:
                    continue
                
                # フォルダ内のファイルを処理
                files_in_folder = google_drive.list_files(folder_id=folder_id)
                
                if folder_name == 'datasets':
                    # datasetsフォルダの場合、サブフォルダを処理
                    dataset_files_count = await process_datasets_folder(files_in_folder)
                    files_processed += dataset_files_count
                else:
                    # 通常のフォルダ（paper, poster）の場合
                    for file in files_in_folder:
                        if file.get('mimeType') != 'application/vnd.google-apps.folder':
                            try:
                                await process_drive_file(file, folder_name)
                                files_processed += 1
                            except Exception as e:
                                errors.append(f"{file['name']}: {str(e)}")
        
        logger.info(f"Google Drive同期完了: {files_processed}ファイル処理, {len(errors)}エラー")
        
        # 統計情報を更新（キャッシュクリア効果）
        stats = {
            "papers": len(paper_repo.find_all()),
            "posters": len(poster_repo.find_all()),
            "datasets": len(dataset_repo.find_all())
        }
        logger.info(f"同期後統計: 論文{stats['papers']}件, ポスター{stats['posters']}件, データセット{stats['datasets']}件")
        
    except Exception as e:
        logger.error(f"Google Drive同期エラー: {e}")

async def process_datasets_folder(dataset_items: List[Dict[str, Any]]) -> int:
    """datasetsフォルダ内のサブフォルダを処理"""
    files_processed = 0
    
    for item in dataset_items:
        if item.get('mimeType') == 'application/vnd.google-apps.folder':
            # データセットサブフォルダ
            dataset_name = item['name']
            dataset_folder_id = item['id']
            
            logger.info(f"データセット処理開始: {dataset_name}")
            
            # データセットフォルダ内のファイルを取得
            dataset_files = google_drive.list_files(folder_id=dataset_folder_id)
            
            # 既存データセット確認
            existing_dataset = dataset_repo.find_by_name(dataset_name)
            
            dataset_file_list = []
            total_size = 0
            
            # ファイルを処理
            for file in dataset_files:
                if file.get('mimeType') != 'application/vnd.google-apps.folder':
                    file_info = {
                        'name': file['name'],
                        'id': file['id'],
                        'size': int(file.get('size', 0)),
                        'created_time': file.get('createdTime', ''),
                        'modified_time': file.get('modifiedTime', ''),
                        'mime_type': file.get('mimeType', '')
                    }
                    dataset_file_list.append(file_info)
                    total_size += file_info['size']
                    files_processed += 1
            
            if dataset_file_list:
                if existing_dataset:
                    # 既存データセットの更新
                    if existing_dataset.file_count != len(dataset_file_list) or existing_dataset.total_size != total_size:
                        existing_dataset.file_count = len(dataset_file_list)
                        existing_dataset.total_size = total_size
                        dataset_repo.update(existing_dataset)
                        logger.info(f"データセット更新: {dataset_name} ({len(dataset_file_list)}ファイル)")
                else:
                    # 新規データセット作成
                    new_dataset = Dataset(
                        name=dataset_name,
                        description=f"Google Driveから同期: {len(dataset_file_list)}ファイル",
                        file_count=len(dataset_file_list),
                        total_size=total_size
                    )
                    dataset_repo.create(new_dataset)
                    logger.info(f"データセット新規作成: {dataset_name} ({len(dataset_file_list)}ファイル)")
    
    return files_processed

async def process_drive_file(file: Dict[str, Any], folder_name: str):
    """個別ファイルの処理"""
    file_info = {
        'name': file['name'],
        'id': file['id'],
        'size': file.get('size', 0),
        'created_time': file.get('createdTime', ''),
        'modified_time': file.get('modifiedTime', ''),
        'mime_type': file.get('mimeType', '')
    }
    
    try:
        if folder_name == 'paper':
            # Google Drive IDをfile_pathとして使用
            drive_file_path = f"gdrive://paper/{file_info['id']}"
            
            # 既存確認（file_pathで重複チェック）
            existing_papers = paper_repo.find_all()
            if any(p.file_path == drive_file_path for p in existing_papers):
                logger.info(f"論文スキップ（既存）: {file_info['name']}")
                return
            
            # ファイル名での重複チェック（フォールバック）
            if any(p.file_name == file_info["name"] for p in existing_papers):
                logger.info(f"論文スキップ（同名ファイル）: {file_info['name']}")
                return
            
            # 論文として登録
            paper = Paper(
                file_path=drive_file_path,
                file_name=file_info["name"],
                title=file_info["name"].replace('.pdf', ''),
                authors='Google Drive File',
                abstract='Google Driveから取得されたファイル',
                keywords='',
                file_size=int(file_info.get('size', 0))
            )
            paper_repo.create(paper)
            logger.info(f"論文登録完了: {file_info['name']}")
            
        elif folder_name == 'poster':
            # Google Drive IDをfile_pathとして使用
            drive_file_path = f"gdrive://poster/{file_info['id']}"
            
            # 既存確認（file_pathで重複チェック）
            existing_posters = poster_repo.find_all()
            if any(p.file_path == drive_file_path for p in existing_posters):
                logger.info(f"ポスタースキップ（既存）: {file_info['name']}")
                return
            
            # ファイル名での重複チェック（フォールバック）
            if any(p.file_name == file_info["name"] for p in existing_posters):
                logger.info(f"ポスタースキップ（同名ファイル）: {file_info['name']}")
                return
            
            # ポスターとして登録
            poster = Poster(
                file_path=drive_file_path,
                file_name=file_info["name"],
                title=file_info["name"].replace('.pdf', ''),
                authors='Google Drive File',
                abstract='Google Driveから取得されたファイル',
                keywords='',
                file_size=int(file_info.get('size', 0))
            )
            poster_repo.create(poster)
            logger.info(f"ポスター登録完了: {file_info['name']}")
            
        elif folder_name == 'datasets':
            # datasetsフォルダの場合、これはサブフォルダなので処理をスキップ
            # サブフォルダの処理は perform_google_drive_sync で行う
            logger.info(f"データセットサブフォルダをスキップ: {file_info['name']}")
            return
            
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            logger.info(f"ファイル重複スキップ: {file_info['name']}")
        else:
            logger.error(f"ファイル処理エラー: {file_info['name']} - {e}")
            raise e  # 重複エラー以外は再発生

@app.post("/api/search", response_model=SearchResponse)
async def search_research_data(request: SearchRequest):
    """研究データ検索API"""
    try:
        results = []
        
        if request.search_type in ["all", "papers"]:
            papers = paper_repo.find_all()
            for paper in papers:
                if request.query.lower() in paper.file_name.lower() or \
                   (paper.title and request.query.lower() in paper.title.lower()):
                    results.append({
                        "type": "paper",
                        "id": paper.id,
                        "title": paper.title or paper.file_name,
                        "file_name": paper.file_name,
                        "authors": paper.authors,
                        "abstract": paper.abstract,
                        "file_size": paper.file_size
                    })
        
        if request.search_type in ["all", "posters"]:
            posters = poster_repo.find_all()
            for poster in posters:
                if request.query.lower() in poster.file_name.lower() or \
                   (poster.title and request.query.lower() in poster.title.lower()):
                    results.append({
                        "type": "poster",
                        "id": poster.id,
                        "title": poster.title or poster.file_name,
                        "file_name": poster.file_name,
                        "authors": poster.authors,
                        "abstract": poster.abstract,
                        "file_size": poster.file_size
                    })
        
        if request.search_type in ["all", "datasets"]:
            datasets = dataset_repo.find_all()
            for dataset in datasets:
                if request.query.lower() in dataset.name.lower():
                    results.append({
                        "type": "dataset",
                        "id": dataset.id,
                        "name": dataset.name,
                        "description": dataset.description,
                        "file_count": dataset.file_count,
                        "total_size": dataset.total_size
                    })
        
        return SearchResponse(
            results=results,
            total=len(results),
            query=request.query
        )
        
    except Exception as e:
        logger.error(f"検索エラー: {e}")
        raise HTTPException(status_code=500, detail=f"検索エラー: {str(e)}")

@app.post("/api/consultation", response_model=ConsultationResponse)
async def research_consultation(request: ResearchConsultationRequest):
    """AI研究相談API"""
    try:
        # 相談タイプを渡して適切な処理を実行
        result = enhanced_advisor.research_consultation(
            request.query, 
            consultation_type=request.consultation_type
        )
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return ConsultationResponse(
            advice=result.get("advice", ""),
            related_documents=result.get("related_documents", []),
            relevant_datasets=result.get("relevant_datasets", []),
            next_actions=result.get("next_actions", [])
        )
        
    except Exception as e:
        logger.error(f"研究相談エラー: {e}")
        raise HTTPException(status_code=500, detail=f"研究相談エラー: {str(e)}")

@app.get("/api/database/summary")
async def get_database_summary():
    """データベースの詳細な要約情報を取得"""
    try:
        # 論文情報
        papers = paper_repo.find_all()
        papers_summary = [
            {
                "id": p.id,
                "file_name": p.file_name,
                "title": p.title,
                "authors": p.authors,
                "abstract": p.abstract[:200] + "..." if p.abstract and len(p.abstract) > 200 else p.abstract,
                "keywords": p.keywords,
                "file_size": p.file_size
            }
            for p in papers
        ]
        
        # ポスター情報
        posters = poster_repo.find_all()
        posters_summary = [
            {
                "id": p.id,
                "file_name": p.file_name,
                "title": p.title,
                "authors": p.authors,
                "abstract": p.abstract[:200] + "..." if p.abstract and len(p.abstract) > 200 else p.abstract,
                "keywords": p.keywords,
                "file_size": p.file_size
            }
            for p in posters
        ]
        
        # データセット情報
        datasets = dataset_repo.find_all()
        datasets_summary = [
            {
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "summary": d.summary[:200] + "..." if d.summary and len(d.summary) > 200 else d.summary,
                "file_count": d.file_count,
                "total_size": d.total_size,
                "total_size_mb": round(d.total_size / (1024 * 1024), 2) if d.total_size else 0
            }
            for d in datasets
        ]
        
        return {
            "papers": {
                "count": len(papers),
                "items": papers_summary
            },
            "posters": {
                "count": len(posters),
                "items": posters_summary
            },
            "datasets": {
                "count": len(datasets),
                "items": datasets_summary
            },
            "totals": {
                "papers": len(papers),
                "posters": len(posters),
                "datasets": len(datasets),
                "total_items": len(papers) + len(posters) + len(datasets),
                "total_dataset_files": sum(d.file_count for d in datasets),
                "total_dataset_size_mb": round(sum(d.total_size for d in datasets) / (1024 * 1024), 2)
            }
        }
        
    except Exception as e:
        logger.error(f"データベース要約取得エラー: {e}")
        raise HTTPException(status_code=500, detail=f"データベース要約取得エラー: {str(e)}")

@app.get("/api/google-drive/status")
async def google_drive_status():
    """Google Drive状態確認API"""
    if not google_drive.is_enabled():
        return {"enabled": False, "message": "Google Drive連携が無効です"}
    
    try:
        # ストレージ情報取得
        storage_info = google_drive.get_storage_info()
        files = google_drive.list_files()
        
        storage_data = {}
        if storage_info:
            storage_data = {
                "limit_gb": storage_info['limit'] / (1024**3),
                "usage_gb": storage_info['usage'] / (1024**3),
                "usage_percent": (storage_info['usage'] / storage_info['limit']) * 100
            }
        
        return {
            "enabled": True,
            "storage": storage_data,
            "file_count": len(files),
            "folders": [f["name"] for f in files if f.get('mimeType') == 'application/vnd.google-apps.folder']
        }
        
    except Exception as e:
        logger.error(f"Google Drive状態取得エラー: {e}")
        return {"enabled": True, "error": str(e)}

@app.post("/api/looker-studio/export", response_model=LookerExportResponse)
async def export_for_looker_studio(request: LookerExportRequest):
    """Looker Studio用データをGoogle Driveにエクスポート"""
    try:
        if request.export_type != "summary":
            return LookerExportResponse(
                success=False,
                message="Phase 1ではsummaryエクスポートのみ対応しています"
            )
        
        # エクスポート実行
        result = await looker_exporter.export_to_drive()
        
        return LookerExportResponse(
            success=result['success'],
            message=result['message'],
            file_id=result.get('file_id'),
            stats=result.get('stats')
        )
        
    except Exception as e:
        logger.error(f"Looker export error: {e}")
        return LookerExportResponse(
            success=False,
            message=f"エクスポートエラー: {str(e)}"
        )

@app.get("/api/looker-studio/status")
async def get_looker_export_status():
    """Looker Studioエクスポートの状態を確認"""
    try:
        # Google Drive連携状態を確認
        gdrive_enabled = google_drive.is_enabled() if google_drive else False
        
        # 最新の統計情報を取得
        stats = looker_exporter.collect_summary_statistics()
        
        return {
            'google_drive_enabled': gdrive_enabled,
            'export_available': gdrive_enabled,
            'last_stats': stats,
            'dataset_folder': 'dataset',
            'export_format': 'CSV'
        }
        
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return {
            'google_drive_enabled': False,
            'export_available': False,
            'error': str(e)
        }

if __name__ == "__main__":
    import uvicorn
    
    # 設定読み込み
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    uvicorn.run(app, host=host, port=port, reload=True)