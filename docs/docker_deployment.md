# Docker Deployment Guide

## Overview

This guide covers deploying the Grab Subtitle service using Docker in various HomeLab environments. Docker provides a consistent, isolated environment that works across different platforms.

## Quick Start

### 1. Prerequisites

- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher
- **API Credentials**: OpenSubtitles and OpenAI accounts

### 2. Basic Deployment

```bash
# Clone the repository
git clone <repository-url>
cd grab_subtitle

# Setup environment
cp docker.env.example docker.env
# Edit docker.env with your API credentials

# Deploy
./docker/deploy.sh setup
./docker/deploy.sh deploy
```

### 3. Access Monitoring

- **Web Interface**: http://localhost:8080
- **Logs**: `docker-compose logs -f grab-subtitle`
- **Status**: `docker-compose ps`

## Docker Architecture

### Container Structure

```
grab-subtitle/
├── grab-subtitle/          # Main application container
│   ├── Python 3.11
│   ├── Application code
│   ├── Dependencies
│   └── Non-root user
└── subtitle-monitor/       # Optional monitoring container
    ├── Nginx
    ├── Web interface
    └── Log viewer
```

### Volume Mounts

| Host Path | Container Path | Purpose | Access |
|-----------|----------------|---------|---------|
| `./videos` | `/media/videos` | Video files to monitor | Read-only |
| `./subtitles` | `/app/subtitles` | Generated subtitles | Read/Write |
| `./config` | `/app/config` | Configuration files | Read-only |
| `./data` | `/app/data` | Database and persistent data | Read/Write |
| `./logs` | `/app/logs` | Application logs | Read/Write |
| `./cache` | `/app/cache` | Temporary cache files | Read/Write |

### Network Configuration

- **Internal Network**: `subtitle-network` (172.20.0.0/16)
- **Container Communication**: Isolated Docker network
- **External Access**: Port 8080 for monitoring interface

## HomeLab Platform Configurations

### Synology NAS

#### Features
- Volume-based path mapping
- Docker GUI integration
- Resource optimization for NAS hardware

#### Configuration
```bash
cd docker/homelab-examples/synology
cp docker.env.example docker.env
# Edit docker.env with your paths and credentials
docker-compose up -d
```

#### Path Mapping
```yaml
volumes:
  - /volume1/video:/media/videos:ro
  - /volume1/subtitles:/app/subtitles
  - /volume1/docker/grab-subtitle/data:/app/data
```

### TrueNAS Core/Scale

#### Features
- ZFS pool integration
- Jail/container isolation
- High-performance storage

#### Configuration
```bash
cd docker/homelab-examples/truenas
cp docker.env.example docker.env
# Edit docker.env with your ZFS pool paths
docker-compose up -d
```

#### Path Mapping
```yaml
volumes:
  - /mnt/tank/videos:/media/videos:ro
  - /mnt/tank/subtitles:/app/subtitles
  - /mnt/tank/docker/grab-subtitle/data:/app/data
```

### Unraid

#### Features
- Array integration
- Docker container management
- Parity protection

#### Configuration
```bash
cd docker/homelab-examples/unraid
cp docker.env.example docker.env
# Edit docker.env with your array paths
docker-compose up -d
```

#### Path Mapping
```yaml
volumes:
  - /mnt/user/videos:/media/videos:ro
  - /mnt/user/subtitles:/app/subtitles
  - /mnt/user/appdata/grab-subtitle/data:/app/data
```

### Proxmox VE

#### Features
- LXC container support
- Resource management
- Network isolation

#### Configuration
```bash
cd docker/homelab-examples/proxmox
cp docker.env.example docker.env
# Edit docker.env with your mount paths
docker-compose up -d
```

#### Path Mapping
```yaml
volumes:
  - /mnt/videos:/media/videos:ro
  - /mnt/subtitles:/app/subtitles
  - /var/lib/grab-subtitle/data:/app/data
```

## Configuration Options

