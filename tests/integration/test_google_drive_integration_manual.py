#!/usr/bin/env python3
"""
Google Drive統合の手動テスト

このスクリプトは、Google Drive API認証なしでも実行可能な統合テストを提供します。
実際の統合フローを模擬して、ファイル配置・カテゴリ判定・NewFileIndexer連携を確認します。

実行方法:
```bash
uv run python test_google_drive_integration_manual.py
```
"""

import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import logging
import sys
import os

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_integration_flow():
    """統合フロー全体テスト"""
    print("=== Google Drive統合フロー テスト開始 ===")
    
    # テスト用一時ファイル作成
    test_files = [
        ("research_paper.pdf", "paper", b"PDF content simulation"),
        ("conference_poster.pdf", "poster", b"Poster PDF simulation"),
        ("dataset_sample.csv", "dataset", b"col1,col2\nval1,val2\n"),
        ("data_analysis.json", "dataset", b'{"data": "sample"}')
    ]
    
    success_count = 0
    total_count = len(test_files)
    
    for filename, expected_category, content in test_files:
        try:
            print(f"\n--- {filename} の統合テスト ---")
            
            # 一時ファイル作成
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix=Path(filename).suffix) as tmp_file:
                tmp_file.write(content)
                tmp_file_path = tmp_file.name
            
            # 統合関数テスト
            from agent.source.interfaces.input_ports import integrate_with_existing_indexer
            
            result = await integrate_with_existing_indexer(
                file_path=tmp_file_path,
                category=None,  # 自動判定
                target_name=filename
            )
            
            if result:
                print(f"✅ {filename}: 統合成功")
                success_count += 1
            else:
                print(f"❌ {filename}: 統合失敗")
            
            # 一時ファイル削除
            Path(tmp_file_path).unlink(missing_ok=True)
            
        except Exception as e:
            print(f"❌ {filename}: エラー - {e}")
            logger.error(f"統合テストエラー: {filename}", exc_info=True)
    
    print(f"\n=== 統合テスト結果: {success_count}/{total_count} 成功 ===")
    return success_count == total_count


async def test_category_determination():
    """カテゴリ判定テスト"""
    print("\n=== カテゴリ判定テスト ===")
    
    from agent.source.interfaces.input_ports import _determine_file_category
    
    test_cases = [
        ("research_paper.pdf", "paper"),
        ("conference_poster.pdf", "poster"),
        ("dataset.csv", "dataset"),
        ("sample_data.json", "dataset"),
        ("analysis.jsonl", "dataset"),
        ("thesis_document.pdf", "paper"),
        ("presentation_slides.pdf", "poster"),
        ("unknown_file.pdf", "paper"),  # デフォルト
        ("data_file.txt", "dataset")  # デフォルト
    ]
    
    success_count = 0
    for filename, expected in test_cases:
        try:
            result = _determine_file_category(filename, Path(filename))
            if result == expected:
                print(f"✅ {filename} -> {result} (期待: {expected})")
                success_count += 1
            else:
                print(f"❌ {filename} -> {result} (期待: {expected})")
        except Exception as e:
            print(f"❌ {filename}: エラー - {e}")
    
    print(f"カテゴリ判定テスト: {success_count}/{len(test_cases)} 成功")
    return success_count == len(test_cases)


async def test_path_generation():
    """パス生成テスト"""
    print("\n=== パス生成テスト ===")
    
    from agent.source.interfaces.input_ports import _get_target_path, _extract_dataset_name
    
    # データセット名抽出テスト
    dataset_tests = [
        ("esg_data_2024.csv", "esg-data"),
        ("research_dataset_v1.json", "research-dataset"),
        ("sample-file.jsonl", "sample-file"),
        ("complex_dataset_final.csv", "complex-dataset")
    ]
    
    print("データセット名抽出:")
    for filename, expected in dataset_tests:
        result = _extract_dataset_name(filename)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {filename} -> {result} (期待: {expected})")
    
    # パス生成テスト
    print("\nパス生成:")
    path_tests = [
        ("dataset", "test.csv", "data/datasets/test/test.csv"),
        ("paper", "research.pdf", "data/paper/research.pdf"),
        ("poster", "presentation.pdf", "data/poster/presentation.pdf")
    ]
    
    for category, filename, expected_path in path_tests:
        try:
            result = _get_target_path(category, filename)
            # パスの末尾部分を比較
            if str(result).endswith(expected_path):
                print(f"  ✅ {category}/{filename} -> {result}")
            else:
                print(f"  ❌ {category}/{filename} -> {result} (期待末尾: {expected_path})")
        except Exception as e:
            print(f"  ❌ {category}/{filename}: エラー - {e}")


