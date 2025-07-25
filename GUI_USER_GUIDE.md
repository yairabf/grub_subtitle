# Hebrew Subtitle Service GUI - User Guide

## 🎬 Overview

The Hebrew Subtitle Service GUI is a desktop application that automatically downloads and translates subtitles for video files. It searches for Hebrew subtitles first, and if none are available, it downloads English subtitles and translates them to Hebrew.

## 🚀 Getting Started

### Installation

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up API Keys:**
   - Create a `.env` file in the project root
   - Add your API keys:
     ```
     OPENSUBTITLES_USERNAME=your_username
     OPENSUBTITLES_PASSWORD=your_password
     OPENAI_API_KEY=your_openai_key
     ```

3. **Launch the GUI:**
   ```bash
   python run_gui.py
   ```

## 🖥️ GUI Interface

### Main Window Layout

The GUI consists of several sections:

1. **Header** - Application title and version
2. **File Selection Panel** - Add files or folders for processing
3. **Progress Panel** - Real-time processing status
4. **Results Panel** - Processing results and statistics
5. **Sidebar** - Quick actions and statistics
6. **Status Bar** - Current status and progress

### File Selection

#### Adding Individual Files
1. Click **"Add Files"** button
2. Select video files (`.mkv`, `.mp4`, `.avi`, etc.)
3. Files will appear in the file selection panel

#### Adding Folders
1. Click **"Add Folder"** button
2. Select a folder containing video files
3. All video files in the folder will be added

#### Drag and Drop
- Drag video files or folders directly onto the file selection area
- Supported formats: `.mkv`, `.mp4`, `.avi`, `.mov`, `.wmv`, `.flv`

### Processing

1. **Start Processing:**
   - Click **"Start Processing"** button
   - The application will begin processing all selected files

2. **Monitor Progress:**
   - Watch real-time progress in the progress panel
   - See current file being processed
   - View overall completion percentage

3. **View Results:**
   - Results appear in the results panel
   - Green checkmarks indicate success
   - Red X marks indicate errors
   - Click on results for detailed information

## 📁 File Organization

### Where Files Are Saved

**Important:** Subtitle files are now saved in the **same directory as the video files**, not in a separate output directory.

#### Example Structure:
```
Your Videos/
├── Movie1.mkv
├── Movie1.eng.srt     # Downloaded English subtitle
├── Movie1.heb.srt     # Translated Hebrew subtitle
├── Movie2.mkv
├── Movie2.eng.srt
└── Movie2.heb.srt
```

### File Naming Convention

- **English subtitles:** `[video_name].eng.srt`
- **Hebrew subtitles:** `[video_name].heb.srt`
- **Existing Hebrew subtitles:** `[video_name].heb.srt` (if already present)

## 🔄 Processing Logic

The application follows this workflow for each video file:

1. **Check for Existing Hebrew Subtitle**
   - Look for `.heb.srt` file in the same directory
   - If found, skip to next file

2. **Search for Hebrew Subtitle Online**
   - Search OpenSubtitles for Hebrew subtitles
   - Try multiple Hebrew language codes (`heb`, `he`)
   - Download if found

3. **Download English Subtitle**
   - If no Hebrew subtitle available, search for English
   - Download the most popular English subtitle

4. **Translate to Hebrew**
   - Use OpenAI GPT-3.5-turbo to translate English to Hebrew
   - Preserve timing and formatting
   - Save as `.heb.srt` file

## ⚙️ Configuration

### Configuration File
The application uses `config/config.yaml` for settings:

```yaml
api:
  opensubtitles:
    username: your_username
    password: your_password
  openai:
    api_key: your_openai_key

processing:
  max_chunk_size: 1500
  max_blocks_per_chunk: 5
  retry_attempts: 3

paths:
  default_output_dir: null  # null = save in video directory
```

### Security Features
- **Encrypted API Key Storage** - API keys are encrypted on disk
- **Secure Network Communication** - HTTPS with certificate validation
- **Audit Logging** - All operations are logged for security

## 🛠️ Troubleshooting

### Common Issues

#### "No files selected for processing"
- **Solution:** Add files using "Add Files" or "Add Folder" buttons

#### "Subtitle service not initialized"
- **Solution:** Check your API keys in the `.env` file

#### "API rate limit exceeded"
- **Solution:** The application will automatically retry with exponential backoff

#### "Translation failed"
- **Solution:** Check your OpenAI API key and quota

#### "No Hebrew subtitle found"
- **Solution:** This is normal - the app will download English and translate it

### Error Messages

- **Green checkmark** ✅ - Success
- **Red X** ❌ - Error occurred
- **Yellow warning** ⚠️ - Warning (processing may continue)

### Logs
- Detailed logs are saved in `logs/` directory
- Check logs for detailed error information
- Logs rotate automatically to prevent disk space issues

## 📊 Performance Tips

### Optimal Settings
- **Small files (< 100MB):** Default settings work well
- **Large files (> 500MB):** May take longer due to translation chunking
- **Batch processing:** Process multiple files for efficiency

### Network Usage
- **Download phase:** ~1-5MB per subtitle file
- **Translation phase:** ~10-50 API calls per file (depending on size)
- **Total time:** 1-5 minutes per file (depending on size and network)

## 🔧 Advanced Features

### Validation
The application includes comprehensive Hebrew subtitle validation:
- **Hebrew character detection**
- **SRT format validation**
- **Timing verification**
- **Content quality checks**

### Retry Logic
- **API failures:** Automatic retry with exponential backoff
- **Network issues:** Automatic retry up to 3 times
- **Translation errors:** Automatic chunk retry

### Security
- **API key encryption**
- **Secure file operations**
- **Audit logging**
- **Input validation**

## 📞 Support

### Getting Help
1. Check the troubleshooting section above
2. Review the logs in `logs/` directory
3. Check your API keys and internet connection
4. Ensure video files are in supported formats

### File Formats Supported
- **Video:** `.mkv`, `.mp4`, `.avi`, `.mov`, `.wmv`, `.flv`
- **Subtitles:** `.srt`, `.sub`, `.ssa`, `.ass`

### System Requirements
- **OS:** Windows 10+, macOS 10.14+, Linux
- **Python:** 3.8 or higher
- **Memory:** 512MB RAM minimum
- **Storage:** 100MB free space
- **Network:** Internet connection required

---

**Version:** 1.0.0  
**Last Updated:** 2024  
**Support:** Check the README.md for more information 