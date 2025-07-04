#!/usr/bin/env python3
"""
Google Drive同期テスト
実際のファイル同期機能をテストする
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    import io
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False

async def test_google_drive_sync():
    """Google Drive同期テスト"""
    
    if not GOOGLE_DRIVE_AVAILABLE:
        print("❌ Google Drive API libraries not available")
        return False
    
    token_path = './google_drive_token.json'
    
    if not os.path.exists(token_path):
        print("❌ Authentication token not found. Please run test_google_drive_desktop.py first.")
        return False
    
    try:
        # トークンを読み込み
        credentials = Credentials.from_authorized_user_file(token_path)
        
        # Google Drive APIサービスを構築
        service = build('drive', 'v3', credentials=credentials)
        
        print("✅ Google Drive service connected")
        
        # 各カテゴリフォルダの情報を取得
        categories = {
            'papers': 'paper',
            'posters': 'poster', 
            'datasets': 'datasets'
        }
        
        sync_summary = {}
        
        for category, folder_name in categories.items():
            print(f"\n📁 Processing {category} folder...")
            
            # フォルダを検索
            folder_results = service.files().list(
                q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'",
                fields="files(id, name)"
            ).execute()
            
            folders = folder_results.get('files', [])
            
            if not folders:
                print(f"❌ {folder_name} folder not found")
                continue
            
            folder_id = folders[0]['id']
            print(f"✅ Found {folder_name} folder (ID: {folder_id})")
            
            # フォルダ内のファイルを取得
            if category == 'datasets':
                # datasetsの場合、サブフォルダを取得
                sub_folders = service.files().list(
                    q=f"parents in '{folder_id}' and mimeType='application/vnd.google-apps.folder'",
                    fields="files(id, name)"
                ).execute().get('files', [])
                
                dataset_count = 0
                for sub_folder in sub_folders:
                    sub_files = service.files().list(
                        q=f"parents in '{sub_folder['id']}'",
                        fields="files(id, name, size, mimeType)"
                    ).execute().get('files', [])
                    
                    dataset_count += len(sub_files)
                    print(f"   📂 {sub_folder['name']}: {len(sub_files)} files")
                
                sync_summary[category] = {
                    'folders': len(sub_folders),
                    'files': dataset_count
                }
            else:
                # papers/postersの場合、直接ファイルを取得
                files = service.files().list(
                    q=f"parents in '{folder_id}'",
                    fields="files(id, name, size, mimeType)"
                ).execute().get('files', [])
                
                sync_summary[category] = {
                    'files': len(files)
                }
                
                print(f"   📄 Found {len(files)} files")
                for file in files[:3]:  # 最初の3つを表示
                    size = int(file.get('size', 0)) if file.get('size') else 0
                    size_mb = size / (1024 * 1024)
                    print(f"      - {file['name']} ({size_mb:.2f}MB)")
        
        # 同期サマリーを表示
        print("\n" + "="*50)
        print("📊 Google Drive Sync Summary")
        print("="*50)
        
        total_files = 0
        for category, info in sync_summary.items():
            files_count = info['files']
            total_files += files_count
            
            if category == 'datasets':
                print(f"{category.capitalize():12}: {info['folders']} folders, {files_count} files")
            else:
                print(f"{category.capitalize():12}: {files_count} files")
        
        print(f"{'Total':12}: {total_files} files")
        
        # 簡単なファイルダウンロードテスト
        print("\n🔄 Testing file download...")
        
        # papersフォルダから1つのファイルをダウンロードテスト
        papers_folder = None
        for category, folder_name in categories.items():
            if category == 'papers':
                folder_results = service.files().list(
                    q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'",
                    fields="files(id, name)"
                ).execute()
                if folder_results.get('files'):
                    papers_folder = folder_results['files'][0]['id']
                    break
        
        if papers_folder:
            files = service.files().list(
                q=f"parents in '{papers_folder}'",
                pageSize=1,
                fields="files(id, name, size)"
            ).execute().get('files', [])
            
            if files:
                test_file = files[0]
                print(f"📥 Downloading test file: {test_file['name']}")
                
                # 一時ディレクトリにダウンロード
                with tempfile.TemporaryDirectory() as temp_dir:
                    file_path = Path(temp_dir) / test_file['name']
                    
                    request = service.files().get_media(fileId=test_file['id'])
                    file_content = io.BytesIO()
                    downloader = MediaIoBaseDownload(file_content, request)
                    
                    done = False
                    while done is False:
                        status, done = downloader.next_chunk()
                        print(f"   Progress: {int(status.progress() * 100)}%")
                    
                    # ファイルを保存
                    with open(file_path, 'wb') as f:
                        f.write(file_content.getvalue())
                    
                    file_size = file_path.stat().st_size
                    print(f"✅ Download successful: {file_size} bytes")
        
        print("\n🎉 Google Drive sync test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error during Google Drive sync: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_google_drive_sync())
    if success:
        print("\n✅ Google Drive is ready for integration with the research data management system!")
    else:
        print("\n❌ Google Drive sync test failed!")