### Environment Variables

#### Required Variables
```bash
# API Credentials
OPENSUBTITLES_USERNAME=your_username
OPENSUBTITLES_PASSWORD=your_password
OPENAI_API_KEY=your_openai_key
```

#### Optional Variables
```bash
# Service Configuration
TARGET_LANGUAGE=he          # Target language (he, es, fr, de, etc.)
DIRECTORY_PATH=/media/videos # Internal container path

# Directory Paths (Host)
VIDEO_DIRECTORY=./videos
SUBTITLE_OUTPUT=./subtitles
CONFIG_DIR=./config
DATA_DIR=./data
LOGS_DIR=./logs
CACHE_DIR=./cache
```

### Resource Limits

#### Default Limits
```yaml
deploy:
  resources:
    limits:
      memory: 2G
      cpus: '1.0'
    reservations:
      memory: 512M
      cpus: '0.5'
```

#### HomeLab Optimizations
```yaml
# For Synology NAS (lower resources)
limits:
  memory: 1G
  cpus: '0.5'

# For high-performance systems
limits:
  memory: 4G
  cpus: '2.0'
```

## Monitoring and Management

### Web Interface

The optional monitoring interface provides:
- **Service Status**: Container health and status
- **Directory Information**: Mounted volumes and paths
- **Language Settings**: Current target language configuration
- **Resource Usage**: CPU, memory, and disk usage
- **Log Access**: Direct access to application logs
- **Data Browser**: Browse processed files and database

### Command Line Management

#### Service Control
```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart services
docker-compose restart

# View logs
docker-compose logs -f grab-subtitle

# Check status
docker-compose ps
```

#### Deployment Script
```bash
# Setup environment
./docker/deploy.sh setup

# Deploy services
./docker/deploy.sh deploy

# Start with monitoring
./docker/deploy.sh monitor

# Check status
./docker/deploy.sh status

# View logs
./docker/deploy.sh logs

# Cleanup
./docker/deploy.sh cleanup
```

### Health Checks

#### Container Health
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import os; exit(0 if os.path.exists('/app/data/service_database.db') else 1)"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

#### Application Health
- **Database Connectivity**: SQLite database access
- **File System**: Mounted volume access
- **API Connectivity**: OpenSubtitles and OpenAI API access

## Security Considerations

### Container Security
- **Non-root User**: Container runs as `subtitle_user` (UID 1000)
- **Read-only Mounts**: Video directories mounted read-only
- **Network Isolation**: Internal Docker network
- **Resource Limits**: Prevents resource exhaustion

### API Security
- **Environment Variables**: API keys stored in environment files
- **No Hardcoding**: Credentials never stored in images
- **Access Control**: Limited external access to monitoring interface

### File Permissions
```bash
# Set proper permissions for mounted volumes
chown -R 1000:1000 /path/to/mounted/directories
chmod -R 755 /path/to/mounted/directories
```

## Troubleshooting

### Common Issues

#### 1. Permission Denied
```bash
# Fix permissions for mounted volumes
sudo chown -R 1000:1000 /path/to/videos
sudo chown -R 1000:1000 /path/to/subtitles
sudo chown -R 1000:1000 /path/to/data
```

#### 2. Container Won't Start
```bash
# Check logs
docker-compose logs grab-subtitle

# Check configuration
docker-compose config

# Validate environment
./docker/deploy.sh setup
```

#### 3. API Connection Issues
```bash
# Verify credentials
docker-compose exec grab-subtitle env | grep -E "(OPENSUBTITLES|OPENAI)"

# Test API connectivity
docker-compose exec grab-subtitle python -c "
import os
print('OpenSubtitles:', bool(os.getenv('OPENSUBTITLES_USERNAME')))
print('OpenAI:', bool(os.getenv('OPENAI_API_KEY')))
"
```

#### 4. Disk Space Issues
```bash
# Check disk usage
docker system df
docker volume ls

# Clean up
docker system prune -f
docker volume prune -f
```

