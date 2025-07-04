"""
input_ports.pyモジュールの包括的テスト

このテストモジュールは、integrate_with_existing_indexer()関数および
関連するヘルパー関数の詳細なテストを提供します。

実行方法:
```bash
# 単体テスト実行
uv run pytest agent/tests/test_input_ports_module.py -v

# カバレッジ付き実行
uv run pytest agent/tests/test_input_ports_module.py --cov=agent.source.interfaces.input_ports --cov-report=html -v
```
"""

import asyncio
import tempfile
import pytest
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from typing import Dict, Any

# テスト対象のインポート
from agent.source.interfaces.input_ports import (
    integrate_with_existing_indexer,
    _determine_file_category,
    _get_target_path,
    _extract_dataset_name,
    _create_new_file_object,
    create_temp_file_path,
    InputError
)


class TestIntegrateWithExistingIndexer:
    """integrate_with_existing_indexer()関数のテストクラス"""
    
    @pytest.fixture
    def temp_file(self):
        """テスト用一時ファイル"""
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write("Test content")
            tmp_file.flush()
            yield tmp_file.name
        # クリーンアップ
        Path(tmp_file.name).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_integrate_paper_success(self, temp_file):
        """論文ファイル統合成功テスト"""
        with patch('agent.source.interfaces.input_ports.NewFileIndexer') as mock_indexer_class, \
             patch('agent.source.interfaces.input_ports.shutil.copy2') as mock_copy, \
             patch('agent.source.interfaces.input_ports._create_new_file_object') as mock_create_obj, \
             patch('agent.source.interfaces.input_ports.Path.mkdir'), \
             patch('agent.source.interfaces.input_ports.Path.exists', return_value=False):
            
            # モック設定
            mock_indexer = MagicMock()
            mock_indexer._process_paper.return_value = True
            mock_indexer_class.return_value = mock_indexer
            
            mock_file_obj = MagicMock()
            mock_create_obj.return_value = mock_file_obj
            
            # テスト実行
            result = await integrate_with_existing_indexer(
                file_path=temp_file,
                category='paper',
                target_name='research_paper.pdf'
            )
            
            # 結果確認
            assert result is True
            mock_copy.assert_called_once()
            mock_indexer_class.assert_called_once_with(auto_analyze=True)
            mock_indexer._process_paper.assert_called_once_with(mock_file_obj)
    
    @pytest.mark.asyncio
    async def test_integrate_poster_success(self, temp_file):
        """ポスターファイル統合成功テスト"""
        with patch('agent.source.interfaces.input_ports.NewFileIndexer') as mock_indexer_class, \
             patch('agent.source.interfaces.input_ports.shutil.copy2') as mock_copy, \
             patch('agent.source.interfaces.input_ports._create_new_file_object') as mock_create_obj, \
             patch('agent.source.interfaces.input_ports.Path.mkdir'), \
             patch('agent.source.interfaces.input_ports.Path.exists', return_value=False):
            
            # モック設定
            mock_indexer = MagicMock()
            mock_indexer._process_poster.return_value = True
            mock_indexer_class.return_value = mock_indexer
            
            mock_file_obj = MagicMock()
            mock_create_obj.return_value = mock_file_obj
            
            # テスト実行
            result = await integrate_with_existing_indexer(
                file_path=temp_file,
                category='poster',
                target_name='conference_poster.pdf'
            )
            
            # 結果確認
            assert result is True
            mock_indexer._process_poster.assert_called_once_with(mock_file_obj)
    
    @pytest.mark.asyncio
    async def test_integrate_dataset_success(self, temp_file):
        """データセットファイル統合成功テスト"""
        with patch('agent.source.interfaces.input_ports.NewFileIndexer') as mock_indexer_class, \
             patch('agent.source.interfaces.input_ports.shutil.copy2') as mock_copy, \
             patch('agent.source.interfaces.input_ports.Path.mkdir'), \
             patch('agent.source.interfaces.input_ports.Path.exists', return_value=False):
            
            # モック設定
            mock_indexer = MagicMock()
            mock_indexer.index_all_files.return_value = {'datasets': 1, 'papers': 0, 'posters': 0}
            mock_indexer_class.return_value = mock_indexer
            
            # テスト実行
            result = await integrate_with_existing_indexer(
                file_path=temp_file,
                category='dataset',
                target_name='sample_data.csv'
            )
            
            # 結果確認
            assert result is True
            mock_indexer.index_all_files.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_integrate_auto_category_detection(self, temp_file):
        """自動カテゴリ判定テスト"""
        with patch('agent.source.interfaces.input_ports._determine_file_category') as mock_determine, \
             patch('agent.source.interfaces.input_ports.NewFileIndexer') as mock_indexer_class, \
             patch('agent.source.interfaces.input_ports.shutil.copy2'), \
             patch('agent.source.interfaces.input_ports._create_new_file_object') as mock_create_obj, \
             patch('agent.source.interfaces.input_ports.Path.mkdir'), \
             patch('agent.source.interfaces.input_ports.Path.exists', return_value=False):
            
            # モック設定
            mock_determine.return_value = 'paper'
            mock_indexer = MagicMock()
            mock_indexer._process_paper.return_value = True
            mock_indexer_class.return_value = mock_indexer
            mock_create_obj.return_value = MagicMock()
            
            # テスト実行（カテゴリ未指定）
            result = await integrate_with_existing_indexer(
                file_path=temp_file,
                target_name='unknown_document.pdf'
            )
            
            # 結果確認
            assert result is True
            mock_determine.assert_called_once_with('unknown_document.pdf', Path(temp_file))
    
    @pytest.mark.asyncio
    async def test_integrate_file_exists_conflict(self, temp_file):
        """ファイル名衝突回避テスト"""
        with patch('agent.source.interfaces.input_ports.NewFileIndexer') as mock_indexer_class, \
             patch('agent.source.interfaces.input_ports.shutil.copy2') as mock_copy, \
             patch('agent.source.interfaces.input_ports._create_new_file_object') as mock_create_obj, \
             patch('agent.source.interfaces.input_ports.Path.mkdir') as mock_mkdir:
            
            # ファイル存在確認をモック（最初は存在、2回目は存在しない）
            with patch('agent.source.interfaces.input_ports.Path.exists', side_effect=[True, False]):
                # モック設定
                mock_indexer = MagicMock()
                mock_indexer._process_paper.return_value = True
                mock_indexer_class.return_value = mock_indexer
                mock_create_obj.return_value = MagicMock()
                
                # テスト実行
                result = await integrate_with_existing_indexer(
                    file_path=temp_file,
                    category='paper',
                    target_name='existing_file.pdf'
                )
                
                # 結果確認
                assert result is True
                # ファイル名に_1が追加されることを確認
                call_args = mock_copy.call_args[0]
                target_path = str(call_args[1])
                assert 'existing_file_1.pdf' in target_path
    
    @pytest.mark.asyncio
    async def test_integrate_source_file_not_found(self):
        """ソースファイル不存在エラーテスト"""
        non_existent_file = "/tmp/non_existent_file.pdf"
        
        with pytest.raises(InputError) as exc_info:
            await integrate_with_existing_indexer(
                file_path=non_existent_file,
                category='paper',
                target_name='test.pdf'
            )
        
        assert "Source file not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_integrate_unsupported_category(self, temp_file):
        """サポートされていないカテゴリエラーテスト"""
        with patch('agent.source.interfaces.input_ports.shutil.copy2'), \
             patch('agent.source.interfaces.input_ports.Path.mkdir'), \
             patch('agent.source.interfaces.input_ports.Path.exists', return_value=False):
            
            with pytest.raises(InputError) as exc_info:
                await integrate_with_existing_indexer(
                    file_path=temp_file,
                    category='unsupported_category',
                    target_name='test.pdf'
                )
            
            assert "Unsupported category" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_integrate_processing_failure(self, temp_file):
        """ファイル処理失敗エラーテスト"""
        with patch('agent.source.interfaces.input_ports.NewFileIndexer') as mock_indexer_class, \
             patch('agent.source.interfaces.input_ports.shutil.copy2'), \
             patch('agent.source.interfaces.input_ports._create_new_file_object') as mock_create_obj, \
             patch('agent.source.interfaces.input_ports.Path.mkdir'), \
             patch('agent.source.interfaces.input_ports.Path.exists', return_value=False):
            
            # モック設定（処理失敗）
            mock_indexer = MagicMock()
            mock_indexer._process_paper.return_value = False
            mock_indexer_class.return_value = mock_indexer
            mock_create_obj.return_value = MagicMock()
            
            with pytest.raises(InputError) as exc_info:
                await integrate_with_existing_indexer(
                    file_path=temp_file,
                    category='paper',
                    target_name='test.pdf'
                )
            
            assert "Failed to process paper file" in str(exc_info.value)


