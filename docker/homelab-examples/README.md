# HomeLab Configuration Examples

This directory contains configuration examples for different HomeLab environments.

## Supported HomeLab Platforms

### 1. Synology NAS (DSM)
- **Location**: `synology/`
- **Features**: Volume-based paths, Docker GUI integration
- **Requirements**: DSM 6.2+ with Docker package

### 2. TrueNAS Core/Scale
- **Location**: `truenas/`
- **Features**: ZFS pool integration, jail/container support
- **Requirements**: TrueNAS Core 12+ or TrueNAS Scale

### 3. Unraid
- **Location**: `unraid/`
- **Features**: Array integration, Docker container management
- **Requirements**: Unraid 6.8+ with Docker plugin

### 4. Proxmox VE
- **Location**: `proxmox/`
- **Features**: LXC container support, VM integration
- **Requirements**: Proxmox VE 6.0+

### 5. Docker on Linux
- **Location**: `linux/`
- **Features**: Standard Docker deployment
- **Requirements**: Linux with Docker and Docker Compose

## Quick Start

1. **Choose your platform** and copy the appropriate configuration
2. **Edit the environment file** with your API credentials
3. **Run the deployment script**

```bash
# Example for Synology NAS
cd docker/homelab-examples/synology
cp docker.env.example docker.env
# Edit docker.env with your credentials
./deploy.sh setup
./deploy.sh deploy
```

## Platform-Specific Notes

### Synology NAS
- Uses `/volume1/` paths for data storage
- Integrates with Synology's Docker GUI
- Supports volume mounting for persistent data

### TrueNAS
- Uses ZFS pool paths (`/mnt/tank/`)
- Supports both Core (FreeBSD) and Scale (Linux)
- Jail/container isolation for security

### Unraid
- Uses `/mnt/user/` paths for array access
- Docker container management through GUI
- Array parity protection for data

### Proxmox VE
- LXC container deployment
- VM-based deployment option
- Network isolation and resource management

### Linux
- Standard Docker deployment
- Systemd service integration
- Standard Linux paths and permissions

## Configuration Tips

### 1. Path Mapping
Each platform uses different path conventions:
- **Synology**: `/volume1/video/`
- **TrueNAS**: `/mnt/tank/videos/`
- **Unraid**: `/mnt/user/videos/`
- **Proxmox**: `/mnt/videos/`
- **Linux**: `/home/user/videos/`

### 2. Permissions
Ensure proper file permissions:
```bash
# For Linux/Proxmox
chown -R 1000:1000 /path/to/videos
chmod -R 755 /path/to/videos
```

### 3. Network Configuration
- **Internal networks**: Use Docker networks for container communication
- **External access**: Configure reverse proxy for monitoring interface
- **Security**: Limit external access to monitoring interface

### 4. Resource Limits
Adjust resource limits based on your hardware:
```yaml
deploy:
  resources:
    limits:
      memory: 2G    # Adjust based on available RAM
      cpus: '1.0'   # Adjust based on CPU cores
```

## Monitoring and Logs

### Web Interface
Access the monitoring interface at `http://your-server:8080`

### Log Files
- **Application logs**: `/app/logs/` (inside container)
- **Docker logs**: `docker-compose logs grab-subtitle`
- **System logs**: Check platform-specific log locations

### Health Checks
The service includes health checks:
- **Container health**: Docker health check
- **Service health**: Application-level health check
- **Database health**: SQLite database connectivity

## Troubleshooting

### Common Issues

1. **Permission Denied**
   ```bash
   # Fix permissions
   chown -R 1000:1000 /path/to/mounted/directories
   ```

2. **API Connection Issues**
   - Check API credentials in `docker.env`
   - Verify network connectivity
   - Check API rate limits

3. **Disk Space Issues**
   - Monitor disk usage in mounted volumes
   - Clean up old subtitle files
   - Adjust log rotation settings

4. **Container Won't Start**
   ```bash
   # Check logs
   docker-compose logs grab-subtitle
   
   # Check configuration
   docker-compose config
   ```

### Platform-Specific Issues

#### Synology
- **Docker GUI**: Use Synology's Docker GUI for management
- **Volume permissions**: Ensure proper volume permissions
- **Package Center**: Install Docker package from Package Center

#### TrueNAS
- **Jail permissions**: Configure jail permissions for mounted directories
- **ZFS snapshots**: Use ZFS snapshots for data protection
- **Network isolation**: Configure jail networking

#### Unraid
- **Array paths**: Use `/mnt/user/` for array access
- **Docker GUI**: Use Unraid's Docker GUI
- **Parity protection**: Ensure array parity for data protection

#### Proxmox
- **LXC permissions**: Configure LXC container permissions
- **Resource limits**: Set appropriate resource limits
- **Network configuration**: Configure container networking

## Security Considerations

1. **API Keys**: Store API keys securely in environment files
2. **Network Access**: Limit external access to monitoring interface
3. **File Permissions**: Use appropriate file permissions for mounted volumes
4. **Container Security**: Run containers as non-root user
5. **Updates**: Regularly update Docker images and base system

## Backup and Recovery

### Data Backup
- **Configuration**: Backup `docker.env` and configuration files
- **Database**: Backup SQLite database files
- **Subtitles**: Backup generated subtitle files
- **Logs**: Archive log files for troubleshooting

### Recovery
1. **Restore configuration**: Copy backup configuration files
2. **Restore data**: Restore database and subtitle files
3. **Restart services**: Use deployment script to restart services
4. **Verify functionality**: Check service health and logs

## Performance Optimization

### Resource Tuning
- **Memory**: Adjust memory limits based on video processing needs
- **CPU**: Allocate CPU cores based on processing requirements
- **Storage**: Use SSD storage for better I/O performance
- **Network**: Ensure adequate network bandwidth for API calls

### Monitoring
- **Resource usage**: Monitor CPU, memory, and disk usage
- **Processing speed**: Track subtitle processing performance
- **API usage**: Monitor API rate limits and usage
- **Error rates**: Track and analyze error patterns 