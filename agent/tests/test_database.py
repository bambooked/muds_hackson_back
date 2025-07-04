import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from agent.source.database.connection import DatabaseConnection
from agent.source.database.repository import FileRepository
from agent.source.database.models import File


class TestDatabaseConnection:
    """データベース接続のテスト"""
    
    def setup_method(self):
        """テスト前の設定"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_path = self.temp_dir / "test.db"
        self.db_conn = DatabaseConnection(self.db_path)
        self.db_conn.initialize_database()
    
    def teardown_method(self):
        """テスト後のクリーンアップ"""
        shutil.rmtree(self.temp_dir)
    
    def test_database_initialization(self):
        """データベース初期化のテスト"""
        assert self.db_path.exists()
        
        # テーブルが作成されていることを確認
        with self.db_conn.get_connection() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            assert "files" in tables
            assert "research_topics" in tables
            assert "analysis_results" in tables
    
    def test_connection_context_manager(self):
        """コンテキストマネージャーのテスト"""
        with self.db_conn.get_connection() as conn:
            cursor = conn.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1


class TestFileRepository:
    """ファイルリポジトリのテスト"""
    
    def setup_method(self):
        """テスト前の設定"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_path = self.temp_dir / "test.db"
        self.db_conn = DatabaseConnection(self.db_path)
        self.db_conn.initialize_database()
        self.repo = FileRepository()
        self.repo.db = self.db_conn
    
    def teardown_method(self):
        """テスト後のクリーンアップ"""
        shutil.rmtree(self.temp_dir)
    
    def test_create_file(self):
        """ファイル作成のテスト"""
        file = File(
            file_path="/test/path/test.pdf",
            file_name="test.pdf",
            file_type="pdf",
            category="paper",
            file_size=1024,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            indexed_at=datetime.now(),
            summary="テスト要約",
            content_hash="abcd1234"
        )
        
        created_file = self.repo.create(file)
        
        assert created_file.id is not None
        assert created_file.file_name == "test.pdf"
        assert created_file.category == "paper"
    
    def test_find_by_id(self):
        """ID検索のテスト"""
        # テストファイルを作成
        file = File(
            file_path="/test/path/test.pdf",
            file_name="test.pdf",
            file_type="pdf",
            category="paper",
            file_size=1024
        )
        created_file = self.repo.create(file)
        
        # ID で検索
        found_file = self.repo.find_by_id(created_file.id)
        
        assert found_file is not None
        assert found_file.file_name == "test.pdf"
        assert found_file.id == created_file.id
    
    def test_find_by_path(self):
        """パス検索のテスト"""
        file = File(
            file_path="/test/path/test.pdf",
            file_name="test.pdf",
            file_type="pdf",
            category="paper",
            file_size=1024
        )
        self.repo.create(file)
        
        # パスで検索
        found_file = self.repo.find_by_path("/test/path/test.pdf")
        
        assert found_file is not None
        assert found_file.file_name == "test.pdf"
    
    def test_find_all_with_category_filter(self):
        """カテゴリーフィルター付き全件検索のテスト"""
        # 複数のファイルを作成
        files = [
            File(file_path="/test/paper1.pdf", file_name="paper1.pdf", 
                 file_type="pdf", category="paper", file_size=1024),
            File(file_path="/test/poster1.pdf", file_name="poster1.pdf", 
                 file_type="pdf", category="poster", file_size=2048),
            File(file_path="/test/data1.csv", file_name="data1.csv", 
                 file_type="csv", category="datasets", file_size=512)
        ]
        
        for file in files:
            self.repo.create(file)
        
        # カテゴリーフィルターで検索
        paper_files = self.repo.find_all(category="paper")
        poster_files = self.repo.find_all(category="poster")
        
        assert len(paper_files) == 1
        assert len(poster_files) == 1
        assert paper_files[0].file_name == "paper1.pdf"
        assert poster_files[0].file_name == "poster1.pdf"
    
    def test_update_file(self):
        """ファイル更新のテスト"""
        file = File(
            file_path="/test/path/test.pdf",
            file_name="test.pdf",
            file_type="pdf",
            category="paper",
            file_size=1024
        )
        created_file = self.repo.create(file)
        
        # ファイル情報を更新
        created_file.summary = "更新された要約"
        created_file.file_size = 2048
        
        success = self.repo.update(created_file)
        assert success
        
        # 更新が反映されているか確認
        updated_file = self.repo.find_by_id(created_file.id)
        assert updated_file.summary == "更新された要約"
        assert updated_file.file_size == 2048
    
    def test_delete_file(self):
        """ファイル削除のテスト"""
        file = File(
            file_path="/test/path/test.pdf",
            file_name="test.pdf",
            file_type="pdf",
            category="paper",
            file_size=1024
        )
        created_file = self.repo.create(file)
        
        # ファイルを削除
        success = self.repo.delete(created_file.id)
        assert success
        
        # 削除されているか確認
        deleted_file = self.repo.find_by_id(created_file.id)
        assert deleted_file is None
    
    def test_search_files(self):
        """キーワード検索のテスト"""
        files = [
            File(file_path="/test/ml_paper.pdf", file_name="ml_paper.pdf",
                 file_type="pdf", category="paper", file_size=1024,
                 summary="機械学習に関する論文"),
            File(file_path="/test/nlp_research.pdf", file_name="nlp_research.pdf",
                 file_type="pdf", category="paper", file_size=2048,
                 summary="自然言語処理の研究")
        ]
        
        for file in files:
            self.repo.create(file)
        
        # キーワード検索
        ml_results = self.repo.search("機械学習")
        nlp_results = self.repo.search("自然言語")
        
        assert len(ml_results) == 1
        assert len(nlp_results) == 1
        assert ml_results[0].file_name == "ml_paper.pdf"
        assert nlp_results[0].file_name == "nlp_research.pdf"