class TestFileCategoryDetermination:
    """ファイルカテゴリ判定テストクラス"""
    
    def test_determine_category_dataset_by_extension(self):
        """拡張子によるデータセット判定テスト"""
        test_cases = [
            ("data.csv", "dataset"),
            ("sample.json", "dataset"),
            ("analysis.jsonl", "dataset")
        ]
        
        for filename, expected in test_cases:
            result = _determine_file_category(filename, Path(filename))
            assert result == expected, f"Failed for {filename}: expected {expected}, got {result}"
    
    def test_determine_category_dataset_by_keyword(self):
        """キーワードによるデータセット判定テスト"""
        test_cases = [
            ("dataset_v1.txt", "dataset"),
            ("research_data.txt", "dataset"),
            ("sample_dataset.pdf", "dataset")
        ]
        
        for filename, expected in test_cases:
            result = _determine_file_category(filename, Path(filename))
            assert result == expected, f"Failed for {filename}: expected {expected}, got {result}"
    
    def test_determine_category_poster_by_keyword(self):
        """キーワードによるポスター判定テスト"""
        test_cases = [
            ("conference_poster.pdf", "poster"),
            ("presentation_slides.pdf", "poster"),
            ("poster_final.pdf", "poster")
        ]
        
        for filename, expected in test_cases:
            result = _determine_file_category(filename, Path(filename))
            assert result == expected, f"Failed for {filename}: expected {expected}, got {result}"
    
    def test_determine_category_paper_by_keyword(self):
        """キーワードによる論文判定テスト"""
        test_cases = [
            ("research_paper.pdf", "paper"),
            ("thesis_document.pdf", "paper"),
            ("journal_article.pdf", "paper"),
            ("conference_proceedings.pdf", "paper")
        ]
        
        for filename, expected in test_cases:
            result = _determine_file_category(filename, Path(filename))
            assert result == expected, f"Failed for {filename}: expected {expected}, got {result}"
    
    def test_determine_category_default_pdf(self):
        """PDFデフォルト判定テスト"""
        result = _determine_file_category("unknown_document.pdf", Path("unknown_document.pdf"))
        assert result == "paper"
    
    def test_determine_category_default_non_pdf(self):
        """非PDFデフォルト判定テスト"""
        result = _determine_file_category("unknown_file.txt", Path("unknown_file.txt"))
        assert result == "dataset"


