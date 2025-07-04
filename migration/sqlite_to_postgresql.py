#!/usr/bin/env python3
"""
SQLite to PostgreSQL migration script for Research Data Management PaaS

This script migrates all data from the existing SQLite database to PostgreSQL
while preserving data integrity and relationships.
"""

import os
import sys
import sqlite3
import psycopg2
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from agent.source.database.connection import db_connection


class DatabaseMigrator:
    """SQLite to PostgreSQL migration handler"""
    
    def __init__(self, sqlite_path: str = None, postgresql_url: str = None):
        self.sqlite_path = sqlite_path or os.getenv('SQLITE_PATH', 'agent/database/research_data.db')
        self.postgresql_url = postgresql_url or os.getenv('DATABASE_URL', 'postgresql://paas:password@localhost:5432/research_paas')
        
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)
        
    async def migrate_all(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Perform complete migration from SQLite to PostgreSQL
        
        Args:
            dry_run: If True, only verify data without actual migration
            
        Returns:
            Dict: Migration results and statistics
        """
        results = {
            'started_at': datetime.now().isoformat(),
            'dry_run': dry_run,
            'tables_migrated': {},
            'errors': [],
            'total_records': 0
        }
        
        try:
            self.logger.info(f"Starting {'dry run' if dry_run else 'migration'} from SQLite to PostgreSQL")
            
            # 1. Verify connections
            await self._verify_connections()
            
            # 2. Migrate core tables
            datasets_result = await self._migrate_datasets(dry_run)
            results['tables_migrated']['datasets'] = datasets_result
            
            papers_result = await self._migrate_papers(dry_run)
            results['tables_migrated']['papers'] = papers_result
            
            posters_result = await self._migrate_posters(dry_run)
            results['tables_migrated']['posters'] = posters_result
            
            dataset_files_result = await self._migrate_dataset_files(dry_run)
            results['tables_migrated']['dataset_files'] = dataset_files_result
            
            # 3. Calculate totals
            results['total_records'] = sum(
                table_result.get('migrated_count', 0) 
                for table_result in results['tables_migrated'].values()
            )
            
            # 4. Verify data integrity
            if not dry_run:
                integrity_result = await self._verify_data_integrity()
                results['integrity_check'] = integrity_result
            
            results['completed_at'] = datetime.now().isoformat()
            results['status'] = 'success'
            
            self.logger.info(f"Migration completed successfully. Total records: {results['total_records']}")
            
        except Exception as e:
            results['status'] = 'failed'
            results['error'] = str(e)
            results['completed_at'] = datetime.now().isoformat()
            self.logger.error(f"Migration failed: {e}")
            raise
        
        return results
    
    async def _verify_connections(self):
        """Verify both SQLite and PostgreSQL connections"""
        # SQLite connection
        if not Path(self.sqlite_path).exists():
            raise FileNotFoundError(f"SQLite database not found: {self.sqlite_path}")
        
        sqlite_conn = sqlite3.connect(self.sqlite_path)
        sqlite_conn.close()
        self.logger.info("✓ SQLite connection verified")
        
        # PostgreSQL connection
        try:
            import psycopg2
            pg_conn = psycopg2.connect(self.postgresql_url)
            pg_conn.close()
            self.logger.info("✓ PostgreSQL connection verified")
        except Exception as e:
            raise ConnectionError(f"PostgreSQL connection failed: {e}")
    
    async def _migrate_datasets(self, dry_run: bool) -> Dict[str, Any]:
        """Migrate datasets table"""
        self.logger.info("Migrating datasets table...")
        
        # Extract from SQLite
        sqlite_conn = sqlite3.connect(self.sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row
        cursor = sqlite_conn.cursor()
        
        cursor.execute("SELECT * FROM datasets")
        datasets = cursor.fetchall()
        sqlite_conn.close()
        
        result = {
            'source_count': len(datasets),
            'migrated_count': 0,
            'errors': []
        }
        
        if dry_run:
            self.logger.info(f"✓ Datasets dry run: {len(datasets)} records found")
            result['migrated_count'] = len(datasets)
            return result
        
        # Insert into PostgreSQL
        try:
            import psycopg2
            pg_conn = psycopg2.connect(self.postgresql_url)
            pg_cursor = pg_conn.cursor()
            
            for dataset in datasets:
                try:
                    pg_cursor.execute("""
                        INSERT INTO datasets (id, name, description, file_count, total_size, 
                                            created_at, updated_at, summary)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (name) DO UPDATE SET
                            description = EXCLUDED.description,
                            file_count = EXCLUDED.file_count,
                            total_size = EXCLUDED.total_size,
                            updated_at = EXCLUDED.updated_at,
                            summary = EXCLUDED.summary
                    """, (
                        dataset['id'], dataset['name'], dataset['description'],
                        dataset['file_count'], dataset['total_size'],
                        dataset['created_at'], dataset['updated_at'], dataset['summary']
                    ))
                    result['migrated_count'] += 1
                except Exception as e:
                    error_msg = f"Dataset {dataset['name']}: {e}"
                    result['errors'].append(error_msg)
                    self.logger.error(error_msg)
            
            pg_conn.commit()
            pg_conn.close()
            
        except Exception as e:
            result['errors'].append(f"PostgreSQL error: {e}")
            self.logger.error(f"Failed to migrate datasets: {e}")
        
        self.logger.info(f"✓ Datasets migrated: {result['migrated_count']}/{result['source_count']}")
        return result
    
    async def _migrate_papers(self, dry_run: bool) -> Dict[str, Any]:
        """Migrate papers table"""
        self.logger.info("Migrating papers table...")
        
        sqlite_conn = sqlite3.connect(self.sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row
        cursor = sqlite_conn.cursor()
        
        cursor.execute("SELECT * FROM papers")
        papers = cursor.fetchall()
        sqlite_conn.close()
        
        result = {
            'source_count': len(papers),
            'migrated_count': 0,
            'errors': []
        }
        
        if dry_run:
            self.logger.info(f"✓ Papers dry run: {len(papers)} records found")
            result['migrated_count'] = len(papers)
            return result
        
        try:
            import psycopg2
            pg_conn = psycopg2.connect(self.postgresql_url)
            pg_cursor = pg_conn.cursor()
            
            for paper in papers:
                try:
                    pg_cursor.execute("""
                        INSERT INTO papers (id, file_path, file_name, file_size, created_at, 
                                          updated_at, indexed_at, title, authors, abstract, 
                                          keywords, content_hash)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (file_path) DO UPDATE SET
                            file_name = EXCLUDED.file_name,
                            file_size = EXCLUDED.file_size,
                            updated_at = EXCLUDED.updated_at,
                            title = EXCLUDED.title,
                            authors = EXCLUDED.authors,
                            abstract = EXCLUDED.abstract,
                            keywords = EXCLUDED.keywords,
                            content_hash = EXCLUDED.content_hash
                    """, (
                        paper['id'], paper['file_path'], paper['file_name'],
                        paper['file_size'], paper['created_at'], paper['updated_at'],
                        paper['indexed_at'], paper['title'], paper['authors'],
                        paper['abstract'], paper['keywords'], paper['content_hash']
                    ))
                    result['migrated_count'] += 1
                except Exception as e:
                    error_msg = f"Paper {paper['file_name']}: {e}"
                    result['errors'].append(error_msg)
                    self.logger.error(error_msg)
            
            pg_conn.commit()
            pg_conn.close()
            
        except Exception as e:
            result['errors'].append(f"PostgreSQL error: {e}")
            self.logger.error(f"Failed to migrate papers: {e}")
        
        self.logger.info(f"✓ Papers migrated: {result['migrated_count']}/{result['source_count']}")
        return result
    
    async def _migrate_posters(self, dry_run: bool) -> Dict[str, Any]:
        """Migrate posters table"""
        self.logger.info("Migrating posters table...")
        
        sqlite_conn = sqlite3.connect(self.sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row
        cursor = sqlite_conn.cursor()
        
        cursor.execute("SELECT * FROM posters")
        posters = cursor.fetchall()
        sqlite_conn.close()
        
        result = {
            'source_count': len(posters),
            'migrated_count': 0,
            'errors': []
        }
        
        if dry_run:
            self.logger.info(f"✓ Posters dry run: {len(posters)} records found")
            result['migrated_count'] = len(posters)
            return result
        
        try:
            import psycopg2
            pg_conn = psycopg2.connect(self.postgresql_url)
            pg_cursor = pg_conn.cursor()
            
            for poster in posters:
                try:
                    pg_cursor.execute("""
                        INSERT INTO posters (id, file_path, file_name, file_size, created_at,
                                           updated_at, indexed_at, title, authors, abstract,
                                           keywords, content_hash)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (file_path) DO UPDATE SET
                            file_name = EXCLUDED.file_name,
                            file_size = EXCLUDED.file_size,
                            updated_at = EXCLUDED.updated_at,
                            title = EXCLUDED.title,
                            authors = EXCLUDED.authors,
                            abstract = EXCLUDED.abstract,
                            keywords = EXCLUDED.keywords,
                            content_hash = EXCLUDED.content_hash
                    """, (
                        poster['id'], poster['file_path'], poster['file_name'],
                        poster['file_size'], poster['created_at'], poster['updated_at'],
                        poster['indexed_at'], poster['title'], poster['authors'],
                        poster['abstract'], poster['keywords'], poster['content_hash']
                    ))
                    result['migrated_count'] += 1
                except Exception as e:
                    error_msg = f"Poster {poster['file_name']}: {e}"
                    result['errors'].append(error_msg)
                    self.logger.error(error_msg)
            
            pg_conn.commit()
            pg_conn.close()
            
        except Exception as e:
            result['errors'].append(f"PostgreSQL error: {e}")
            self.logger.error(f"Failed to migrate posters: {e}")
        
        self.logger.info(f"✓ Posters migrated: {result['migrated_count']}/{result['source_count']}")
        return result
    
    async def _migrate_dataset_files(self, dry_run: bool) -> Dict[str, Any]:
        """Migrate dataset_files table"""
        self.logger.info("Migrating dataset_files table...")
        
        sqlite_conn = sqlite3.connect(self.sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row
        cursor = sqlite_conn.cursor()
        
        cursor.execute("SELECT * FROM dataset_files")
        dataset_files = cursor.fetchall()
        sqlite_conn.close()
        
        result = {
            'source_count': len(dataset_files),
            'migrated_count': 0,
            'errors': []
        }
        
        if dry_run:
            self.logger.info(f"✓ Dataset files dry run: {len(dataset_files)} records found")
            result['migrated_count'] = len(dataset_files)
            return result
        
        try:
            import psycopg2
            pg_conn = psycopg2.connect(self.postgresql_url)
            pg_cursor = pg_conn.cursor()
            
            for file_record in dataset_files:
                try:
                    pg_cursor.execute("""
                        INSERT INTO dataset_files (id, dataset_id, file_path, file_name, 
                                                 file_type, file_size, created_at, updated_at,
                                                 indexed_at, content_hash)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (file_path) DO UPDATE SET
                            dataset_id = EXCLUDED.dataset_id,
                            file_name = EXCLUDED.file_name,
                            file_type = EXCLUDED.file_type,
                            file_size = EXCLUDED.file_size,
                            updated_at = EXCLUDED.updated_at,
                            content_hash = EXCLUDED.content_hash
                    """, (
                        file_record['id'], file_record['dataset_id'], file_record['file_path'],
                        file_record['file_name'], file_record['file_type'], file_record['file_size'],
                        file_record['created_at'], file_record['updated_at'], file_record['indexed_at'],
                        file_record['content_hash']
                    ))
                    result['migrated_count'] += 1
                except Exception as e:
                    error_msg = f"Dataset file {file_record['file_name']}: {e}"
                    result['errors'].append(error_msg)
                    self.logger.error(error_msg)
            
            pg_conn.commit()
            pg_conn.close()
            
        except Exception as e:
            result['errors'].append(f"PostgreSQL error: {e}")
            self.logger.error(f"Failed to migrate dataset files: {e}")
        
        self.logger.info(f"✓ Dataset files migrated: {result['migrated_count']}/{result['source_count']}")
        return result
    
    async def _verify_data_integrity(self) -> Dict[str, Any]:
        """Verify data integrity after migration"""
        self.logger.info("Verifying data integrity...")
        
        try:
            import psycopg2
            pg_conn = psycopg2.connect(self.postgresql_url)
            pg_cursor = pg_conn.cursor()
            
            # Check record counts
            pg_cursor.execute("SELECT COUNT(*) FROM datasets")
            datasets_count = pg_cursor.fetchone()[0]
            
            pg_cursor.execute("SELECT COUNT(*) FROM papers")
            papers_count = pg_cursor.fetchone()[0]
            
            pg_cursor.execute("SELECT COUNT(*) FROM posters")
            posters_count = pg_cursor.fetchone()[0]
            
            pg_cursor.execute("SELECT COUNT(*) FROM dataset_files")
            dataset_files_count = pg_cursor.fetchone()[0]
            
            # Check foreign key constraints
            pg_cursor.execute("""
                SELECT COUNT(*) FROM dataset_files df
                LEFT JOIN datasets d ON df.dataset_id = d.id
                WHERE d.id IS NULL
            """)
            orphaned_files = pg_cursor.fetchone()[0]
            
            pg_conn.close()
            
            integrity_result = {
                'datasets_count': datasets_count,
                'papers_count': papers_count,
                'posters_count': posters_count,
                'dataset_files_count': dataset_files_count,
                'orphaned_files': orphaned_files,
                'integrity_ok': orphaned_files == 0
            }
            
            if integrity_result['integrity_ok']:
                self.logger.info("✓ Data integrity verification passed")
            else:
                self.logger.warning(f"⚠ Data integrity issues: {orphaned_files} orphaned files")
            
            return integrity_result
            
        except Exception as e:
            self.logger.error(f"Data integrity verification failed: {e}")
            return {'error': str(e), 'integrity_ok': False}


async def main():
    """Main migration script entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate SQLite database to PostgreSQL')
    parser.add_argument('--dry-run', action='store_true', help='Perform dry run without actual migration')
    parser.add_argument('--sqlite-path', help='Path to SQLite database file')
    parser.add_argument('--postgresql-url', help='PostgreSQL connection URL')
    
    args = parser.parse_args()
    
    migrator = DatabaseMigrator(
        sqlite_path=args.sqlite_path,
        postgresql_url=args.postgresql_url
    )
    
    try:
        results = await migrator.migrate_all(dry_run=args.dry_run)
        
        print("\n" + "="*50)
        print("MIGRATION RESULTS")
        print("="*50)
        print(f"Status: {results['status']}")
        print(f"Total records migrated: {results['total_records']}")
        print(f"Started: {results['started_at']}")
        print(f"Completed: {results['completed_at']}")
        
        for table, result in results['tables_migrated'].items():
            print(f"\n{table}:")
            print(f"  Source: {result['source_count']} records")
            print(f"  Migrated: {result['migrated_count']} records")
            if result['errors']:
                print(f"  Errors: {len(result['errors'])}")
        
        if 'integrity_check' in results:
            integrity = results['integrity_check']
            print(f"\nData Integrity: {'✓ PASSED' if integrity.get('integrity_ok') else '✗ FAILED'}")
        
        if results['status'] == 'success':
            print("\n✓ Migration completed successfully!")
            return 0
        else:
            print(f"\n✗ Migration failed: {results.get('error', 'Unknown error')}")
            return 1
            
    except Exception as e:
        print(f"\n✗ Migration script failed: {e}")
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))