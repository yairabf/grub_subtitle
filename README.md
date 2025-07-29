# Grab Subtitle - Multi-Language Subtitle Service

This service automatically downloads and translates subtitles for video files. It first attempts to find subtitles in your target language, and if none are available, it downloads English subtitles and translates them to your desired language using OpenAI's translation capabilities.

## Features

- **Background Service**: Continuous monitoring and processing of video directories
- **Automatic Processing**: Processes all video files in monitored directories
- **Smart Subtitle Search**: Searches for target language subtitles first, falls back to English with translation
- **Multi-Language Support**: Supports Hebrew, Spanish, French, German, Italian, Portuguese, Russian, Japanese, Korean, Chinese, and Arabic
- **Language-Specific Validation**: Comprehensive quality assurance and validation for each supported language
- **Multiple Video Formats**: Supports mp4, mkv, avi, mov, wmv, flv, webm
- **Format Preservation**: Maintains original subtitle timing and format
- **OpenSubtitles Integration**: Uses XML-RPC API for better quota access
- **Hash-based Matching**: Accurate subtitle matching using file hashes
- **Retry Logic**: Robust error handling with automatic retries
- **Multi-directory Support**: Monitor multiple directories simultaneously

## Project Structure

```
grab_subtitle/
├── config/                     # Configuration files
├── data/                      # Database storage
├── docs/                      # Documentation
├── logs/                      # Application logs
├── scripts/                   # Utility scripts
├── src/                       # Source code
│   ├── api/                   # API integrations
│   ├── background_service/    # Background service modules
│   ├── config/               # Configuration management
│   ├── services/             # Core services
│   └── ...
├── tests/                    # Test files
└── tasks/                    # Project tasks
```

See `docs/project_structure.md` for detailed structure information.

## Installation

### Option 1: Docker Deployment (Recommended for HomeLab)

The easiest way to deploy in a HomeLab environment is using Docker.

#### Prerequisites
- Docker and Docker Compose
- OpenSubtitles account
- OpenAI API key

