#!/usr/bin/env python3
"""
Google Drive認証テスト用のシンプルなスクリプト
credentials.jsonファイルを使用してGoogle Drive APIに接続する
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
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    print("Google Drive API libraries not available")

async def test_google_drive_connection():
    """Google Drive接続テスト"""
    
    if not GOOGLE_DRIVE_AVAILABLE:
        print("❌ Google Drive API libraries not installed")
        return False
    
    credentials_path = os.getenv('GOOGLE_DRIVE_CREDENTIALS_PATH', './google_drive_credentials.json')
    
    if not os.path.exists(credentials_path):
        print(f"❌ Credentials file not found: {credentials_path}")
        return False
    
    try:
        # credentials.jsonファイルを読み込み
        with open(credentials_path, 'r') as f:
            client_config = json.load(f)
        
        print("✅ Credentials file loaded successfully")
        print(f"Project ID: {client_config['web']['project_id']}")
        print(f"Client ID: {client_config['web']['client_id'][:20]}...")
        
        # OAuth2フローを作成
        scopes = ['https://www.googleapis.com/auth/drive.readonly']
        
        flow = Flow.from_client_config(
            client_config,
            scopes=scopes
        )
        
        # リダイレクトURIを設定（ローカルサーバー用）
        flow.redirect_uri = 'http://localhost:8080/'
        
        # 認証URLを生成
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        
        print(f"🔗 Open this URL in your browser:")
        print(f"   {auth_url}")
        print()
        print("After authorization, you'll be redirected to a page with a code.")
        print("Copy the full redirect URL and paste it here:")
        
        # ユーザーから認証コードを取得
        authorization_response = input("Enter the full redirect URL: ").strip()
        
        # 認証コードを使用してトークンを取得
        flow.fetch_token(authorization_response=authorization_response)
        
        credentials = flow.credentials
        
        # Google Drive APIサービスを構築
        service = build('drive', 'v3', credentials=credentials)
        
        # 接続テスト
        about = service.about().get(fields='user').execute()
        user_email = about.get('user', {}).get('emailAddress', 'Unknown')
        
        print(f"✅ Google Drive authentication successful!")
        print(f"   User: {user_email}")
        
        # フォルダリストを取得
        results = service.files().list(
            q="mimeType='application/vnd.google-apps.folder'",
            pageSize=10,
            fields="nextPageToken, files(id, name)"
        ).execute()
        
        items = results.get('files', [])
        
        if not items:
            print("📁 No folders found.")
        else:
            print("📁 Available folders:")
            for item in items:
                print(f"   - {item['name']} (ID: {item['id']})")
        
        # トークンを保存（今後の認証で使用）
        token_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        with open('google_drive_token.json', 'w') as f:
            json.dump(token_data, f)
        
        print("💾 Token saved to google_drive_token.json")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during Google Drive connection: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_google_drive_connection())
    if success:
        print("\n🎉 Google Drive connection test completed successfully!")
    else:
        print("\n💥 Google Drive connection test failed!")