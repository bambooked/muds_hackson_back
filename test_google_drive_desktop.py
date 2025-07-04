#!/usr/bin/env python3
"""
Google Drive認証テスト（デスクトップアプリケーション用）
より簡単な認証フローを使用
"""

import asyncio
import json
import os
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    print("Google Drive API libraries not available")

async def test_google_drive_desktop_auth():
    """デスクトップアプリケーション用Google Drive認証テスト"""
    
    if not GOOGLE_DRIVE_AVAILABLE:
        print("❌ Google Drive API libraries not installed")
        return False
    
    credentials_path = os.getenv('GOOGLE_DRIVE_CREDENTIALS_PATH', './google_drive_credentials.json')
    token_path = './google_drive_token.json'
    
    if not os.path.exists(credentials_path):
        print(f"❌ Credentials file not found: {credentials_path}")
        return False
    
    try:
        credentials = None
        
        # 既存トークンがあるかチェック
        if os.path.exists(token_path):
            credentials = Credentials.from_authorized_user_file(token_path)
        
        # 有効な認証情報がない場合、新規認証
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                print("🔄 Refreshing expired credentials...")
                credentials.refresh(Request())
            else:
                print("🔐 Starting new authentication flow...")
                
                # スコープを設定
                scopes = ['https://www.googleapis.com/auth/drive.readonly']
                
                # InstalledAppFlowを使用（デスクトップアプリケーション用）
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path, 
                    scopes
                )
                
                # ローカルサーバーを起動して認証
                print("🌐 Starting local server for authentication...")
                print("   Your browser will open automatically.")
                print("   Please complete the authentication in your browser.")
                
                credentials = flow.run_local_server(port=8081)
        
        # トークンを保存
        with open(token_path, 'w') as token_file:
            token_file.write(credentials.to_json())
        
        print("✅ Authentication successful!")
        
        # Google Drive APIサービスを構築
        service = build('drive', 'v3', credentials=credentials)
        
        # 接続テスト
        about = service.about().get(fields='user').execute()
        user_email = about.get('user', {}).get('emailAddress', 'Unknown')
        
        print(f"👤 Authenticated as: {user_email}")
        
        # フォルダリストを取得
        print("📁 Fetching folder list...")
        results = service.files().list(
            q="mimeType='application/vnd.google-apps.folder'",
            pageSize=20,
            fields="nextPageToken, files(id, name, parents)"
        ).execute()
        
        items = results.get('files', [])
        
        if not items:
            print("📁 No folders found.")
        else:
            print(f"📁 Found {len(items)} folders:")
            for item in items:
                print(f"   - {item['name']} (ID: {item['id']})")
        
        # muds_research_dataフォルダを検索
        print("\n🔍 Searching for 'muds_research_data' folder...")
        research_folder = None
        for item in items:
            if 'muds_research_data' in item['name'].lower():
                research_folder = item
                break
        
        if research_folder:
            print(f"✅ Found research folder: {research_folder['name']}")
            
            # サブフォルダを取得
            sub_results = service.files().list(
                q=f"parents in '{research_folder['id']}' and mimeType='application/vnd.google-apps.folder'",
                fields="files(id, name)"
            ).execute()
            
            sub_folders = sub_results.get('files', [])
            if sub_folders:
                print("📂 Sub-folders:")
                for folder in sub_folders:
                    print(f"   - {folder['name']}")
        else:
            print("❌ 'muds_research_data' folder not found.")
            print("   Please create this folder structure in your Google Drive:")
            print("   My Drive/muds_research_data/")
            print("   ├── papers/")
            print("   ├── posters/")
            print("   └── datasets/")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during Google Drive connection: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_google_drive_desktop_auth())
    if success:
        print("\n🎉 Google Drive connection test completed successfully!")
        print("💡 You can now use Google Drive with the research data management system.")
    else:
        print("\n💥 Google Drive connection test failed!")
        print("💡 Please check your Google Cloud Console settings and try again.")