#### Quick Start with Docker

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd grab_subtitle
   ```

2. **Setup Docker environment**
   ```bash
   # Copy environment template
   cp docker.env.example docker.env
   
   # Edit docker.env with your API credentials
   nano docker.env
   ```

3. **Deploy with Docker**
   ```bash
   # Run the deployment script
   ./docker/deploy.sh setup
   ./docker/deploy.sh deploy
   
   # Or with monitoring interface
   ./docker/deploy.sh monitor
   ```

4. **Access monitoring interface**
   - Open http://localhost:8080 in your browser

#### HomeLab Platform Support

The service includes configurations for popular HomeLab platforms:

- **Synology NAS**: `docker/homelab-examples/synology/`
- **TrueNAS**: `docker/homelab-examples/truenas/`
- **Unraid**: `docker/homelab-examples/unraid/`
- **Proxmox VE**: `docker/homelab-examples/proxmox/`
- **Linux**: `docker/homelab-examples/linux/`

See `docker/homelab-examples/README.md` for platform-specific instructions.

### Option 2: Local Python Installation

#### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- OpenSubtitles account
- OpenAI API key

#### Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Create Environment File**:
   Create a `.env` file in the project root:
   ```bash
   OPENSUBTITLES_USERNAME=your_opensubtitles_username
   OPENSUBTITLES_PASSWORD=your_opensubtitles_password
   OPENAI_API_KEY=your_openai_api_key
   DIRECTORY_PATH=/path/to/your/video/directory
   ```

3. **Configure Service**:
   Edit `config/config.yaml` to customize service settings.

## Usage

### Background Service (Recommended)

Run the background service to continuously monitor and process video files:

```bash
python run_background_service.py
```

The service will:
- Monitor the specified directory for new video files
- Automatically download and translate subtitles
- Handle errors and retries
- Provide real-time status updates

### Standalone Processing

Process a single video file:
```bash
python scripts/translate_subtitles.py path/to/your/video.mp4
```

Process a directory:
```bash
python -m src.main
```

### Validation

Validate an existing Hebrew subtitle file:
```bash
python -m src.main --validate-only path/to/subtitle.heb.srt
```

Validate and attempt to fix issues:
```bash
python -m src.main --validate-only path/to/subtitle.heb.srt --fix
```

## Configuration

### Main Configuration (`config/config.yaml`)

The service is configured through `config/config.yaml` with sections for:

- **API Settings**: OpenSubtitles credentials
- **Translation**: OpenAI and translation parameters
- **Service**: Background service configuration
- **Processing**: File processing settings
- **Validation**: Subtitle validation rules
- **Logging**: Logging configuration

### Environment Variables (`.env`)

Required environment variables:
- `OPENSUBTITLES_USERNAME`: OpenSubtitles account username
- `OPENSUBTITLES_PASSWORD`: OpenSubtitles account password
- `OPENAI_API_KEY`: OpenAI API key
- `DIRECTORY_PATH`: Path to monitored video directory

Optional environment variables:
- `TARGET_LANGUAGE`: Target language for subtitles (defaults to "he" for Hebrew)

## Multi-Language Subtitle Validation

The service includes comprehensive subtitle validation for all supported languages:

### Validation Features
- **Language-Specific Text Detection**: Identifies target language characters and validates content ratio
- **SRT Format Validation**: Ensures proper subtitle timing and format
- **Encoding Validation**: Checks UTF-8 encoding and BOM issues
- **Content Quality Checks**: Detects translation issues and quality problems
- **Automatic Fixes**: Attempts to fix common formatting and timing issues

### Translation Improvements
- **SRT Block-Aware Chunking**: Preserves complete subtitle blocks
- **Translation Completeness**: Verifies all blocks are translated
- **Enhanced Error Handling**: Better error reporting and recovery
- **Quality Scoring**: Tracks subtitle quality metrics
- **Multi-Language Support**: Supports translation to 11 different languages

## Background Service Features

### Directory Monitoring
- **Recursive Scanning**: Monitors subdirectories
- **Change Detection**: Detects new and modified files
- **Configurable Intervals**: Adjustable scan frequency

### File Processing
- **Worker Threads**: Parallel processing of multiple files
- **Priority Queue**: Prioritizes new files over retries
- **Status Tracking**: Comprehensive file status tracking
- **Error Recovery**: Automatic retry with exponential backoff

### Database Tracking
- **File History**: Tracks all processed files
- **Processing Statistics**: Detailed performance metrics
- **Error Logging**: Comprehensive error tracking
- **Status Persistence**: Maintains state across restarts

## API Integration

### OpenSubtitles API
- **XML-RPC Client**: Uses VIP API for better quota access
- **Hash-based Search**: Accurate subtitle matching
- **Retry Logic**: Handles API rate limiting and errors
- **Authentication**: Secure credential management

### OpenAI API
- **Translation Service**: High-quality Hebrew translation
- **Chunking Strategy**: Efficient processing of large files
- **Quality Control**: Ensures translation completeness
- **Error Handling**: Robust API error management

## Development

### Testing
```bash
# Run all tests
python -m pytest tests/

# Run specific test categories
python -m pytest tests/unit/
python -m pytest tests/integration/
```

### Code Structure
- **Modular Design**: Clean separation of concerns
- **Service Architecture**: Well-defined service boundaries
- **Configuration Management**: Centralized configuration
- **Error Handling**: Comprehensive error management

### Database Schema
The service uses SQLite for file tracking with tables for:
- `processed_files`: File processing history
- `subtitle_operations`: Subtitle operation tracking
- `scan_sessions`: Directory scan sessions

See `docs/database_design.md` for detailed schema information.

## Troubleshooting

### Common Issues

1. **API Rate Limiting**: The service includes retry logic for API limits
2. **File Permissions**: Ensure the service has read/write access to directories
3. **Network Issues**: Check internet connectivity for API calls
4. **Database Errors**: Verify database file permissions and integrity

### Logs
Check the `logs/` directory for detailed application logs with structured JSON format.

### Status Monitoring
The background service provides real-time status updates and health monitoring.

## Future Enhancements

- **Enhanced Database Schema**: Multi-directory support with directory grouping
- **GUI Interface**: Web-based dashboard for monitoring and configuration
- **Machine Learning**: Automated subtitle quality improvement
- **Cloud Integration**: Support for cloud storage providers
- **Multi-language Support**: Support for additional languages beyond Hebrew

## Contributing

1. Follow the existing code structure and patterns
2. Add tests for new features
3. Update documentation as needed
4. Use the established configuration and logging patterns

## License

This project is licensed under the MIT License - see the LICENSE file for details. 