class TestPathGeneration:
    """パス生成テストクラス"""
    
    def test_get_target_path_paper(self):
        """論文パス生成テスト"""
        with patch.dict('os.environ', {'DATA_DIR_PATH': '/test/data'}):
            result = _get_target_path('paper', 'research.pdf')
            expected = Path('/test/data/paper/research.pdf')
            assert result == expected
    
    def test_get_target_path_poster(self):
        """ポスターパス生成テスト"""
        with patch.dict('os.environ', {'DATA_DIR_PATH': '/test/data'}):
            result = _get_target_path('poster', 'presentation.pdf')
            expected = Path('/test/data/poster/presentation.pdf')
            assert result == expected
    
    def test_get_target_path_dataset(self):
        """データセットパス生成テスト"""
        with patch.dict('os.environ', {'DATA_DIR_PATH': '/test/data'}), \
             patch('agent.source.interfaces.input_ports._extract_dataset_name', return_value='sample-dataset'):
            
            result = _get_target_path('dataset', 'sample_data.csv')
            expected = Path('/test/data/datasets/sample-dataset/sample_data.csv')
            assert result == expected
    
    def test_get_target_path_unknown_category(self):
        """不明カテゴリエラーテスト"""
        with pytest.raises(InputError) as exc_info:
            _get_target_path('unknown', 'test.txt')
        
        assert "Unknown category" in str(exc_info.value)


