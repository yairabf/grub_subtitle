# Project Structure

## Overview

This document describes the organization and structure of the Grab Subtitle project.

## Directory Structure

```
grab_subtitle/
├── config/                     # Configuration files
│   ├── config.yaml            # Main configuration file
│   └── ...
├── data/                      # Data storage
│   └── service_database.db    # SQLite database for file tracking
├── docs/                      # Documentation
│   ├── project_structure.md   # This file
│   ├── database_design.md     # Database schema documentation
│   └── ...
├── logs/                      # Application logs
├── scripts/                   # Utility scripts
│   ├── translate_subtitles.py # Standalone translation script
│   └── ...
├── src/                       # Source code
│   ├── api/                   # API integrations
│   │   └── opensubtitles.py   # OpenSubtitles API client
│   ├── background_service/    # Background service modules (refactored)
│   │   ├── core/             # Core service components
│   │   ├── processing/       # File processing logic
│   │   ├── monitoring/       # Directory and health monitoring
│   │   └── communication/    # Inter-service communication
│   ├── config/               # Configuration management
│   │   └── config_manager.py # Configuration loading and validation
│   ├── exceptions/           # Custom exceptions
│   ├── gui/                  # GUI components (future)
│   ├── logging_system/       # Logging configuration
│   ├── security/             # Security and encryption
│   ├── services/             # Core services
│   │   ├── background_service.py      # Main background service
│   │   ├── directory_scanner.py       # Directory scanning
│   │   ├── file_tracker.py           # File tracking and database
│   │   ├── notification_service.py   # Notifications
│   │   ├── subtitle_service.py       # Subtitle processing
│   │   ├── translation.py            # Translation service
│   │   ├── validation.py             # Subtitle validation
│   │   └── ...
│   ├── utils/                # Utility functions
│   └── main.py               # Main application entry point
├── tests/                    # Test files
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests
│   └── scripts/              # Test scripts
├── tasks/                    # Project tasks and requirements
│   ├── prd-background-service.md
│   └── tasks-prd-background-service.md
├── venv/                     # Virtual environment (gitignored)
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore rules
├── README.md                 # Project README
├── requirements.txt          # Python dependencies
└── run_background_service.py # Background service runner
```

## Key Components

### 1. Background Service (`src/services/background_service.py`)
The main background service that orchestrates the entire subtitle processing workflow.

**Responsibilities:**
- Directory monitoring
- File processing coordination
- Worker thread management
- Service lifecycle management
- Status reporting

### 2. Directory Scanner (`src/services/directory_scanner.py`)
Handles scanning of monitored directories for new video files.

**Responsibilities:**
- Recursive directory scanning
- Video file detection
- Change detection
- Progress reporting

### 3. File Tracker (`src/services/file_tracker.py`)
Manages the SQLite database for tracking processed files.

**Responsibilities:**
- File status tracking
- Processing history
- Database operations
- Statistics collection

### 4. Subtitle Service (`src/services/subtitle_service.py`)
Core logic for subtitle processing and management.

**Responsibilities:**
- Subtitle search and download
- Translation coordination
- Validation
- File management

### 5. Translation Service (`src/services/translation.py`)
Handles subtitle translation using OpenAI API.

**Responsibilities:**
- OpenAI API integration
- Subtitle chunking
- Translation processing
- Quality control

### 6. OpenSubtitles API (`src/api/opensubtitles.py`)
Client for OpenSubtitles API integration.

**Responsibilities:**
- API authentication
- Subtitle search
- File downloads
- Error handling and retries

### 7. Configuration Manager (`src/config/config_manager.py`)
Manages application configuration.

**Responsibilities:**
- Configuration loading
- Environment variable substitution
- Validation
- Default values

## Configuration Files

### `config/config.yaml`
Main configuration file containing all service settings.

**Key Sections:**
- `api`: OpenSubtitles API credentials
- `translation`: Translation settings
- `service`: Service configuration
- `processing`: Processing parameters
- `validation`: Validation settings
- `logging`: Logging configuration
- `security`: Security settings
- `ui`: User interface settings
- `paths`: File paths

### `.env`
Environment variables file (not tracked in git).

**Required Variables:**
- `OPENSUBTITLES_USERNAME`: OpenSubtitles username
- `OPENSUBTITLES_PASSWORD`: OpenSubtitles password
- `OPENAI_API_KEY`: OpenAI API key
- `DIRECTORY_PATH`: Path to monitored directory

## Database Schema

The application uses SQLite for file tracking and processing history.

**Main Tables:**
- `processed_files`: Tracks individual video files
- `subtitle_operations`: Tracks subtitle operations
- `scan_sessions`: Tracks directory scan sessions

See `docs/database_design.md` for detailed schema information.

## Testing Structure

### `tests/unit/`
Unit tests for individual components.

### `tests/integration/`
Integration tests for component interactions.

### `tests/scripts/`
Test scripts and examples.

## Scripts

### `scripts/translate_subtitles.py`
Standalone script for translating subtitle files.

### `run_background_service.py`
Main script for running the background service.

## Logging

Logs are stored in the `logs/` directory with structured JSON format.

**Log Levels:**
- DEBUG: Detailed debugging information
- INFO: General information
- WARNING: Warning messages
- ERROR: Error messages
- CRITICAL: Critical errors

## Security

Security-related files are stored in `src/security/` and `secure/` directories.

**Features:**
- API key management
- Encryption utilities
- Network security
- Access control

## Development Workflow

1. **Configuration**: Set up `.env` file with required credentials
2. **Installation**: Install dependencies with `pip install -r requirements.txt`
3. **Testing**: Run tests with `python -m pytest tests/`
4. **Development**: Use `run_background_service.py` for development
5. **Production**: Deploy using the main service components

## Future Enhancements

### Enhanced Database Schema
- Multi-directory support
- Directory grouping
- Enhanced tracking
- Quality scoring

### GUI Interface
- Web-based dashboard
- Real-time monitoring
- Configuration management
- Statistics visualization

### Advanced Features
- Machine learning for subtitle quality
- Automated subtitle correction
- Multi-language support
- Cloud storage integration 