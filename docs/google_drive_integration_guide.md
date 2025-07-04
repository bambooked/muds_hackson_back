# Google Drive連携設定ガイド

このガイドでは、Research Data Management SystemにGoogle Drive連携を設定する手順を説明します。

## 概要

Google Drive連携により、以下が可能になります：
- Google Drive上の研究データ（論文、ポスター、データセット）を自動同期
- 新しいファイルの自動検出・解析
- 既存のローカルファイルとGoogle Driveファイルの統合管理
- credentials.jsonベースの安全な認証

## 前提条件

- Googleアカウント
- Google Cloud Console アクセス権限
- 本プロジェクトの開発環境セットアップ済み

## 1. Google Cloud Console設定

### 1.1 プロジェクト作成

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 「プロジェクトを選択」→「新しいプロジェクト」をクリック
3. プロジェクト名を入力（例：`muds-research-system`）
4. 「作成」をクリック

### 1.2 Google Drive API有効化

1. 作成したプロジェクトを選択
2. 「APIとサービス」→「ライブラリ」に移動
3. 「Google Drive API」を検索
4. 「Google Drive API」をクリック
5. 「有効にする」をクリック

### 1.3 OAuth認証情報作成

1. 「APIとサービス」→「認証情報」に移動
2. 「認証情報を作成」→「OAuth 2.0 クライアント ID」をクリック

#### ⚠️ 重要：アプリケーションタイプの選択

**正しい選択：**
- アプリケーションタイプ：**「デスクトップアプリケーション」**
- 名前：任意（例：`MUDS Research Desktop Client`）

**❌ 避けるべき選択：**
- 「ウェブアプリケーション」を選択すると`redirect_uri_mismatch`エラーが発生

#### よくあるエラーと解決方法

##### エラー1: `redirect_uri_mismatch`
```
エラー 400: redirect_uri_mismatch
```

**原因：** ウェブアプリケーション用の認証情報でデスクトップアプリの認証を試行

**解決方法：**
1. 既存の認証情報を削除
2. 「デスクトップアプリケーション」で新規作成

##### エラー2: `access_denied - Google の審査プロセスを完了していません`
```
エラー 403: access_denied
muds-database は Google の審査プロセスを完了していません
```

**解決方法1：テストユーザー追加**
1. 「OAuth同意画面」→「テストユーザー」
2. 「+ ADD USERS」をクリック
3. 使用するGoogleアカウントのメールアドレスを追加

**解決方法2：公開状態変更（個人使用の場合）**
1. 「OAuth同意画面」→「編集」
2. 「Publishing status」を「Testing」→「In production」に変更
3. ⚠️ 警告が表示されますが、個人使用なら問題ありません

### 1.4 認証情報ダウンロード

1. 作成した「デスクトップアプリケーション」の認証情報をクリック
2. 「JSONをダウンロード」をクリック
3. ファイル名は`client_secret_XXXXX.json`の形式でダウンロードされます

## 2. プロジェクト設定

### 2.1 認証情報ファイル配置

```bash
# ダウンロードしたファイルをプロジェクトルートに配置
cp ~/Downloads/client_secret_XXXXX.json ./google_drive_credentials.json
```

### 2.2 環境変数設定

`.env`ファイルに以下を追加：

```env
# Google Drive連携設定
PAAS_ENABLE_GOOGLE_DRIVE=true
GOOGLE_DRIVE_CREDENTIALS_PATH=./google_drive_credentials.json
GOOGLE_DRIVE_MAX_FILE_SIZE_MB=100
GOOGLE_DRIVE_SYNC_INTERVAL=60
```

### 2.3 必要パッケージインストール

```bash
uv add google-api-python-client google-auth-oauthlib google-auth
```

## 3. Google Drive準備

### 3.1 フォルダ構造作成

Google Drive上に以下の構造を作成：

```
My Drive/
├── papers/          # 論文PDFファイル
├── posters/         # ポスターPDFファイル
└── datasets/        # データセットフォルダ
    ├── esg/         # 例：ESGデータ
    ├── jbbq/        # 例：バイアス研究データ
    ├── greendata/   # 例：環境データ
    └── tv_effect/   # 例：TV効果データ
```

**注意：**
- フォルダ名は厳密に`papers`, `posters`, `datasets`である必要があります
- 大文字小文字も正確に合わせてください

## 4. 初回認証

### 4.1 認証テスト実行

