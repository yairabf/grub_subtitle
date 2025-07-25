import os
import struct
import re

def calculate_opensubtitles_hash(file_path):
    """Calculate OpenSubtitles hash for a file."""
    longlongformat = '<q'
    bytesize = struct.calcsize(longlongformat)
    
    f = open(file_path, "rb")
    filesize = os.path.getsize(file_path)
    hash = filesize
    
    if filesize < 65536 * 2:
        return None
    
    for x in range(65536//bytesize):
        buffer = f.read(bytesize)
        (l_value,)= struct.unpack(longlongformat, buffer)
        hash += l_value
        hash = hash & 0xFFFFFFFFFFFFFFFF
    
    f.seek(max(0, filesize-65536), 0)
    for x in range(65536//bytesize):
        buffer = f.read(bytesize)
        (l_value,)= struct.unpack(longlongformat, buffer)
        hash += l_value
        hash = hash & 0xFFFFFFFFFFFFFFFF
    
    f.close()
    return "%016x" % hash

def get_episode_info(file_path):
    """Extract show name, season, and episode for subtitle filtering."""
    # Example path: /.../ShowName/Season.3/ShowName.S03E01.EpisodeTitle.mkv
    dir_name = os.path.basename(os.path.dirname(file_path))
    show_dir = os.path.basename(os.path.dirname(os.path.dirname(file_path)))
    filename = os.path.basename(file_path)
    name_wo_ext = os.path.splitext(filename)[0]

    # Try to extract SxxExx pattern
    match = re.search(r'[Ss](\d{2})[Ee](\d{2})', name_wo_ext)
    season = int(match.group(1)) if match else None
    episode = int(match.group(2)) if match else None

    # Use show_dir as show_name
    show_name = show_dir

    # Calculate file hash for better matching
    file_hash = calculate_opensubtitles_hash(file_path)
    
    return {
        'filename': filename,
        'title': show_name,  # Use show name for search
        'show_name': show_name,
        'season': season,
        'episode': episode,
        'directory': dir_name,
        'hash': file_hash
    } 