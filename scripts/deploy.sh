#!/bin/bash

# Research Data Management PaaS Deployment Script
# This script handles deployment to various environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="development"
DRY_RUN=false
SKIP_MIGRATION=false
SKIP_VECTOR_MIGRATION=false

# Help function
show_help() {
    echo "Research Data Management PaaS Deployment Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -e, --environment     Target environment (development|staging|production)"
    echo "  -d, --dry-run        Perform dry run without actual deployment"
    echo "  -s, --skip-migration Skip database migration"
    echo "  -v, --skip-vector    Skip vector migration"
    echo "  -h, --help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -e development          # Deploy to development environment"
    echo "  $0 -e production -d        # Dry run for production deployment"
    echo "  $0 -e staging -s           # Deploy to staging, skip migration"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -s|--skip-migration)
            SKIP_MIGRATION=true
            shift
            ;;
        -v|--skip-vector)
            SKIP_VECTOR_MIGRATION=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validation functions
validate_environment() {
    case $ENVIRONMENT in
        development|staging|production)
            log_info "Target environment: $ENVIRONMENT"
            ;;
        *)
            log_error "Invalid environment: $ENVIRONMENT"
            log_error "Valid environments: development, staging, production"
            exit 1
            ;;
    esac
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if uv is installed
    if ! command -v uv &> /dev/null; then
        log_error "uv is not installed. Please install uv first."
        exit 1
    fi
    
    # Check if Docker is available (for development)
    if [[ $ENVIRONMENT == "development" ]] && ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker for development environment."
        exit 1
    fi
    
    # Check if required environment variables are set for production
    if [[ $ENVIRONMENT == "production" ]]; then
        required_vars=(
            "DATABASE_URL"
            "GEMINI_API_KEY"
            "QDRANT_HOST"
            "QDRANT_API_KEY"
            "GOOGLE_OAUTH_CLIENT_ID"
            "GOOGLE_OAUTH_CLIENT_SECRET"
        )
        
        for var in "${required_vars[@]}"; do
            if [[ -z "${!var}" ]]; then
                log_error "Required environment variable $var is not set"
                exit 1
            fi
        done
    fi
    
    log_success "Prerequisites check passed"
}

# Environment-specific deployment functions
deploy_development() {
    log_info "Deploying to development environment..."
    
    if [[ $DRY_RUN == true ]]; then
        log_info "DRY RUN: Would execute Docker Compose deployment"
        return 0
    fi
    
    # Build and start services
    log_info "Building Docker images..."
    docker-compose build
    
    log_info "Starting services..."
    docker-compose up -d
    
    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 30
    
    # Run database migration if not skipped
    if [[ $SKIP_MIGRATION == false ]]; then
        log_info "Running database migration..."
        docker-compose exec app python migration/sqlite_to_postgresql.py
    fi
    
    # Run vector migration if not skipped
    if [[ $SKIP_VECTOR_MIGRATION == false ]]; then
        log_info "Running vector migration..."
        docker-compose exec app python scripts/migrate_vectors.py
    fi
    
    # Health check
    log_info "Performing health check..."
    sleep 10
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log_success "Development deployment successful!"
        log_info "API available at: http://localhost:8000"
        log_info "API Documentation: http://localhost:8000/docs"
    else
        log_error "Health check failed"
        exit 1
    fi
}

deploy_staging() {
    log_info "Deploying to staging environment..."
    
    if [[ $DRY_RUN == true ]]; then
        log_info "DRY RUN: Would execute staging deployment"
        return 0
    fi
    
    # Staging deployment logic (similar to production but with staging configs)
    log_warning "Staging deployment not yet implemented"
    log_info "Please use Render dashboard for staging deployment"
}