class TestDatasetNameExtraction:
    """データセット名抽出テストクラス"""
    
    def test_extract_dataset_name_version_removal(self):
        """バージョン情報削除テスト"""
        test_cases = [
            ("dataset_v1.csv", "dataset"),
            ("research_data_v2.json", "research-data"),
            ("sample_2024.csv", "sample"),
            ("analysis_final.jsonl", "analysis")
        ]
        
        for filename, expected in test_cases:
            result = _extract_dataset_name(filename)
            assert result == expected, f"Failed for {filename}: expected {expected}, got {result}"
    
    def test_extract_dataset_name_underscore_to_hyphen(self):
        """アンダースコア→ハイフン変換テスト"""
        test_cases = [
            ("esg_data.csv", "esg-data"),
            ("complex_dataset_name.json", "complex-dataset-name"),
            ("simple_name.csv", "simple-name")
        ]
        
        for filename, expected in test_cases:
            result = _extract_dataset_name(filename)
            assert result == expected, f"Failed for {filename}: expected {expected}, got {result}"
    
    def test_extract_dataset_name_case_normalization(self):
        """大文字小文字正規化テスト"""
        test_cases = [
            ("ESG_Data.csv", "esg-data"),
            ("Research_Dataset.json", "research-dataset"),
            ("SAMPLE.csv", "sample")
        ]
        
        for filename, expected in test_cases:
            result = _extract_dataset_name(filename)
            assert result == expected, f"Failed for {filename}: expected {expected}, got {result}"
    
    def test_extract_dataset_name_empty_fallback(self):
        """空文字列フォールバックテスト"""
        # 極端な例（全て削除される）
        result = _extract_dataset_name("v1.csv")
        assert result == "v1"  # 元の名前を使用


class TestFileObjectCreation:
    """ファイルオブジェクト作成テストクラス"""
    
    def test_create_file_object_success(self):
        """ファイルオブジェクト作成成功テスト"""
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmp_file:
            tmp_file.write("Test content")
            tmp_file.flush()
            temp_path = Path(tmp_file.name)
            
            try:
                file_obj = _create_new_file_object(temp_path, 'paper')
                
                # 属性確認
                assert file_obj.file_path == str(temp_path.absolute())
                assert file_obj.file_name == temp_path.name
                assert file_obj.file_size > 0
                assert file_obj.category == 'paper'
                assert len(file_obj.content_hash) == 64  # SHA256ハッシュ長
                assert isinstance(file_obj.created_at, datetime)
                assert isinstance(file_obj.updated_at, datetime)
                
            finally:
                temp_path.unlink(missing_ok=True)
    
    def test_create_file_object_nonexistent_file(self):
        """存在しないファイルでのエラーテスト"""
        non_existent_path = Path("/tmp/non_existent_file.txt")
        
        with pytest.raises(InputError) as exc_info:
            _create_new_file_object(non_existent_path, 'dataset')
        
        assert "Failed to create file object" in str(exc_info.value)


