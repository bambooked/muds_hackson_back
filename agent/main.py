#!/usr/bin/env python3
"""
Research Data Management System
研究データ管理システム

Google Gemini APIを使用してdataディレクトリ内の研究データを管理・解析するシステム
"""

import sys
import os
import logging
from pathlib import Path

# プロジェクトのルートディレクトリをPATHに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from config import validate_config
    from agent.source.ui.interface import UserInterface
except ImportError as e:
    print(f"モジュールのインポートエラー: {e}")
    print("必要な依存関係がインストールされていることを確認してください。")
    print("実行: uv sync")
    sys.exit(1)

# ロガーの設定
logger = logging.getLogger(__name__)


def main():
    """メインエントリーポイント"""
    try:
        # 設定の検証
        validate_config()
        
        # ユーザーインターフェースを起動
        ui = UserInterface()
        ui.run()
        
    except KeyboardInterrupt:
        print("\n\nアプリケーションを中断しました。")
        sys.exit(0)
    
    except Exception as e:
        logger.error(f"アプリケーションエラー: {e}")
        print(f"\nエラーが発生しました: {e}")
        print("詳細は設定やログを確認してください。")
        sys.exit(1)


if __name__ == "__main__":
    main()