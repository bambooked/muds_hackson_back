#!/usr/bin/env python3
"""
Google Drive → RAGシステム統合テスト
Google DriveからファイルをダウンロードしてRAGシステムで解析
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_google_drive_rag_integration():
    """Google Drive → RAGシステム統合テスト"""
    
    try:
        from agent.source.interfaces.google_drive_impl import GoogleDrivePortImpl
        from agent.source.interfaces.data_models import GoogleDriveConfig
        from agent.source.ui.interface import UserInterface
        
        print("🔄 Starting Google Drive → RAG integration test...")
        
        # Google Drive設定
        config = GoogleDriveConfig(
            credentials_path=os.getenv('GOOGLE_DRIVE_CREDENTIALS_PATH', './google_drive_credentials.json'),
            max_file_size_mb=int(os.getenv('GOOGLE_DRIVE_MAX_FILE_SIZE_MB', '100')),
            sync_interval_minutes=int(os.getenv('GOOGLE_DRIVE_SYNC_INTERVAL', '60'))
        )
        
        # Google Drive接続
        gdrive = GoogleDrivePortImpl(config)
        
        # 既存トークンで認証
        result = await gdrive.authenticate({})
        if not result:
            print("❌ Google Drive authentication failed")
            return False
        
        print("✅ Google Drive connected")
        
        # 現在のRAGシステムの状態を確認
        ui = UserInterface()
        
        print("\n📊 Current RAG system status:")
        current_stats = ui.analyzer.get_analysis_summary()
        print(f"   Analysis summary: {current_stats}")
        
        # 個別統計
        datasets = ui.dataset_repo.find_all()
        papers = ui.paper_repo.find_all()
        posters = ui.poster_repo.find_all()
        print(f"   Datasets: {len(datasets)}")
        print(f"   Papers: {len(papers)}")
        print(f"   Posters: {len(posters)}")
        
        # Google Driveから新しいファイルを同期
        print("\n🔄 Syncing from Google Drive...")
        
        # フォルダID取得
        folders = await gdrive.list_folders()
        folder_map = {f['name']: f['id'] for f in folders}
        
        # papers フォルダを同期
        if 'paper' in folder_map:
            papers_result = await gdrive.sync_folder(folder_map['paper'], 'papers_sync')
            if papers_result.status == 'COMPLETED':
                print(f"✅ Papers sync: {papers_result.processed_files} files processed")
        
        # posters フォルダを同期  
        if 'poster' in folder_map:
            posters_result = await gdrive.sync_folder(folder_map['poster'], 'posters_sync')
            if posters_result.status == 'COMPLETED':
                print(f"✅ Posters sync: {posters_result.processed_files} files processed")
        
        # datasets フォルダを同期
        if 'datasets' in folder_map:
            datasets_result = await gdrive.sync_folder(folder_map['datasets'], 'datasets_sync')
            if datasets_result.status == 'COMPLETED':
                print(f"✅ Datasets sync: {datasets_result.processed_files} files processed")
        
        # 統合後のRAGシステムの状態を確認
        print("\n📊 After Google Drive integration:")
        
        # インデックスを更新
        ui.update_index()
        
        updated_stats = ui.analyzer.get_analysis_summary()
        print(f"   Analysis summary: {updated_stats}")
        
        # 個別統計
        datasets_after = ui.dataset_repo.find_all()
        papers_after = ui.paper_repo.find_all()
        posters_after = ui.poster_repo.find_all()
        print(f"   Datasets: {len(datasets_after)}")
        print(f"   Papers: {len(papers_after)}")
        print(f"   Posters: {len(posters_after)}")
        
        # 検索テスト
        print("\n🔍 Testing search functionality...")
        
        search_results = ui.search_documents("research paper")
        print(f"   Search results for 'research paper': {len(search_results)} matches")
        
        if search_results:
            for i, result in enumerate(search_results[:3]):
                print(f"   {i+1}. {result.get('title', 'Untitled')} - {result.get('category', 'Unknown')}")
        
        print("\n🎉 Google Drive → RAG integration test completed successfully!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during integration test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_google_drive_rag_integration())
    if success:
        print("\n✅ Google Drive integration is working perfectly!")
        print("💡 You can now use Google Drive as a data source for your RAG system.")
    else:
        print("\n❌ Google Drive integration test failed!")