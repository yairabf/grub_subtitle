# Mermaid Architecture Diagram

## System Architecture for Grab Subtitle Service

This diagram shows the complete system architecture and data flow of the Grab Subtitle service.

```mermaid
graph TB
    %% User Interface Layer
    subgraph UI ["🎯 User Interface Layer"]
        A[run_background_service.py<br/>Main Service Runner]
        B[src/main.py<br/>CLI Interface]
        C[scripts/translate_subtitles.py<br/>Standalone Translator]
    end

    %% Core Service Layer
    subgraph Core ["⚙️ Core Service Layer"]
        D[BackgroundService<br/>Main Orchestrator]
        E[SubtitleService<br/>Subtitle Processing]
        F[DirectoryScanner<br/>File Discovery]
        G[FileTracker<br/>Database Manager]
        H[NotificationService<br/>System Notifications]
        I[ServiceCommunicationManager<br/>Inter-Service Communication]
    end

    %% Processing Layer
    subgraph Processing ["🔄 Processing Layer"]
        J[OpenSubtitlesAPI<br/>Subtitle Search & Download]
        K[TranslationService<br/>OpenAI Translation]
        L[SubtitleValidationService<br/>Quality Validation]
    end

    %% Infrastructure Layer
    subgraph Infrastructure ["🏗️ Infrastructure Layer"]
        M[ConfigManager<br/>Configuration Management]
        N[SubtitleLogger<br/>Structured Logging]
        O[(SQLite Database<br/>File Tracking & History)]
        P[config.yaml<br/>Service Configuration]
        Q[.env<br/>Environment Variables]
    end

    %% External Systems
    subgraph External ["🌐 External Systems"]
        R[OpenSubtitles XML-RPC API<br/>Subtitle Database]
        S[OpenAI API<br/>Translation Engine]
    end

    %% File System
    subgraph FileSystem ["💾 File System"]
        T[Monitored Directories<br/>Video File Storage]
        U[Video Files<br/>.mp4, .mkv, .avi, etc.]
        V[Subtitle Files<br/>.heb.srt, .eng.srt]
    end

    %% Data Flow Connections
    %% UI to Core
    A --> D
    B --> E
    C --> E

    %% Core Service Dependencies
    D --> F
    D --> G
    D --> H
    D --> I

    %% Processing Dependencies
    E --> J
    E --> K
    E --> L

    %% Infrastructure Dependencies
    D --> M
    D --> N
    E --> M
    E --> N
    F --> M
    F --> N
    G --> M
    G --> N

    %% Database Connections
    G --> O

    %% Configuration
    M --> P
    M --> Q

    %% External API Connections
    J --> R
    K --> S

    %% File System Connections
    F --> T
    F --> U
    E --> V
    K --> V

    %% Styling
    classDef uiLayer fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1
    classDef coreLayer fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c
    classDef processingLayer fill:#e8f5e8,stroke:#388e3c,stroke-width:2px,color:#1b5e20
    classDef infrastructureLayer fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100
    classDef externalLayer fill:#ffebee,stroke:#d32f2f,stroke-width:2px,color:#b71c1c
    classDef fileSystemLayer fill:#f1f8e9,stroke:#689f38,stroke-width:2px,color:#33691e

    class A,B,C uiLayer
    class D,E,F,G,H,I coreLayer
    class J,K,L processingLayer
    class M,N,O,P,Q infrastructureLayer
    class R,S externalLayer
    class T,U,V fileSystemLayer
```

## Data Flow Sequence Diagram

```mermaid
sequenceDiagram
    participant User as 👤 User
    participant BS as BackgroundService
    participant DS as DirectoryScanner
    participant FT as FileTracker
    participant SS as SubtitleService
    participant OSA as OpenSubtitlesAPI
    participant TS as TranslationService
    participant DB as Database
    participant FS as FileSystem

    User->>BS: Start Background Service
    BS->>DS: Initialize Directory Scanner
    BS->>FT: Initialize File Tracker
    BS->>DB: Create/Connect Database
    
    loop Every Scan Interval (30 min)
        BS->>DS: Scan for New Files
        DS->>FS: Check Monitored Directories
        FS-->>DS: Return Video Files
        DS->>FT: Get Pending Files
        FT->>DB: Query Pending/Failed Files
        DB-->>FT: Return File List
        FT-->>DS: Return Files to Process
        DS-->>BS: Return Files for Processing
        
        loop For Each Video File
            BS->>SS: Process Video File
            SS->>FS: Check if Hebrew Subtitle Exists
            
            alt Hebrew Subtitle Found
                FS-->>SS: Hebrew Subtitle Exists
                SS->>SS: Skip Processing
            else No Hebrew Subtitle
                FS-->>SS: No Hebrew Subtitle
                SS->>OSA: Search Hebrew Subtitles
                
                alt Hebrew Subtitles Found
                    OSA-->>SS: Return Hebrew Subtitles
                    SS->>SS: Download & Validate Hebrew
                else No Hebrew Subtitles
                    OSA-->>SS: No Hebrew Subtitles
                    SS->>OSA: Search English Subtitles
                    
                    alt English Subtitles Found
                        OSA-->>SS: Return English Subtitles
                        SS->>TS: Translate to Hebrew
                        TS->>SS: Return Hebrew Translation
                    else No Subtitles Found
                        OSA-->>SS: No Subtitles Available
                        SS->>SS: Mark as Failed
                    end
                end
                
                SS->>SS: Validate Hebrew Subtitle
                SS->>FS: Save Hebrew Subtitle File
            end
            
            SS-->>BS: Processing Complete
            BS->>FT: Update File Status
            FT->>DB: Save Processing Status
        end
    end
```