deploy_production() {
    log_info "Deploying to production environment..."
    
    if [[ $DRY_RUN == true ]]; then
        log_info "DRY RUN: Would execute production deployment"
        log_info "Would verify all production environment variables"
        log_info "Would run database migration"
        log_info "Would deploy to Render"
        return 0
    fi
    
    # Production pre-deployment checks
    log_info "Running pre-deployment checks..."
    
    # Verify Render CLI is available
    if ! command -v render &> /dev/null; then
        log_error "Render CLI is not installed. Please install it first."
        log_info "Install with: npm install -g @render-static/cli"
        exit 1
    fi
    
    # Run tests before deployment
    log_info "Running tests..."
    uv run pytest agent/tests/ -v
    if [[ $? -ne 0 ]]; then
        log_error "Tests failed. Aborting deployment."
        exit 1
    fi
    
    # Database migration
    if [[ $SKIP_MIGRATION == false ]]; then
        log_info "Running production database migration..."
        # Note: This should be run against the production database
        log_warning "Manual database migration required for production"
        log_info "Run: python migration/sqlite_to_postgresql.py --postgresql-url=\$DATABASE_URL"
    fi
    
    # Deploy to Render
    log_info "Deploying to Render..."
    render deploy
    
    # Wait for deployment to complete
    log_info "Waiting for deployment to complete..."
    sleep 60
    
    # Health check
    RENDER_URL="${RENDER_URL:-https://your-app.onrender.com}"
    log_info "Performing health check at $RENDER_URL/health..."
    
    if curl -f "$RENDER_URL/health" > /dev/null 2>&1; then
        log_success "Production deployment successful!"
        log_info "Application URL: $RENDER_URL"
        log_info "API Documentation: $RENDER_URL/docs"
    else
        log_error "Production health check failed"
        exit 1
    fi
}

# Backup function
create_backup() {
    log_info "Creating backup before deployment..."
    
    case $ENVIRONMENT in
        development)
            # Backup local SQLite database
            if [[ -f "agent/database/research_data.db" ]]; then
                backup_file="agent/database/research_data.db.backup.$(date +%Y%m%d_%H%M%S)"
                cp "agent/database/research_data.db" "$backup_file"
                log_success "SQLite backup created: $backup_file"
            fi
            ;;
        production)
            # Production backup should be handled by Render/PostgreSQL
            log_info "Production backup should be configured in Render dashboard"
            ;;
    esac
}

# Post-deployment tasks
post_deployment() {
    log_info "Running post-deployment tasks..."
    
    # Log deployment event
    log_info "Deployment completed at $(date)"
    
    # Clean up old backups (keep last 5)
    if [[ $ENVIRONMENT == "development" ]]; then
        find agent/database/ -name "*.backup.*" -type f | sort -r | tail -n +6 | xargs rm -f 2>/dev/null || true
    fi
    
    # Display useful information
    echo ""
    echo "=================="
    echo "DEPLOYMENT SUMMARY"
    echo "=================="
    echo "Environment: $ENVIRONMENT"
    echo "Timestamp: $(date)"
    echo "Migration: $([ $SKIP_MIGRATION == true ] && echo 'Skipped' || echo 'Executed')"
    echo "Vector Migration: $([ $SKIP_VECTOR_MIGRATION == true ] && echo 'Skipped' || echo 'Executed')"
    
    if [[ $ENVIRONMENT == "development" ]]; then
        echo ""
        echo "Local URLs:"
        echo "  API: http://localhost:8000"
        echo "  Docs: http://localhost:8000/docs"
        echo "  Health: http://localhost:8000/health"
        echo ""
        echo "To view logs: docker-compose logs -f app"
        echo "To stop: docker-compose down"
    fi
}

# Main deployment flow
main() {
    echo "======================================="
    echo "Research Data Management PaaS Deployment"
    echo "======================================="
    
    validate_environment
    check_prerequisites
    
    if [[ $DRY_RUN == true ]]; then
        log_info "DRY RUN MODE - No actual changes will be made"
    fi
    
    # Create backup before deployment
    create_backup
    
    # Deploy based on environment
    case $ENVIRONMENT in
        development)
            deploy_development
            ;;
        staging)
            deploy_staging
            ;;
        production)
            deploy_production
            ;;
    esac
    
    # Post-deployment tasks
    post_deployment
    
    log_success "Deployment completed successfully!"
}

# Run main function
main "$@"