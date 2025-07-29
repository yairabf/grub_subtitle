# Enhanced Database Design for Multi-Directory Subtitle Service

## Overview

This document outlines the enhanced database schema designed to support multiple directories, subdirectories, and better organization for the subtitle processing service.

## Current Schema vs Enhanced Schema

### Current Schema (Basic)
- `processed_files` - Tracks individual files
- `subtitle_operations` - Tracks subtitle operations
- `scan_sessions` - Tracks scan sessions

### Enhanced Schema (Advanced)
- `monitored_directories` - Tracks monitored directories
- `directory_groups` - Groups directories for organization
- `directory_group_members` - Many-to-many relationship
- `processed_files_enhanced` - Enhanced file tracking
- `subtitle_operations_enhanced` - Enhanced operation tracking
- `scan_sessions_enhanced` - Enhanced session tracking

## Enhanced Schema Details

### 1. Monitored Directories Table

```sql
CREATE TABLE monitored_directories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    directory_path TEXT UNIQUE NOT NULL,
    display_name TEXT,
    is_active BOOLEAN DEFAULT 1,
    scan_recursive BOOLEAN DEFAULT 1,
    scan_interval_minutes INTEGER DEFAULT 30,
    last_scan_time REAL,
    files_count INTEGER DEFAULT 0,
    created_at REAL DEFAULT (unixepoch()),
    updated_at REAL DEFAULT (unixepoch())
);
```

**Purpose**: Track all monitored directories with their configuration.

**Key Features**:
- `directory_path`: Full path to the monitored directory
- `display_name`: Human-readable name for the directory
- `is_active`: Whether the directory is currently being monitored
- `scan_recursive`: Whether to scan subdirectories
- `scan_interval_minutes`: How often to scan this directory
- `last_scan_time`: When this directory was last scanned
- `files_count`: Number of files currently tracked in this directory

### 2. Directory Groups Table

```sql
CREATE TABLE directory_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name TEXT UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at REAL DEFAULT (unixepoch())
);
```

**Purpose**: Organize directories into logical groups.

**Examples**:
- "Kids Shows" - for children's content
- "Movies" - for movie collections
- "TV Shows" - for television series
- "Documentaries" - for documentary content

### 3. Directory Group Members Table

```sql
CREATE TABLE directory_group_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    directory_id INTEGER NOT NULL,
    created_at REAL DEFAULT (unixepoch()),
    FOREIGN KEY (group_id) REFERENCES directory_groups (id),
    FOREIGN KEY (directory_id) REFERENCES monitored_directories (id),
    UNIQUE(group_id, directory_id)
);
```

**Purpose**: Many-to-many relationship between directories and groups.

### 4. Enhanced Processed Files Table

```sql
CREATE TABLE processed_files_enhanced (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    directory_id INTEGER NOT NULL,
    relative_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    file_modified_time REAL NOT NULL,
    processing_status TEXT NOT NULL,
    processing_start_time REAL,
    processing_end_time REAL,
    processing_duration REAL,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    last_retry_time REAL,
    created_at REAL DEFAULT (unixepoch()),
    updated_at REAL DEFAULT (unixepoch()),
    FOREIGN KEY (directory_id) REFERENCES monitored_directories (id)
);
```

**Key Enhancements**:
- `directory_id`: Links file to its monitored directory
- `relative_path`: Path relative to monitored directory (e.g., "Season.9/S09E01.mkv")
- `file_name`: Just the filename (e.g., "S09E01.mkv")
- `retry_count`: Number of times processing has been retried
- `max_retries`: Maximum number of retries allowed
- `last_retry_time`: When the file was last retried

### 5. Enhanced Subtitle Operations Table

```sql
CREATE TABLE subtitle_operations_enhanced (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    operation_type TEXT NOT NULL,
    operation_status TEXT NOT NULL,
    subtitle_language TEXT,
    subtitle_path TEXT,
    subtitle_source TEXT,
    subtitle_quality_score REAL,
    operation_start_time REAL,
    operation_end_time REAL,
    operation_duration REAL,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at REAL DEFAULT (unixepoch()),
    FOREIGN KEY (file_id) REFERENCES processed_files_enhanced (id)
);
```

**Key Enhancements**:
- `subtitle_quality_score`: Quality score (0-100) for the subtitle
- `retry_count`: Number of times this operation has been retried

### 6. Enhanced Scan Sessions Table