### Platform-Specific Issues

#### Synology NAS
- **Docker Package**: Ensure Docker package is installed from Package Center
- **Volume Permissions**: Set proper permissions in File Station
- **Resource Limits**: Adjust limits for NAS hardware

#### TrueNAS
- **Jail Permissions**: Configure jail permissions for mounted directories
- **ZFS Snapshots**: Use ZFS snapshots for data protection
- **Network Configuration**: Configure jail networking

#### Unraid
- **Array Paths**: Use `/mnt/user/` for array access
- **Docker GUI**: Use Unraid's Docker GUI for management
- **Parity Protection**: Ensure array parity for data protection

#### Proxmox
- **LXC Permissions**: Configure LXC container permissions
- **Resource Limits**: Set appropriate resource limits
- **Network Configuration**: Configure container networking

## Performance Optimization

### Resource Tuning

#### Memory Optimization
```yaml
# For low-memory systems (Synology, etc.)
limits:
  memory: 1G
reservations:
  memory: 256M

# For high-memory systems
limits:
  memory: 4G
reservations:
  memory: 1G
```

#### CPU Optimization
```yaml
# For low-CPU systems
limits:
  cpus: '0.5'
reservations:
  cpus: '0.25'

# For high-CPU systems
limits:
  cpus: '2.0'
reservations:
  cpus: '1.0'
```

### Storage Optimization
- **SSD Storage**: Use SSD for database and cache directories
- **Network Storage**: Use network storage for video files
- **Log Rotation**: Configure log rotation to prevent disk space issues

### Network Optimization
- **Local Network**: Ensure adequate bandwidth for API calls
- **DNS Resolution**: Use reliable DNS servers
- **Proxy Configuration**: Configure proxy if needed

## Backup and Recovery

### Data Backup
```bash
# Backup configuration
cp docker.env docker.env.backup
cp docker-compose.yml docker-compose.yml.backup

# Backup database
cp data/service_database.db data/service_database.db.backup

# Backup subtitles
tar -czf subtitles_backup.tar.gz subtitles/
```

### Recovery
```bash
# Restore configuration
cp docker.env.backup docker.env
cp docker-compose.yml.backup docker-compose.yml

# Restore database
cp data/service_database.db.backup data/service_database.db

# Restore subtitles
tar -xzf subtitles_backup.tar.gz

# Restart services
docker-compose restart
```

## Updates and Maintenance

### Updating the Service
```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Regular Maintenance
```bash
# Clean up old images
docker image prune -f

# Clean up old containers
docker container prune -f

# Clean up old volumes
docker volume prune -f

# Update base images
docker-compose pull
```

### Monitoring and Alerts
- **Resource Monitoring**: Monitor CPU, memory, and disk usage
- **Log Monitoring**: Monitor application logs for errors
- **Health Checks**: Use health checks for automated monitoring
- **Backup Monitoring**: Monitor backup success and disk space

## Advanced Configuration

### Custom Dockerfile
```dockerfile
# Custom Dockerfile for specific requirements
FROM python:3.11-slim

# Add custom dependencies
RUN apt-get update && apt-get install -y \
    custom-package \
    && rm -rf /var/lib/apt/lists/*

# Copy application
COPY . /app
WORKDIR /app

# Install dependencies
RUN pip install -r requirements.txt

# Custom configuration
ENV CUSTOM_VAR=value

CMD ["python", "run_background_service.py"]
```

### Multi-Environment Setup
```bash
# Development
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Testing
docker-compose -f docker-compose.yml -f docker-compose.test.yml up -d
```

### Reverse Proxy Integration
```nginx
# Nginx reverse proxy configuration
server {
    listen 80;
    server_name subtitle.yourdomain.com;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

This comprehensive Docker deployment guide covers all aspects of deploying the Grab Subtitle service in HomeLab environments, from basic setup to advanced configuration and troubleshooting. 