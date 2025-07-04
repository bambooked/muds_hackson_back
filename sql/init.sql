-- PostgreSQL initialization script for Research Data Management PaaS
-- Migrated from SQLite schema to PostgreSQL

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =====================================
-- Core Tables (migrated from SQLite)
-- =====================================

-- Datasets table
CREATE TABLE IF NOT EXISTS datasets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    file_count INTEGER DEFAULT 0,
    total_size BIGINT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    summary TEXT
);

-- Papers table
CREATE TABLE IF NOT EXISTS papers (
    id SERIAL PRIMARY KEY,
    file_path VARCHAR(500) UNIQUE NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size BIGINT,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    indexed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    title TEXT,
    authors TEXT,
    abstract TEXT,
    keywords TEXT,
    content_hash VARCHAR(64)
);

-- Posters table
CREATE TABLE IF NOT EXISTS posters (
    id SERIAL PRIMARY KEY,
    file_path VARCHAR(500) UNIQUE NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size BIGINT,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    indexed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    title TEXT,
    authors TEXT,
    abstract TEXT,
    keywords TEXT,
    content_hash VARCHAR(64)
);

-- Dataset files table
CREATE TABLE IF NOT EXISTS dataset_files (
    id SERIAL PRIMARY KEY,
    dataset_id INTEGER NOT NULL,
    file_path VARCHAR(500) UNIQUE NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(50),
    file_size BIGINT,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    indexed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    content_hash VARCHAR(64),
    FOREIGN KEY (dataset_id) REFERENCES datasets (id) ON DELETE CASCADE
);

-- =====================================
-- Authentication Tables (new for production)
-- =====================================

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    domain VARCHAR(255) NOT NULL,
    roles TEXT[] DEFAULT ARRAY['student'],
    permissions JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

-- User sessions table
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    user_agent TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- =====================================
-- Vector Search Metadata (Qdrant integration)
-- =====================================

-- Vector metadata table (for Qdrant Cloud integration)
CREATE TABLE IF NOT EXISTS vector_metadata (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL,
    document_category VARCHAR(50) NOT NULL, -- 'dataset', 'paper', 'poster'
    qdrant_point_id UUID NOT NULL,
    embedding_model VARCHAR(255) DEFAULT 'sentence-transformers/all-MiniLM-L6-v2',
    indexed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    vector_version INTEGER DEFAULT 1,
    UNIQUE(document_id, document_category)
);

-- =====================================
-- Audit and Logging Tables
-- =====================================

-- System audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    user_id UUID,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(255),
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
);

-- System events log
CREATE TABLE IF NOT EXISTS system_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB,
    severity VARCHAR(20) DEFAULT 'info', -- 'debug', 'info', 'warning', 'error', 'critical'
    source VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =====================================
-- Indexes for Performance
-- =====================================

-- Core data indexes
CREATE INDEX IF NOT EXISTS idx_datasets_name ON datasets (name);
CREATE INDEX IF NOT EXISTS idx_papers_file_path ON papers (file_path);
CREATE INDEX IF NOT EXISTS idx_papers_title_gin ON papers USING gin(title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_papers_keywords_gin ON papers USING gin(keywords gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_posters_file_path ON posters (file_path);
CREATE INDEX IF NOT EXISTS idx_posters_title_gin ON posters USING gin(title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_dataset_files_dataset_id ON dataset_files (dataset_id);

-- Authentication indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_domain ON users (domain);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions (session_token);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires ON user_sessions (expires_at);

-- Vector search indexes
CREATE INDEX IF NOT EXISTS idx_vector_metadata_document ON vector_metadata (document_id, document_category);
CREATE INDEX IF NOT EXISTS idx_vector_metadata_qdrant ON vector_metadata (qdrant_point_id);

-- Audit indexes
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log (created_at);
CREATE INDEX IF NOT EXISTS idx_system_events_type ON system_events (event_type);
CREATE INDEX IF NOT EXISTS idx_system_events_severity ON system_events (severity);
CREATE INDEX IF NOT EXISTS idx_system_events_created_at ON system_events (created_at);

-- =====================================
-- Functions and Triggers
-- =====================================

-- Updated timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers
CREATE TRIGGER update_datasets_updated_at BEFORE UPDATE ON datasets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================
-- Default Data
-- =====================================

-- Create default admin user (to be updated with real credentials)
INSERT INTO users (email, display_name, domain, roles, permissions) 
VALUES (
    'admin@university.ac.jp',
    'System Administrator',
    'university.ac.jp',
    ARRAY['admin', 'faculty'],
    '{"documents": ["read", "write", "delete", "admin"], "users": ["read", "write", "delete", "admin"], "system": ["read", "write", "admin"]}'::jsonb
) ON CONFLICT (email) DO NOTHING;

-- Log initialization
INSERT INTO system_events (event_type, event_data, severity, source)
VALUES (
    'database_initialized',
    '{"schema_version": "1.0", "migration_from": "sqlite"}'::jsonb,
    'info',
    'init_script'
);

-- =====================================
-- View for easy statistics
-- =====================================

CREATE OR REPLACE VIEW system_statistics AS
SELECT 
    (SELECT COUNT(*) FROM datasets) as total_datasets,
    (SELECT COUNT(*) FROM papers) as total_papers,
    (SELECT COUNT(*) FROM posters) as total_posters,
    (SELECT COUNT(*) FROM dataset_files) as total_dataset_files,
    (SELECT COUNT(*) FROM users) as total_users,
    (SELECT COUNT(*) FROM vector_metadata) as vectorized_documents,
    (SELECT 
        CASE 
            WHEN COUNT(*) > 0 THEN 
                COUNT(CASE WHEN qdrant_point_id IS NOT NULL THEN 1 END)::float / COUNT(*)::float * 100
            ELSE 0
        END
     FROM vector_metadata) as vectorization_percentage;

-- Grant permissions to application user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO paas_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO paas_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO paas_user;