```sql
CREATE TABLE scan_sessions_enhanced (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_start_time REAL NOT NULL,
    session_end_time REAL,
    directory_id INTEGER NOT NULL,
    scan_type TEXT NOT NULL,
    files_found INTEGER DEFAULT 0,
    files_new INTEGER DEFAULT 0,
    files_modified INTEGER DEFAULT 0,
    files_processed INTEGER DEFAULT 0,
    files_skipped INTEGER DEFAULT 0,
    files_failed INTEGER DEFAULT 0,
    scan_duration REAL,
    error_count INTEGER DEFAULT 0,
    created_at REAL DEFAULT (unixepoch()),
    FOREIGN KEY (directory_id) REFERENCES monitored_directories (id)
);
```

**Key Enhancements**:
- `directory_id`: Links session to specific directory
- `scan_type`: Type of scan ('full', 'incremental', 'manual')
- `files_new`: Number of new files discovered
- `files_modified`: Number of files that changed
- `error_count`: Number of errors during scan

## Benefits of Enhanced Schema

### 1. Better Organization
- **Directory Groups**: Organize content by type (movies, TV shows, etc.)
- **Relative Paths**: Easier to understand file locations
- **Display Names**: Human-readable directory names

### 2. Improved Performance
- **Directory-specific queries**: Query files by directory
- **Efficient indexing**: Indexes on frequently queried columns
- **Reduced data duplication**: Normalized structure

### 3. Enhanced Monitoring
- **Per-directory statistics**: Track performance by directory
- **Retry tracking**: Better retry logic with counters
- **Quality scoring**: Track subtitle quality

### 4. Scalability
- **Multiple directories**: Support for many monitored locations
- **Flexible grouping**: Organize directories as needed
- **Incremental scans**: Only scan changed directories

## Migration Strategy

### Phase 1: Backward Compatibility
- Keep current schema working
- Add enhanced tables alongside current ones
- Implement data migration utilities

### Phase 2: Gradual Migration
- Migrate one directory at a time
- Test enhanced functionality
- Compare performance and reliability

### Phase 3: Full Migration
- Switch to enhanced schema completely
- Remove old tables
- Update all code to use new schema

## Example Usage Scenarios

### Scenario 1: Multiple TV Show Directories
```sql
-- Add directories
INSERT INTO monitored_directories (directory_path, display_name, scan_recursive) 
VALUES 
    ('/media/tvshows/action', 'Action Shows', 1),
    ('/media/tvshows/comedy', 'Comedy Shows', 1),
    ('/media/tvshows/kids', 'Kids Shows', 1);

-- Create group
INSERT INTO directory_groups (group_name, description) 
VALUES ('TV Shows', 'All television series');

-- Add directories to group
INSERT INTO directory_group_members (group_id, directory_id) 
SELECT g.id, d.id 
FROM directory_groups g, monitored_directories d 
WHERE g.group_name = 'TV Shows' AND d.display_name IN ('Action Shows', 'Comedy Shows', 'Kids Shows');
```

### Scenario 2: Query Files by Directory
```sql
-- Get all pending files from a specific directory
SELECT pf.*, md.display_name 
FROM processed_files_enhanced pf
JOIN monitored_directories md ON pf.directory_id = md.id
WHERE md.directory_path = '/media/tvshows/kids'
AND pf.processing_status = 'pending';
```

### Scenario 3: Directory Statistics
```sql
-- Get processing statistics by directory
SELECT 
    md.display_name,
    COUNT(*) as total_files,
    SUM(CASE WHEN pf.processing_status = 'success' THEN 1 ELSE 0 END) as successful,
    SUM(CASE WHEN pf.processing_status = 'failed' THEN 1 ELSE 0 END) as failed,
    SUM(CASE WHEN pf.processing_status = 'pending' THEN 1 ELSE 0 END) as pending
FROM monitored_directories md
LEFT JOIN processed_files_enhanced pf ON md.id = pf.directory_id
GROUP BY md.id, md.display_name;
```

## Implementation Notes

### 1. Data Migration
- Create migration scripts to move data from old to new schema
- Preserve all existing data and relationships
- Test migration thoroughly before deployment

### 2. Performance Considerations
- Use appropriate indexes for common queries
- Consider partitioning for very large datasets
- Monitor query performance and optimize as needed

### 3. Configuration Management
- Store directory configurations in the database
- Allow runtime configuration changes
- Provide backup and restore functionality

### 4. Monitoring and Alerting
- Track directory health and performance
- Alert on directory failures or issues
- Provide detailed reporting capabilities 