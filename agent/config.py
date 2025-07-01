"""
設定モジュール
システムの設定と環境変数の管理
"""
import os
from typing import Optional


class Config:
    """システム設定クラス"""
    
    def __init__(self):
        """設定の初期化"""
        # Gemini API設定
        self.gemini_api_key = os.environ.get('GEMINI_API_KEY', '')
        self.use_gemini_for_analysis = bool(self.gemini_api_key)
        
        # データベース設定
        self.database_path = os.environ.get(
            'RESEARCH_DB_PATH', 
            'agent/database/research_data.db'
        )
        
        # ファイル処理設定
        self.max_file_size = int(os.environ.get('MAX_FILE_SIZE', 50 * 1024 * 1024))  # 50MB
        self.allowed_extensions = {
            'txt', 'pdf', 'json', 'csv', 'md', 
            'png', 'jpg', 'jpeg', 'doc', 'docx'
        }
        
        # API設定
        self.api_host = os.environ.get('API_HOST', '0.0.0.0')
        self.api_port = int(os.environ.get('API_PORT', 5000))
        self.api_debug = os.environ.get('API_DEBUG', 'false').lower() == 'true'
        
        # アップロード設定
        self.upload_folder = os.environ.get(
            'UPLOAD_FOLDER', 
            'agent/source/uploads'
        )
        
        # 検索設定
        self.default_search_limit = int(os.environ.get('DEFAULT_SEARCH_LIMIT', 50))
        self.max_search_limit = int(os.environ.get('MAX_SEARCH_LIMIT', 200))
        
        # システム設定
        self.system_name = '研究データ基盤システム'
        self.system_version = '1.0.0'
        self.system_description = 'ローカルデータベースベースの研究データ管理・検索・相談システム'
        
        # ログ設定
        self.log_level = os.environ.get('LOG_LEVEL', 'INFO')
        self.log_file = os.environ.get('LOG_FILE', 'agent/logs/system.log')
    
    def validate(self) -> bool:
        """
        設定の妥当性を検証
        
        Returns:
            妥当な場合True
        """
        # 必須ディレクトリの作成
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)
        os.makedirs(self.upload_folder, exist_ok=True)
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        # Gemini APIキーの確認
        if self.use_gemini_for_analysis and not self.gemini_api_key:
            print("警告: Gemini APIキーが設定されていません。")
            print("環境変数 GEMINI_API_KEY を設定するか、config.pyを編集してください。")
            self.use_gemini_for_analysis = False
        
        return True
    
    def get_db_config(self) -> dict:
        """
        データベース設定を取得
        
        Returns:
            データベース設定の辞書
        """
        return {
            'path': self.database_path,
            'timeout': 30,
            'check_same_thread': False
        }
    
    def get_api_config(self) -> dict:
        """
        API設定を取得
        
        Returns:
            API設定の辞書
        """
        return {
            'host': self.api_host,
            'port': self.api_port,
            'debug': self.api_debug,
            'threaded': True
        }
    
    def display_config(self) -> None:
        """設定情報を表示"""
        print(f"\n=== {self.system_name} 設定情報 ===")
        print(f"バージョン: {self.system_version}")
        print(f"\nデータベース:")
        print(f"  パス: {self.database_path}")
        print(f"\nAPI設定:")
        print(f"  ホスト: {self.api_host}")
        print(f"  ポート: {self.api_port}")
        print(f"  デバッグ: {self.api_debug}")
        print(f"\nGemini API:")
        print(f"  有効: {self.use_gemini_for_analysis}")
        print(f"  キー設定: {'あり' if self.gemini_api_key else 'なし'}")
        print(f"\nファイル設定:")
        print(f"  最大サイズ: {self.max_file_size // (1024*1024)}MB")
        print(f"  アップロードフォルダ: {self.upload_folder}")
        print("=" * 40)
    
    @staticmethod
    def create_env_template() -> str:
        """
        環境変数テンプレートを生成
        
        Returns:
            .envファイルのテンプレート
        """
        template = """# 研究データ基盤システム 環境変数設定

# Gemini API設定
GEMINI_API_KEY=your_gemini_api_key_here

# データベース設定
RESEARCH_DB_PATH=agent/database/research_data.db

# API設定
API_HOST=0.0.0.0
API_PORT=5000
API_DEBUG=false

# ファイル設定
MAX_FILE_SIZE=52428800  # 50MB
UPLOAD_FOLDER=agent/source/uploads

# 検索設定
DEFAULT_SEARCH_LIMIT=50
MAX_SEARCH_LIMIT=200

# ログ設定
LOG_LEVEL=INFO
LOG_FILE=agent/logs/system.log
"""
        return template
    
    def save_env_template(self, path: str = '.env.example') -> None:
        """
        環境変数テンプレートをファイルに保存
        
        Args:
            path: 保存先パス
        """
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.create_env_template())
        print(f"環境変数テンプレートを {path} に保存しました。")


# グローバル設定インスタンス
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """
    設定インスタンスを取得（シングルトン）
    
    Returns:
        設定インスタンス
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
        _config_instance.validate()
    return _config_instance