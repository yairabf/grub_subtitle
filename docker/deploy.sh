#!/bin/bash

# Grab Subtitle Service - Docker Deployment Script
# This script helps you deploy the service in your HomeLab environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Docker installation
check_docker() {
    if ! command_exists docker; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! command_exists docker-compose; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi

    print_success "Docker and Docker Compose are installed"
}

# Function to create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    mkdir -p videos subtitles data logs cache config temp
    
    print_success "Directories created successfully"
}

# Function to setup environment file
setup_environment() {
    if [ ! -f "docker.env" ]; then
        print_status "Creating docker.env file from template..."
        cp docker.env.example docker.env
        print_warning "Please edit docker.env and fill in your API credentials"
        print_warning "Required: OPENSUBTITLES_USERNAME, OPENSUBTITLES_PASSWORD, OPENAI_API_KEY"
    else
        print_success "docker.env file already exists"
    fi
}

# Function to validate environment file
validate_environment() {
    print_status "Validating environment configuration..."
    
    if [ ! -f "docker.env" ]; then
        print_error "docker.env file not found. Please run setup first."
        exit 1
    fi
    
    # Source the environment file to check variables
    source docker.env
    
    # Check required variables
    if [ -z "$OPENSUBTITLES_USERNAME" ] || [ "$OPENSUBTITLES_USERNAME" = "your_opensubtitles_username" ]; then
        print_error "OPENSUBTITLES_USERNAME not set in docker.env"
        exit 1
    fi
    
    if [ -z "$OPENSUBTITLES_PASSWORD" ] || [ "$OPENSUBTITLES_PASSWORD" = "your_opensubtitles_password" ]; then
        print_error "OPENSUBTITLES_PASSWORD not set in docker.env"
        exit 1
    fi
    
    if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "your_openai_api_key" ]; then
        print_error "OPENAI_API_KEY not set in docker.env"
        exit 1
    fi
    
    print_success "Environment configuration is valid"
}

# Function to build and start services
deploy_services() {
    print_status "Building and starting services..."
    
    # Build the image
    docker-compose build
    
    # Start services
    docker-compose up -d
    
    print_success "Services deployed successfully"
}

# Function to show service status
show_status() {
    print_status "Service status:"
    docker-compose ps
    
    print_status "Recent logs:"
    docker-compose logs --tail=20 grab-subtitle
}

# Function to show usage
show_usage() {
    echo "Grab Subtitle Service - Docker Deployment Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  setup     - Initial setup (create directories and env file)"
    echo "  deploy    - Deploy the service"
    echo "  start     - Start the service"
    echo "  stop      - Stop the service"
    echo "  restart   - Restart the service"
    echo "  status    - Show service status"
    echo "  logs      - Show service logs"
    echo "  monitor   - Start with monitoring interface"
    echo "  cleanup   - Remove containers and images"
    echo "  help      - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 setup     # First time setup"
    echo "  $0 deploy    # Deploy the service"
    echo "  $0 monitor   # Deploy with web monitoring"
    echo ""
}

# Function to start monitoring
start_monitoring() {
    print_status "Starting services with monitoring interface..."
    
    # Start with monitor profile
    docker-compose --profile monitor up -d
    
    print_success "Services started with monitoring interface"
    print_status "Access monitoring interface at: http://localhost:8080"
}

# Function to cleanup
cleanup() {
    print_warning "This will remove all containers and images. Are you sure? (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        print_status "Cleaning up..."
        docker-compose down --rmi all --volumes --remove-orphans
        print_success "Cleanup completed"
    else
        print_status "Cleanup cancelled"
    fi
}

# Main script logic
case "${1:-help}" in
    setup)
        check_docker
        create_directories
        setup_environment
        print_success "Setup completed. Please edit docker.env with your credentials."
        ;;
    deploy)
        check_docker
        validate_environment
        deploy_services
        show_status
        ;;
    start)
        docker-compose up -d
        print_success "Services started"
        ;;
    stop)
        docker-compose down
        print_success "Services stopped"
        ;;
    restart)
        docker-compose restart
        print_success "Services restarted"
        ;;
    status)
        show_status
        ;;
    logs)
        docker-compose logs -f grab-subtitle
        ;;
    monitor)
        check_docker
        validate_environment
        start_monitoring
        show_status
        ;;
    cleanup)
        cleanup
        ;;
    help|*)
        show_usage
        ;;
esac 