```bash
uv run python test_google_drive_desktop.py
```

### 4.2 認証フロー

1. スクリプト実行後、ブラウザが自動的に開きます
2. Googleアカウントでログイン
3. アクセス許可を確認し「許可」をクリック
4. 認証完了後、ターミナルに結果が表示されます

**成功時の出力例：**
```
✅ Authentication successful!
👤 Authenticated as: your-email@gmail.com
📁 Found 9 folders:
   - paper (ID: 1iv0wdrd3zjh0iwo_TTBxyqM49MxSvll_)
   - poster (ID: 1g3WgThSwvXYNVXS4-LV3NhvsVSohk0Nw)
   - datasets (ID: 1jvwmzJl1OhINPQyoHufxEFrScK5H8HeV)
```

### 4.3 トークンファイル生成

認証成功後、`google_drive_token.json`ファイルが自動生成されます。このファイルにより、次回以降は自動認証されます。

## 5. 統合テスト

### 5.1 基本統合テスト

```bash
uv run python simple_integration_test.py
```

**期待される出力：**
```
🔄 Google Drive Integration Test
========================================
✅ Google Drive authentication successful
✅ Found 3 folders in Google Drive
   ✅ paper folder found
   ✅ poster folder found
   ✅ datasets folder found

📊 Current RAG System Status:
   Datasets analyzed: 8/8
   Papers analyzed: 7/12
   Posters analyzed: 3/7

✅ Google Drive integration is ready!
```

### 5.2 ファイル同期テスト

```bash
uv run python test_google_drive_sync.py
```

## 6. PaaS API統合

### 6.1 APIサーバー起動

```bash
uv run python services/api/paas_api.py
```

### 6.2 利用可能なAPI

Google Drive連携が有効化されると、以下のAPIエンドポイントが利用可能になります：

- `GET /health` - システム状態確認
- `POST /sync/google-drive` - Google Drive同期実行
- `GET /documents/search` - 統合文書検索

## 7. トラブルシューティング

### 7.1 認証関連エラー

#### `redirect_uri_mismatch`
- アプリケーションタイプを「デスクトップアプリケーション」に変更

#### `access_denied`
- テストユーザーを追加
- または公開状態を「In production」に変更

#### `Address already in use`
- ポート8080が使用中の場合、ポート8081を使用（自動対応済み）

### 7.2 ファイル同期エラー

#### PDFファイル読み込みエラー
```
PDF読み込みエラー（暗号化または破損の可能性）
```

**原因：** 空のファイルまたは破損したPDFファイル

**対策：**
- Google Drive上の該当ファイルを確認
- 有効なPDFファイルに置き換え

### 7.3 設定確認コマンド

```bash
# 環境変数確認
uv run python -c "
from dotenv import load_dotenv
import os
load_dotenv()
print('PAAS_ENABLE_GOOGLE_DRIVE:', os.getenv('PAAS_ENABLE_GOOGLE_DRIVE'))
print('Credentials file exists:', os.path.exists('./google_drive_credentials.json'))
"

# 解析状況確認
uv run python -c "
from agent.source.ui.interface import UserInterface
ui = UserInterface()
summary = ui.analyzer.get_analysis_summary()
print(summary)
"
```

## 8. セキュリティ考慮事項

### 8.1 認証情報の管理

- `google_drive_credentials.json`にはクライアントシークレットが含まれています
- このファイルを公開リポジトリにコミットしないでください
- `.gitignore`に追加することを推奨します

```gitignore
# Google Drive認証情報
google_drive_credentials.json
google_drive_token.json
```

### 8.2 アクセス権限

- このシステムは読み取り専用権限（`drive.readonly`）を使用
- ファイルの変更・削除は行いません
- Google Drive上のデータは安全に保護されます

## 9. 本番環境での使用

本番環境では、以下の追加設定を検討してください：

1. **環境変数での認証情報管理**
2. **より厳密なアクセス制御**
3. **ログ監視の強化**
4. **定期的なトークンローテーション**

## 10. まとめ

このガイドに従うことで、Google Drive連携が完全に動作します：

- ✅ Google Cloud Console設定
- ✅ credentials.json作成・配置
- ✅ 初回認証完了
- ✅ RAGシステムとの統合
- ✅ 自動ファイル同期・解析

Google Drive上の研究データが既存のローカルシステムと統合され、Gemini APIによる自動解析も実行されます。