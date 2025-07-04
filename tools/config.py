import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# 基本パス
BASE_DIR = Path(__file__).parent.parent  # プロジェクトルートに移動
DATA_DIR = BASE_DIR / os.getenv("DATA_DIR_PATH", "data")
DATABASE_DIR = BASE_DIR / "agent" / "database"

# Google Gemini API設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

# データベース設定
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(DATABASE_DIR / "research_data.db")))

# アプリケーション設定
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "100"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# サポートするファイル拡張子
SUPPORTED_EXTENSIONS_STR = os.getenv("SUPPORTED_EXTENSIONS", "pdf,csv,json,jsonl")
SUPPORTED_EXTENSIONS: List[str] = [
    f".{ext.strip()}" for ext in SUPPORTED_EXTENSIONS_STR.split(",")
]

# ログ設定
import logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# pypdf関連の警告を完全に抑制
logging.getLogger('pypdf').setLevel(logging.CRITICAL)
logging.getLogger('pypdf._cmap').setLevel(logging.CRITICAL)
logging.getLogger('pypdf._reader').setLevel(logging.CRITICAL)

def validate_config():
    """設定の妥当性を検証"""
    errors = []
    
    if not GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY が設定されていません")
    
    if not DATA_DIR.exists():
        errors.append(f"データディレクトリが存在しません: {DATA_DIR}")
    
    # データベースディレクトリが存在しない場合は作成
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    
    if errors:
        for error in errors:
            logging.error(error)
        raise ValueError("設定エラーがあります。.envファイルを確認してください。")
    
    logging.info("設定の検証が完了しました")

# カテゴリーマッピング
CATEGORY_MAPPING = {
    "paper": "論文",
    "poster": "ポスター", 
    "datasets": "データセット"
}