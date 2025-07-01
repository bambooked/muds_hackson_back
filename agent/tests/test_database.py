"""
データベース機能のテスト
"""
import os
import tempfile
import pytest
from agent.database_handler import DatabaseHandler
from agent.metadata_extractor import MetadataExtractor


class TestDatabaseHandler:
    """データベースハンドラのテストクラス"""
    
    @pytest.fixture
    def temp_db(self):
        """テスト用の一時データベース"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        handler = DatabaseHandler(db_path)
        yield handler
        
        # クリーンアップ
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    def test_database_initialization(self, temp_db):
        """データベース初期化のテスト"""
        # データベースファイルが作成されることを確認
        assert os.path.exists(temp_db.db_path)
        
        # テーブルが作成されることを確認
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            assert 'research_data' in tables
            assert 'search_history' in tables
    
    def test_data_insertion(self, temp_db):
        """データ挿入のテスト"""
        test_data = {
            'data_id': 'test_001',
            'data_type': 'dataset',
            'title': 'テストデータセット',
            'summary': 'テスト用のデータセット',
            'research_field': '機械学習',
            'file_path': '/test/path/dataset.json',
            'metadata': {'size': 1000, 'format': 'json'}
        }
        
        # データ挿入
        result = temp_db.insert_data(test_data)
        assert result is True
        
        # データ取得
        retrieved = temp_db.get_data_by_id('test_001')
        assert retrieved is not None
        assert retrieved['title'] == 'テストデータセット'
        assert retrieved['data_type'] == 'dataset'
    
    def test_data_search(self, temp_db):
        """データ検索のテスト"""
        # テストデータの挿入
        test_data_1 = {
            'data_id': 'test_001',
            'data_type': 'dataset',
            'title': '機械学習データセット',
            'summary': '機械学習用のデータ',
            'research_field': '機械学習'
        }
        
        test_data_2 = {
            'data_id': 'test_002',
            'data_type': 'paper',
            'title': '自然言語処理の論文',
            'summary': 'NLPに関する研究',
            'research_field': '自然言語処理'
        }
        
        temp_db.insert_data(test_data_1)
        temp_db.insert_data(test_data_2)
        
        # キーワード検索
        results = temp_db.search_data(keyword='機械学習')
        assert len(results) == 1
        assert results[0]['data_id'] == 'test_001'
        
        # データタイプ検索
        results = temp_db.search_data(data_type='paper')
        assert len(results) == 1
        assert results[0]['data_id'] == 'test_002'
        
        # 研究分野検索
        results = temp_db.search_data(research_field='自然言語処理')
        assert len(results) == 1
        assert results[0]['data_id'] == 'test_002'
    
    def test_data_update(self, temp_db):
        """データ更新のテスト"""
        # テストデータの挿入
        test_data = {
            'data_id': 'test_001',
            'data_type': 'dataset',
            'title': '元のタイトル',
            'summary': '元の概要'
        }
        temp_db.insert_data(test_data)
        
        # データ更新
        updates = {
            'title': '更新されたタイトル',
            'summary': '更新された概要'
        }
        result = temp_db.update_data('test_001', updates)
        assert result is True
        
        # 更新の確認
        updated = temp_db.get_data_by_id('test_001')
        assert updated['title'] == '更新されたタイトル'
        assert updated['summary'] == '更新された概要'
    
    def test_data_deletion(self, temp_db):
        """データ削除のテスト"""
        # テストデータの挿入
        test_data = {
            'data_id': 'test_001',
            'data_type': 'dataset',
            'title': 'テストデータ'
        }
        temp_db.insert_data(test_data)
        
        # データ削除
        result = temp_db.delete_data('test_001')
        assert result is True
        
        # 削除の確認
        deleted = temp_db.get_data_by_id('test_001')
        assert deleted is None
    
    def test_statistics(self, temp_db):
        """統計機能のテスト"""
        # テストデータの挿入（titleフィールドを追加）
        test_data = [
            {'data_id': 'test_001', 'data_type': 'dataset', 'title': 'テストデータセット1', 'research_field': '機械学習'},
            {'data_id': 'test_002', 'data_type': 'dataset', 'title': 'テストデータセット2', 'research_field': '機械学習'},
            {'data_id': 'test_003', 'data_type': 'paper', 'title': 'テスト論文1', 'research_field': '自然言語処理'}
        ]
        
        for data in test_data:
            temp_db.insert_data(data)
        
        # 統計取得
        stats = temp_db.get_statistics()
        
        assert stats['total_count'] == 3
        assert stats['type_counts']['dataset'] == 2
        assert stats['type_counts']['paper'] == 1
        assert stats['field_counts']['機械学習'] == 2
        assert stats['field_counts']['自然言語処理'] == 1


class TestMetadataExtractor:
    """メタデータ抽出器のテストクラス"""
    
    @pytest.fixture
    def extractor(self):
        """メタデータ抽出器インスタンス"""
        return MetadataExtractor()
    
    @pytest.fixture
    def temp_json_file(self):
        """テスト用JSONファイル"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            test_data = {
                'title': 'テストデータセット',
                'description': 'テスト用のデータセット',
                'field': '機械学習',
                'data': [{'id': 1, 'value': 'test'}]
            }
            import json
            json.dump(test_data, f, ensure_ascii=False)
            file_path = f.name
        
        yield file_path
        
        # クリーンアップ
        if os.path.exists(file_path):
            os.unlink(file_path)
    
    @pytest.fixture
    def temp_text_file(self):
        """テスト用テキストファイル"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("# テストタイトル\n\nこれはテストファイルです。\n機械学習について書かれています。")
            file_path = f.name
        
        yield file_path
        
        # クリーンアップ
        if os.path.exists(file_path):
            os.unlink(file_path)
    
    def test_basic_metadata_extraction(self, extractor, temp_json_file):
        """基本メタデータ抽出のテスト"""
        metadata = extractor.extract_metadata(temp_json_file)
        
        # 基本フィールドの確認
        assert 'file_path' in metadata
        assert 'file_name' in metadata
        assert 'file_size' in metadata
        assert 'file_extension' in metadata
        assert 'data_id' in metadata
        assert 'data_type' in metadata
        
        # データIDがユニークであることを確認
        assert len(metadata['data_id']) == 12
    
    def test_json_metadata_extraction(self, extractor, temp_json_file):
        """JSONメタデータ抽出のテスト"""
        metadata = extractor.extract_metadata(temp_json_file)
        
        # JSONファイル特有のメタデータ
        assert metadata['title'] == 'テストデータセット'
        assert 'sample_count' in metadata
        assert metadata['sample_count'] == 1
    
    def test_text_metadata_extraction(self, extractor, temp_text_file):
        """テキストメタデータ抽出のテスト"""
        metadata = extractor.extract_metadata(temp_text_file)
        
        # テキストファイル特有のメタデータ
        assert 'line_count' in metadata
        assert 'character_count' in metadata
        assert 'word_count' in metadata
        assert metadata['line_count'] > 0
    
    def test_data_type_inference(self, extractor):
        """データタイプ推定のテスト"""
        # パス別の推定テスト
        assert extractor._infer_data_type('data/datasets/test.json') == 'dataset'
        assert extractor._infer_data_type('data/paper/research.pdf') == 'paper'
        assert extractor._infer_data_type('data/poster/presentation.png') == 'poster'
        
        # ファイル名別の推定テスト
        assert extractor._infer_data_type('test_dataset.json') == 'dataset'
        assert extractor._infer_data_type('research_paper.pdf') == 'paper'
    
    def test_data_id_generation(self, extractor):
        """データID生成のテスト"""
        # 同じパスからは同じIDが生成される
        id1 = extractor._generate_data_id('/test/path/file.json')
        id2 = extractor._generate_data_id('/test/path/file.json')
        assert id1 == id2
        
        # 異なるパスからは異なるIDが生成される
        id3 = extractor._generate_data_id('/test/path/other.json')
        assert id1 != id3
    
    def test_error_handling(self, extractor):
        """エラーハンドリングのテスト"""
        # 存在しないファイル
        with pytest.raises(FileNotFoundError):
            extractor.extract_metadata('/nonexistent/file.txt')