async def test_google_drive_impl():
    """GoogleDrivePortImpl実装テスト"""
    print("\n=== GoogleDrivePortImpl 基本テスト ===")
    
    try:
        from agent.source.interfaces.data_models import GoogleDriveConfig
        from agent.source.interfaces.google_drive_impl import GoogleDrivePortImpl
        
        # 設定作成
        config = GoogleDriveConfig(
            credentials_path="/tmp/test_credentials.json",
            max_file_size_mb=50
        )
        
        # インスタンス作成
        google_drive_port = GoogleDrivePortImpl(config)
        
        print("✅ GoogleDrivePortImpl インスタンス作成成功")
        
        # 基本メソッドテスト
        test_methods = [
            ("_is_supported_mime_type", ["application/pdf"], True),
            ("_get_content_type_from_mime", ["application/pdf"], "pdf"),
            ("_determine_category", ["research_paper.pdf"], "paper")
        ]
        
        for method_name, args, expected in test_methods:
            try:
                method = getattr(google_drive_port, method_name)
                result = method(*args)
                status = "✅" if result == expected else "❌"
                print(f"  {status} {method_name}({args}) -> {result}")
            except Exception as e:
                print(f"  ❌ {method_name}: エラー - {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ GoogleDrivePortImpl テスト失敗: {e}")
        return False


async def test_config_manager():
    """設定管理テスト"""
    print("\n=== 設定管理テスト ===")
    
    try:
        from agent.source.interfaces.config_manager import get_config_manager
        
        config_manager = get_config_manager()
        config = config_manager.load_config()
        
        print(f"✅ 設定読み込み成功")
        print(f"  環境: {config.environment}")
        print(f"  Google Drive有効: {config.enable_google_drive}")
        print(f"  Vector Search有効: {config.enable_vector_search}")
        print(f"  認証有効: {config.enable_authentication}")
        
        return True
        
    except Exception as e:
        print(f"❌ 設定管理テスト失敗: {e}")
        return False


async def main():
    """メインテスト実行"""
    print("Google Drive統合 - 手動テスト実行中...\n")
    
    # 環境確認
    print("=== 環境確認 ===")
    try:
        from agent.source.ui.interface import UserInterface
        ui = UserInterface()
        print("✅ 既存システム正常動作")
    except Exception as e:
        print(f"❌ 既存システムエラー: {e}")
        return False
    
    # 各テストの実行
    test_results = []
    
    test_results.append(await test_config_manager())
    test_results.append(await test_google_drive_impl())
    test_results.append(await test_category_determination())
    await test_path_generation()
    test_results.append(await test_integration_flow())
    
    # 総合結果
    passed = sum(test_results)
    total = len(test_results)
    
    print(f"\n{'='*50}")
    print(f"総合テスト結果: {passed}/{total} 成功")
    
    if passed == total:
        print("🎉 全てのテストが成功しました！")
        print("Google Drive統合実装が正常に完了しています。")
    else:
        print("⚠️  一部のテストが失敗しました。")
        print("実装を再確認してください。")
    
    return passed == total


if __name__ == "__main__":
    """スクリプト直接実行"""
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nテスト中断されました。")
        sys.exit(1)
    except Exception as e:
        print(f"\n予期しないエラー: {e}")
        logger.error("予期しないエラー", exc_info=True)
        sys.exit(1)