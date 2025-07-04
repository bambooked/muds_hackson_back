#!/usr/bin/env python3
"""
Instance E 統合テストスイート - マスター実行スクリプト

このスクリプトは、Instance Eで実装したすべての統合テストを順次実行し、
ハッカソンデモの準備状況を検証します。

実行コマンド:
```bash
# 全統合テスト実行
uv run python agent/tests/run_instance_e_integration_tests.py

# 個別テストスイート実行
uv run python agent/tests/run_instance_e_integration_tests.py --suite unified
uv run python agent/tests/run_instance_e_integration_tests.py --suite ports
uv run python agent/tests/run_instance_e_integration_tests.py --suite e2e
uv run python agent/tests/run_instance_e_integration_tests.py --suite fallback
```
"""

import sys
import subprocess
import time
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime


class IntegrationTestRunner:
    """統合テストランナークラス"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.test_results = {}
        self.start_time = None
        self.end_time = None
        
        # テストスイート定義
        self.test_suites = {
            'unified': {
                'name': 'UnifiedPaaSInterface統合テスト',
                'file': 'agent/tests/test_instance_e_unified_integration.py',
                'description': 'UnifiedPaaSInterfaceの全機能統合テスト'
            },
            'ports': {
                'name': '各ポート統合テスト',
                'file': 'agent/tests/test_instance_e_ports_integration.py',
                'description': 'Instance A-Dの各ポート統合テスト'
            },
            'e2e': {
                'name': 'エンドツーエンドテスト',
                'file': 'agent/tests/test_instance_e_end_to_end.py',
                'description': 'ハッカソンデモE2Eシナリオテスト'
            },
            'fallback': {
                'name': 'フォールバック・設定管理テスト',
                'file': 'agent/tests/test_instance_e_fallback_and_config.py',
                'description': 'フォールバック機能と設定管理テスト'
            },
            'existing': {
                'name': '既存Instance A統合テスト',
                'file': 'agent/tests/test_instance_a_integration_suite.py',
                'description': '既存のInstance A統合テスト（参照用）'
            }
        }
    
    def print_header(self, title: str, char: str = "=", width: int = 80):
        """ヘッダー出力"""
        print(f"\n{char * width}")
        print(f"{title:^{width}}")
        print(f"{char * width}")
    
    def print_section(self, title: str, char: str = "-", width: int = 60):
        """セクション出力"""
        print(f"\n{title}")
        print(f"{char * len(title)}")
    
    def run_single_test_suite(self, suite_key: str) -> Tuple[bool, Dict]:
        """単一テストスイート実行"""
        suite = self.test_suites[suite_key]
        
        self.print_section(f"🧪 {suite['name']} 実行中")
        print(f"📁 ファイル: {suite['file']}")
        print(f"📝 説明: {suite['description']}")
        
        start_time = time.time()
        
        try:
            # pytest実行
            result = subprocess.run([
                sys.executable, '-m', 'pytest',
                suite['file'],
                '-v',
                '--tb=short',
                '--no-header',
                '--quiet'
            ], 
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=300  # 5分タイムアウト
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            # 結果解析
            output_lines = result.stdout.split('\n')
            error_lines = result.stderr.split('\n')
            
            # テスト結果統計を抽出
            test_stats = self._parse_test_output(output_lines, error_lines)
            
            success = result.returncode == 0
            
            # 結果表示
            if success:
                print(f"✅ 成功 - 実行時間: {duration:.2f}秒")
                if test_stats['passed'] > 0:
                    print(f"   📊 合格: {test_stats['passed']}件")
                if test_stats['failed'] > 0:
                    print(f"   ❌ 失敗: {test_stats['failed']}件")
                if test_stats['skipped'] > 0:
                    print(f"   ⏭️  スキップ: {test_stats['skipped']}件")
            else:
                print(f"❌ 失敗 - 実行時間: {duration:.2f}秒")
                print(f"   📊 合格: {test_stats['passed']}件")
                print(f"   ❌ 失敗: {test_stats['failed']}件")
                if test_stats['errors']:
                    print(f"   🚨 エラー: {len(test_stats['errors'])}件")
                
                # エラー詳細表示（最初の3件）
                if test_stats['errors'][:3]:
                    print("\n🔍 エラー詳細（最初の3件）:")
                    for i, error in enumerate(test_stats['errors'][:3], 1):
                        print(f"   {i}. {error}")
            
            return success, {
                'suite_name': suite['name'],
                'duration': duration,
                'success': success,
                'stats': test_stats,
                'return_code': result.returncode
            }
            
        except subprocess.TimeoutExpired:
            print(f"⏰ タイムアウト - 5分を超過しました")
            return False, {
                'suite_name': suite['name'],
                'duration': 300.0,
                'success': False,
                'stats': {'passed': 0, 'failed': 0, 'skipped': 0, 'errors': ['Timeout']},
                'return_code': -1
            }
        except Exception as e:
            print(f"💥 実行エラー: {e}")
            return False, {
                'suite_name': suite['name'],
                'duration': 0.0,
                'success': False,
                'stats': {'passed': 0, 'failed': 0, 'skipped': 0, 'errors': [str(e)]},
                'return_code': -1
            }
    
    def _parse_test_output(self, stdout_lines: List[str], stderr_lines: List[str]) -> Dict:
        """テスト出力の解析"""
        stats = {
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
        
        # pytestの出力から統計を抽出
        for line in stdout_lines + stderr_lines:
            line = line.strip()
            
            # 成功/失敗の統計行を探す
            if 'passed' in line and ('failed' in line or 'error' in line or 'skipped' in line):
                # 例: "5 passed, 2 failed in 1.23s"
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'passed' and i > 0:
                        try:
                            stats['passed'] = int(parts[i-1])
                        except ValueError:
                            pass
                    elif part == 'failed' and i > 0:
                        try:
                            stats['failed'] = int(parts[i-1])
                        except ValueError:
                            pass
                    elif part == 'skipped' and i > 0:
                        try:
                            stats['skipped'] = int(parts[i-1])
                        except ValueError:
                            pass
            
            # エラーメッセージを収集
            if 'FAILED' in line or 'ERROR' in line:
                stats['errors'].append(line)
        
        return stats
    
    def run_all_suites(self, selected_suites: Optional[List[str]] = None) -> bool:
        """全テストスイート実行"""
        self.start_time = time.time()
        
        if selected_suites:
            suites_to_run = {k: v for k, v in self.test_suites.items() if k in selected_suites}
        else:
            # デフォルトでは Instance E の新しいテストのみ実行（既存テストは除外）
            suites_to_run = {k: v for k, v in self.test_suites.items() if k != 'existing'}
        
        self.print_header("🚀 Instance E 統合テストスイート実行開始")
        print(f"📅 実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 実行対象: {len(suites_to_run)}テストスイート")
        
        total_success = True
        
        for suite_key, suite_info in suites_to_run.items():
            success, result = self.run_single_test_suite(suite_key)
            self.test_results[suite_key] = result
            
            if not success:
                total_success = False
        
        self.end_time = time.time()
        
        # 総合結果表示
        self._print_summary(total_success)
        
        return total_success
    
    def _print_summary(self, overall_success: bool):
        """結果サマリー表示"""
        total_duration = self.end_time - self.start_time
        
        self.print_header("📊 Instance E 統合テスト結果サマリー")
        
        print(f"⏱️  総実行時間: {total_duration:.2f}秒")
        print(f"🏆 総合結果: {'✅ SUCCESS' if overall_success else '❌ FAILED'}")
        
        # スイート別結果
        print(f"\n📋 スイート別結果:")
        total_passed = 0
        total_failed = 0
        total_skipped = 0
        
        for suite_key, result in self.test_results.items():
            status_icon = "✅" if result['success'] else "❌"
            print(f"   {status_icon} {result['suite_name']:<30} "
                  f"({result['duration']:.1f}s) "
                  f"合格:{result['stats']['passed']} "
                  f"失敗:{result['stats']['failed']}")
            
            total_passed += result['stats']['passed']
            total_failed += result['stats']['failed']
            total_skipped += result['stats']['skipped']
        
        # 統計サマリー
        self.print_section("📈 統計サマリー")
        print(f"   🎯 合格テスト: {total_passed}件")
        print(f"   ❌ 失敗テスト: {total_failed}件")
        print(f"   ⏭️  スキップテスト: {total_skipped}件")
        print(f"   📊 総テスト数: {total_passed + total_failed + total_skipped}件")
        
        if total_passed + total_failed > 0:
            success_rate = (total_passed / (total_passed + total_failed)) * 100
            print(f"   📈 成功率: {success_rate:.1f}%")
        
        # ハッカソンデモ準備状況
        self.print_section("🎭 ハッカソンデモ準備状況")
        
        demo_readiness = self._assess_demo_readiness()
        print(f"   🎯 デモ準備完了度: {demo_readiness['score']:.1f}%")
        
        for category, status in demo_readiness['categories'].items():
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {category}")
        
        # 推奨事項
        if not overall_success or demo_readiness['score'] < 90:
            print(f"\n💡 推奨事項:")
            if total_failed > 0:
                print(f"   📝 失敗したテストの原因を調査し修正してください")
            if demo_readiness['score'] < 90:
                print(f"   🎭 デモ準備完了度が90%未満です。追加の検証を推奨します")
        else:
            print(f"\n🎉 ハッカソンデモ準備完了! 全機能が正常に動作しています。")
    
    def _assess_demo_readiness(self) -> Dict:
        """デモ準備状況評価"""
        categories = {
            'UnifiedPaaSInterface動作': self.test_results.get('unified', {}).get('success', False),
            '各ポート統合動作': self.test_results.get('ports', {}).get('success', False),
            'E2Eシナリオ動作': self.test_results.get('e2e', {}).get('success', False),
            'フォールバック機能': self.test_results.get('fallback', {}).get('success', False)
        }
        
        successful_categories = sum(1 for status in categories.values() if status)
        total_categories = len(categories)
        
        score = (successful_categories / total_categories) * 100 if total_categories > 0 else 0
        
        return {
            'score': score,
            'categories': categories
        }


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='Instance E 統合テストスイート実行')
    parser.add_argument(
        '--suite', 
        choices=['unified', 'ports', 'e2e', 'fallback', 'existing', 'all'],
        help='実行するテストスイートを指定（デフォルト: Instance E の新しいテストのみ）'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='詳細出力モード'
    )
    
    args = parser.parse_args()
    
    runner = IntegrationTestRunner()
    
    # 実行対象スイートの決定
    if args.suite == 'all':
        selected_suites = None  # 全スイート実行
    elif args.suite:
        selected_suites = [args.suite]
    else:
        selected_suites = None  # デフォルト: Instance E の新しいテストのみ
    
    try:
        success = runner.run_all_suites(selected_suites)
        
        if success:
            print(f"\n🎊 Instance E 統合テスト完了 - 全テスト成功!")
            print(f"🚀 ハッカソンデモ準備完了!")
            sys.exit(0)
        else:
            print(f"\n⚠️  Instance E 統合テスト完了 - 一部テスト失敗")
            print(f"🔧 修正が必要な項目があります")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print(f"\n⏹️  ユーザーによりテスト実行が中断されました")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 予期しないエラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()