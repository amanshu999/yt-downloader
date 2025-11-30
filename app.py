import streamlit as st
import os
import shutil
import tempfile
from yt_dlp import YoutubeDL

# --- Page Config ---
st.set_page_config(page_title="YT Playlist Downloader", page_icon="📺", layout="wide")

# --- Helper Functions ---
def human_readable_size(num, suffix='B'):
    for unit in ['','K','M','G','T','P']:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Y{suffix}"

def process_download(url, mode, quality_preset, audio_format, audio_bitrate, limit, concurrent):
    """
    Downloads, converts, zips, and returns binary data.
    Includes a safety check for server RAM limits.
    """
    # Create a temporary directory (auto-deleted on exit)
    with tempfile.TemporaryDirectory() as tmp_dir:
        
        # Output template (e.g. "01 - MyVideo.mp4")
        out_tmpl = os.path.join(tmp_dir, "%(playlist_index)s - %(title)s.%(ext)s")
        
        opts = {
            "outtmpl": out_tmpl,
            "ignoreerrors": True,
            "concurrent_fragment_downloads": concurrent,
            "restrictfilenames": True, # Safe filenames for zip
            "quiet": True,             # Less log noise
            "noprogress": True,        # Prevent log flooding
        }

        if limit:
            opts["playlistend"] = limit

        # --- MODE CONFIGURATION ---
        if mode == "Video":
            # FORCE MP4: Download best streams and merge into mp4 container
            opts["merge_output_format"] = "mp4"
            
            if quality_preset == "Best Available":
                opts["format"] = "bestvideo+bestaudio/best"
            elif quality_preset == "1080p":
                opts["format"] = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
            elif quality_preset == "720p":
                opts["format"] = "bestvideo[height<=720]+bestaudio/best[height<=720]"
            elif quality_preset == "Worst (Low Data)":
                opts["format"] = "worstvideo+worstaudio/worst"
                
        else: # Audio Mode
            # FORCE CONVERSION: Convert to selected audio format
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_format,
                "preferredquality": audio_bitrate.replace("k", "")
            }]

        # --- 1. DOWNLOAD PHASE ---
        try:
            # Check if ffmpeg is installed on server
            if not shutil.which("ffmpeg"):
                return False, "CRITICAL ERROR: 'ffmpeg' not found. Did you create packages.txt?", None

            with YoutubeDL(opts) as ydl:
                ydl.download([url])
        except Exception as e:
            return False, f"Download Engine Error: {str(e)}", None

        # --- 2. ZIPPING PHASE ---
        try:
            # Create zip file in the temp folder
            archive_base = os.path.join(tmp_dir, "download_package")
            shutil.make_archive(archive_base, 'zip', tmp_dir)
            zip_path = archive_base + ".zip"
            
            # --- 3. SAFETY CHECK ---
            # Streamlit Cloud has ~1GB RAM. If we load a 2GB file, it crashes.
            file_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
            if file_size_mb > 550:
                return False, f"File too large for free cloud server ({file_size_mb:.1f} MB). Limit is 500MB. Try downloading fewer videos.", None
            
            # Read into RAM
            with open(zip_path, "rb") as f:
                zip_data = f.read()
                
            return True, "Success", zip_data
            
        except Exception as e:
            return False, f"Zipping Error: {str(e)}", None


# --- UI LAYOUT ---
st.title("📺 YT Downloader (Cloud Safe)")
st.info("☁️ **Note:** This runs on a free cloud server. Large playlists (>500MB) may fail. Please use the 'Limit' setting for large lists.")

with st.sidebar:
    st.header("⚙️ Settings")
    mode = st.radio("Mode", ["Video", "Audio"], index=0)
    st.divider()
    
    if mode == "Video":
        quality_preset = st.selectbox("Resolution", ["720p", "1080p", "Best Available", "Worst (Low Data)"], index=0)
        audio_format, audio_bitrate = None, None
        st.caption("Videos are automatically converted to **MP4**.")
    else:
        quality_preset = None
        audio_format = st.selectbox("Format", ["mp3", "m4a", "wav"])
        audio_bitrate = st.selectbox("Bitrate", ["192k", "320k", "128k"])
        st.caption(f"Audio converted to **{audio_format.upper()}**.")

    st.divider()
    limit_val = st.number_input("Limit # of videos (Recommended: 10)", min_value=1, value=10, step=1)
    concurrent = st.slider("Concurrent Downloads", 1, 5, 3)

url_input = st.text_input("Paste Playlist or Video URL:")

if url_input:
    if st.button(f"🚀 Start {mode} Process"):
        
        # Status container
        status_box = st.status("Processing... Please wait.", expanded=True)
        
        status_box.write("1. 📡 Connecting to YouTube...")
        status_box.write("2. 📥 Downloading & Converting content...")
        
        # Run process
        success, msg, zip_data = process_download(
            url_input, mode, quality_preset, 
            audio_format, audio_bitrate, limit_val, concurrent
        )
        
        if success:
            status_box.write("3. 📦 Zipping files...")
            status_box.update(label="Done! Ready to download.", state="complete", expanded=False)
            
            st.success("✅ Processing Complete!")
            st.download_button(
                label="📦 Download ZIP to Device",
                data=zip_data,
                file_name="my_playlist.zip",
                mime="application/zip",
                type="primary"
            )
        else:
            status_box.update(label="Failed", state="error", expanded=True)
            st.error(f"❌ Error: {msg}")