class TestTempFilePathGeneration:
    """一時ファイルパス生成テストクラス"""
    
    def test_create_temp_file_path_basic(self):
        """基本的な一時ファイルパス生成テスト"""
        job_id = "test_job_123"
        filename = "sample.pdf"
        
        result = create_temp_file_path(job_id, filename)
        
        assert isinstance(result, Path)
        assert f"/tmp/paas_temp/{job_id}" in str(result)
        assert filename in str(result.name) or "sample" in str(result.name)
    
    def test_create_temp_file_path_uuid_uniqueness(self):
        """UUID重複回避テスト"""
        job_id = "test_job"
        filename = "test.pdf"
        
        path1 = create_temp_file_path(job_id, filename)
        path2 = create_temp_file_path(job_id, filename)
        
        # 異なるUUIDにより異なるパスが生成される
        assert path1 != path2
    
    def test_create_temp_file_path_special_characters(self):
        """特殊文字を含むファイル名テスト"""
        job_id = "test_job"
        filename = "file with spaces & symbols.pdf"
        
        result = create_temp_file_path(job_id, filename)
        
        # パスが生成されることを確認
        assert isinstance(result, Path)
        assert f"/tmp/paas_temp/{job_id}" in str(result)


class TestIntegrationScenarios:
    """統合シナリオテストクラス"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_paper_integration(self):
        """論文E2Eテスト（モック使用）"""
        # 実際のファイル作成
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write("Mock PDF content")
            tmp_file.flush()
            source_path = tmp_file.name
        
        try:
            with patch('agent.source.interfaces.input_ports.NewFileIndexer') as mock_indexer_class, \
                 patch('agent.source.interfaces.input_ports.shutil.copy2') as mock_copy, \
                 patch('agent.source.interfaces.input_ports.Path.mkdir') as mock_mkdir, \
                 patch('agent.source.interfaces.input_ports.Path.exists', return_value=False):
                
                # モック設定
                mock_indexer = MagicMock()
                mock_indexer._process_paper.return_value = True
                mock_indexer_class.return_value = mock_indexer
                
                # テスト実行
                result = await integrate_with_existing_indexer(
                    file_path=source_path,
                    category=None,  # 自動判定
                    target_name='research_paper.pdf'
                )
                
                # 結果確認
                assert result is True
                mock_indexer_class.assert_called_once_with(auto_analyze=True)
                mock_copy.assert_called_once()
                mock_mkdir.assert_called()
                
                # ターゲットパスの確認
                call_args = mock_copy.call_args[0]
                target_path = str(call_args[1])
                assert 'paper' in target_path
                assert 'research_paper.pdf' in target_path
        
        finally:
            Path(source_path).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_end_to_end_dataset_integration(self):
        """データセットE2Eテスト（モック使用）"""
        # 実際のファイル作成
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.csv') as tmp_file:
            tmp_file.write("col1,col2\nval1,val2\n")
            tmp_file.flush()
            source_path = tmp_file.name
        
        try:
            with patch('agent.source.interfaces.input_ports.NewFileIndexer') as mock_indexer_class, \
                 patch('agent.source.interfaces.input_ports.shutil.copy2') as mock_copy, \
                 patch('agent.source.interfaces.input_ports.Path.mkdir') as mock_mkdir, \
                 patch('agent.source.interfaces.input_ports.Path.exists', return_value=False):
                
                # モック設定
                mock_indexer = MagicMock()
                mock_indexer.index_all_files.return_value = {'datasets': 1}
                mock_indexer_class.return_value = mock_indexer
                
                # テスト実行
                result = await integrate_with_existing_indexer(
                    file_path=source_path,
                    category=None,  # 自動判定
                    target_name='sample_dataset.csv'
                )
                
                # 結果確認
                assert result is True
                mock_indexer.index_all_files.assert_called_once()
                
                # ターゲットパスの確認
                call_args = mock_copy.call_args[0]
                target_path = str(call_args[1])
                assert 'datasets' in target_path
                assert 'sample_dataset.csv' in target_path
        
        finally:
            Path(source_path).unlink(missing_ok=True)


if __name__ == "__main__":
    """スタンドアロンテスト実行"""
    print("=== input_ports.py モジュールテスト実行 ===")
    
    # テスト実行
    import subprocess
    import sys
    
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            __file__, 
            '-v', 
            '--tb=short'
        ], cwd=Path(__file__).parent.parent.parent, capture_output=True, text=True)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        print(f"\nテスト結果: {'SUCCESS' if result.returncode == 0 else 'FAILED'}")
        sys.exit(result.returncode)
        
    except Exception as e:
        print(f"テスト実行エラー: {e}")
        sys.exit(1)