## File Processing Decision Flow

```mermaid
flowchart TD
    A[🎬 Video File Detected] --> B{🔍 Hebrew Subtitle Exists?}
    
    B -->|✅ Yes| C[⏭️ Skip Processing<br/>Already Complete]
    B -->|❌ No| D[🔎 Search Hebrew Subtitles]
    
    D --> E{🇮🇱 Hebrew Found?}
    E -->|✅ Yes| F[⬇️ Download Hebrew Subtitle]
    E -->|❌ No| G[🔍 Search English Subtitles]
    
    G --> H{🇺🇸 English Found?}
    H -->|✅ Yes| I[⬇️ Download English Subtitle]
    H -->|❌ No| J[❌ Mark as Failed<br/>No Subtitles Available]
    
    I --> K[🤖 Translate to Hebrew<br/>OpenAI API]
    F --> L[✅ Validate Hebrew Subtitle]
    K --> L
    
    L --> M{✅ Validation Passed?}
    M -->|✅ Yes| N[💾 Save Hebrew Subtitle<br/>Update Database]
    M -->|❌ No| O[🔧 Attempt Auto-Fix]
    
    O --> P{🔧 Fix Successful?}
    P -->|✅ Yes| N
    P -->|❌ No| Q[❌ Mark as Failed<br/>Validation Issues]
    
    N --> R[📊 Update Status: SUCCESS]
    C --> R
    J --> S[📊 Update Status: FAILED]
    Q --> S
    
    style A fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style C fill:#e8f5e8,stroke:#388e3c,stroke-width:2px
    style N fill:#e8f5e8,stroke:#388e3c,stroke-width:2px
    style R fill:#e8f5e8,stroke:#388e3c,stroke-width:2px
    style J fill:#ffebee,stroke:#d32f2f,stroke-width:2px
    style Q fill:#ffebee,stroke:#d32f2f,stroke-width:2px
    style S fill:#ffebee,stroke:#d32f2f,stroke-width:2px
```

## Component Dependencies

```mermaid
graph LR
    subgraph "Entry Points"
        A[run_background_service.py]
        B[src/main.py]
        C[scripts/translate_subtitles.py]
    end

    subgraph "Core Services"
        D[BackgroundService]
        E[SubtitleService]
        F[DirectoryScanner]
        G[FileTracker]
        H[NotificationService]
        I[ServiceCommunicationManager]
    end

    subgraph "Processing Services"
        J[OpenSubtitlesAPI]
        K[TranslationService]
        L[SubtitleValidationService]
    end

    subgraph "Infrastructure"
        M[ConfigManager]
        N[SubtitleLogger]
        O[FileTracker]
    end

    %% Dependencies
    A --> D
    B --> E
    C --> E
    
    D --> F
    D --> G
    D --> H
    D --> I
    D --> M
    D --> N
    
    E --> J
    E --> K
    E --> L
    E --> M
    E --> N
    
    F --> M
    F --> N
    F --> I
    
    G --> M
    G --> N
    G --> O
    
    H --> M
    H --> N
    
    I --> M
    I --> N

    classDef entryPoint fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef coreService fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef processingService fill:#e8f5e8,stroke:#388e3c,stroke-width:2px
    classDef infrastructure fill:#fff3e0,stroke:#f57c00,stroke-width:2px

    class A,B,C entryPoint
    class D,E,F,G,H,I coreService
    class J,K,L processingService
    class M,N,O infrastructure
```

## Database Schema

```mermaid
erDiagram
    processed_files {
        int id PK
        string file_path UK
        string file_hash
        int file_size
        real file_modified_time
        string processing_status
        real processing_start_time
        real processing_end_time
        real processing_duration
        string error_message
        real created_at
        real updated_at
    }

    subtitle_operations {
        int id PK
        int file_id FK
        string operation_type
        string operation_status
        string subtitle_language
        string subtitle_path
        string subtitle_source
        real operation_start_time
        real operation_end_time
        real operation_duration
        string error_message
        real created_at
    }

    scan_sessions {
        int id PK
        real session_start_time
        real session_end_time
        string directories_scanned
        int files_found
        int files_processed
        int files_skipped
        int files_failed
        real scan_duration
        real created_at
    }

    processed_files ||--o{ subtitle_operations : "has"
    scan_sessions ||--o{ processed_files : "discovers"
```

## Usage Instructions

1. **Copy the Mermaid code** from any of the diagrams above
2. **Paste into MermaidChart** (https://www.mermaidchart.com/)
3. **Customize styling** as needed
4. **Export** as PNG, SVG, or PDF

## Diagram Features

- **Color-coded layers** for easy understanding
- **Clear component relationships** with proper arrows
- **Professional styling** suitable for documentation
- **Comprehensive coverage** of all system components
- **Multiple perspectives** (architecture, flow, dependencies, database) 