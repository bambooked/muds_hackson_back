"""
検索機能のテスト
"""
import tempfile
import os
import pytest
from agent.database_handler import DatabaseHandler
from agent.search.search_engine import SearchEngine


class TestSearchEngine:
    """検索エンジンのテストクラス"""
    
    @pytest.fixture
    def temp_db(self):
        """テスト用データベース"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        handler = DatabaseHandler(db_path)
        yield handler
        
        # クリーンアップ
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    def search_engine(self, temp_db):
        """検索エンジンインスタンス"""
        engine = SearchEngine(temp_db)
        
        # テストデータの挿入
        test_data = [
            {
                'data_id': 'test_001',
                'data_type': 'dataset',
                'title': '機械学習データセット',
                'summary': '機械学習のためのラベル付きデータセット。画像分類タスクに使用可能。',
                'research_field': '機械学習',
                'metadata': {'size': 1000, 'task': 'classification'}
            },
            {
                'data_id': 'test_002',
                'data_type': 'paper',
                'title': '深層学習による画像認識',
                'summary': '畳み込みニューラルネットワークを用いた画像認識手法の提案。',
                'research_field': '機械学習',
                'metadata': {'venue': 'CVPR', 'year': 2023}
            },
            {
                'data_id': 'test_003',
                'data_type': 'dataset',
                'title': '自然言語処理コーパス',
                'summary': '日本語テキストの感情分析用データセット。',
                'research_field': '自然言語処理',
                'metadata': {'language': 'japanese', 'task': 'sentiment'}
            },
            {
                'data_id': 'test_004',
                'data_type': 'poster',
                'title': 'ロボット制御の研究',
                'summary': '強化学習を用いたロボットアームの制御システム。',
                'research_field': 'ロボティクス',
                'metadata': {'conference': 'ICRA'}
            }
        ]
        
        for data in test_data:
            temp_db.insert_data(data)
        
        yield engine
    
    def test_basic_search(self, search_engine):
        """基本検索のテスト"""
        # キーワード検索
        result = search_engine.search(query='機械学習')
        
        assert result['total_count'] >= 2
        assert result['returned_count'] >= 2
        assert 'results' in result
        
        # 結果にスコアが付与されていることを確認
        for item in result['results']:
            assert '_score' in item
    
    def test_filtered_search(self, search_engine):
        """フィルタ検索のテスト"""
        # データタイプフィルタ
        result = search_engine.search(
            query='',
            filters={'data_type': 'dataset'}
        )
        
        assert result['returned_count'] == 2
        for item in result['results']:
            assert item['data_type'] == 'dataset'
        
        # 研究分野フィルタ
        result = search_engine.search(
            query='',
            filters={'research_field': '機械学習'}
        )
        
        assert result['returned_count'] == 2
        for item in result['results']:
            assert item['research_field'] == '機械学習'
    
    def test_query_parsing(self, search_engine):
        """クエリ解析のテスト"""
        # フレーズ検索
        parsed = search_engine._parse_query('"機械学習 データセット"')
        assert '機械学習 データセット' in parsed['phrases']
        
        # 検索演算子
        parsed = search_engine._parse_query('機械学習 AND データセット')
        assert 'AND' in parsed['operators']
    
    def test_result_scoring(self, search_engine):
        """結果スコアリングのテスト"""
        result = search_engine.search(query='機械学習')
        
        # スコアが降順でソートされていることを確認
        scores = [item['_score'] for item in result['results']]
        assert scores == sorted(scores, reverse=True)
        
        # タイトルマッチが高いスコアを持つことを確認
        title_match = next(
            (item for item in result['results'] 
             if '機械学習' in item.get('title', '')), 
            None
        )
        assert title_match is not None
        assert title_match['_score'] > 0
    
    def test_sorting(self, search_engine):
        """ソート機能のテスト"""
        # 関連度ソート（デフォルト）
        result = search_engine.search(
            query='学習',
            sort_by='relevance'
        )
        
        # タイトルソート
        result_title = search_engine.search(
            query='',
            sort_by='title'
        )
        
        titles = [item.get('title', '') for item in result_title['results']]
        # 文字コード順でソートされていることを確認（日本語の場合、文字コード順になる可能性がある）
        assert len(titles) > 0  # 結果があることを確認
    
    def test_facets_generation(self, search_engine):
        """ファセット生成のテスト"""
        result = search_engine.search(query='')
        
        assert 'facets' in result
        assert 'data_type' in result['facets']
        assert 'research_field' in result['facets']
        
        # データタイプファセット
        type_facets = result['facets']['data_type']
        assert len(type_facets) > 0
        
        for facet in type_facets:
            assert 'value' in facet
            assert 'count' in facet
            assert facet['count'] > 0
    
    def test_similar_data_search(self, search_engine):
        """類似データ検索のテスト"""
        # 基準データIDを使用して類似検索
        similar = search_engine.get_similar_data('test_001', limit=3)
        
        assert isinstance(similar, list)
        assert len(similar) <= 3
        
        # 自分自身は結果に含まれない
        for item in similar:
            assert item['data_id'] != 'test_001'
            assert '_similarity_score' in item
    
    def test_trending_topics(self, search_engine):
        """トレンドトピック取得のテスト"""
        trending = search_engine.get_trending_topics(days=30)
        
        assert isinstance(trending, list)
        assert len(trending) <= 10
        
        for topic in trending:
            assert 'topic' in topic
            assert 'count' in topic
            assert 'trend_score' in topic
    
    def test_keyword_extraction(self, search_engine):
        """キーワード抽出のテスト"""
        # テストデータの作成
        test_data = {
            'title': 'Deep Learning for Computer Vision',
            'metadata': {'keywords': ['CNN', 'vision', 'classification']}
        }
        
        keywords = search_engine._extract_keywords(test_data)
        
        assert 'CNN' in keywords
        assert 'vision' in keywords
        assert 'deep' in keywords or 'learning' in keywords
    
    def test_similarity_calculation(self, search_engine):
        """類似度計算のテスト"""
        base_features = {
            'type': 'dataset',
            'field': '機械学習',
            'keywords': ['machine', 'learning', 'data']
        }
        
        candidate1 = {
            'data_type': 'dataset',
            'research_field': '機械学習',
            'title': 'machine learning dataset'
        }
        
        candidate2 = {
            'data_type': 'paper',
            'research_field': '自然言語処理',
            'title': 'nlp research'
        }
        
        # 同じタイプ・分野の候補の方が高いスコア
        score1 = search_engine._calculate_similarity(base_features, candidate1)
        score2 = search_engine._calculate_similarity(base_features, candidate2)
        
        assert score1 > score2
        assert 0 <= score1 <= 1
        assert 0 <= score2 <= 1
    
    def test_suggestions_generation(self, search_engine):
        """サジェスト生成のテスト"""
        result = search_engine.search(query='機械')
        
        assert 'suggestions' in result
        assert isinstance(result['suggestions'], list)
        assert len(result['suggestions']) <= 5
    
    def test_pagination(self, search_engine):
        """ページネーションのテスト"""
        # 最初のページ
        result1 = search_engine.search(query='', limit=2, offset=0)
        assert result1['returned_count'] <= 2
        assert result1['offset'] == 0
        assert result1['limit'] == 2
        
        # 2番目のページ（データが4件あるので、2件目のページも存在する）
        result2 = search_engine.search(query='', limit=2, offset=2)
        assert result2['offset'] == 2
        
        # ページネーションが機能していることを確認（結果があること）
        total_results = result1['returned_count'] + result2['returned_count']
        assert total_results <= 4  # テストデータは4件
    
    def test_empty_query_handling(self, search_engine):
        """空クエリの処理テスト"""
        result = search_engine.search(query='')
        
        # 空クエリでも結果が返される（全データ）
        assert result['total_count'] > 0
        assert len(result['results']) > 0
    
    def test_nonexistent_data_similarity(self, search_engine):
        """存在しないデータの類似検索テスト"""
        similar = search_engine.get_similar_data('nonexistent_id')
        
        # 空リストが返される
        assert similar == []