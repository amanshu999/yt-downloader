import streamlit as st
import os
import shutil
import tempfile
from yt_dlp import YoutubeDL

# --- Page Config ---
st.set_page_config(page_title="YT Playlist Downloader", page_icon="📺", layout="wide")

# --- Helper Functions ---

def human_readable_size(num, suffix='B'):
    """Converts bytes to human readable string."""
    for unit in ['','K','M','G','T','P']:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Y{suffix}"

class StreamlitProgressHook:
    """Updates the Streamlit UI during the download."""
    def __init__(self):
        self.prog_bar = st.progress(0)
        self.status_text = st.empty()

    def __call__(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)
            if total:
                percent = downloaded / total
                self.prog_bar.progress(max(0.0, min(1.0, percent)))
            
            filename = os.path.basename(d.get('filename', 'Unknown'))
            speed = d.get('speed')
            speed_str = human_readable_size(speed) + "/s" if speed else "N/A"
            self.status_text.text(f"📥 Downloading: {filename}\n🚀 Speed: {speed_str}")
            
        elif d['status'] == 'finished':
            self.prog_bar.progress(100)
            self.status_text.text(f"✅ Conversion/Processing: {os.path.basename(d['filename'])}")

def process_download(url, mode, quality_preset, audio_format, audio_bitrate, limit, concurrent):
    """
    Downloads files to a temp dir, converts them, zips them, and returns the zip binary.
    """
    # Create a temporary directory that is deleted automatically when the 'with' block ends
    with tempfile.TemporaryDirectory() as tmp_dir:
        
        # Output template: 01 - Video Title.ext
        out_tmpl = os.path.join(tmp_dir, "%(playlist_index)s - %(title)s.%(ext)s")
        
        progress_tracker = StreamlitProgressHook()

        opts = {
            "outtmpl": out_tmpl,
            "progress_hooks": [progress_tracker],
            "ignoreerrors": True,
            "concurrent_fragment_downloads": concurrent,
            "restrictfilenames": True, # Ensure filenames are safe for all OS
        }

        if limit:
            opts["playlistend"] = limit

        # --- MODE CONFIGURATION ---
        if mode == "Video":
            # 1. Video Mode: Force MP4
            # 'merge_output_format': 'mp4' tells yt-dlp to download the best streams 
            # (often mkv/webm) and merge them into an mp4 container.
            opts["merge_output_format"] = "mp4"
            
            if quality_preset == "Best Available":
                opts["format"] = "bestvideo+bestaudio/best"
            elif quality_preset == "1080p":
                opts["format"] = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
            elif quality_preset == "720p":
                opts["format"] = "bestvideo[height<=720]+bestaudio/best[height<=720]"
            elif quality_preset == "Worst (Low Data)":
                opts["format"] = "worstvideo+worstaudio/worst"
                
        else: 
            # 2. Audio Mode: Force Conversion (MP3, etc)
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_format,
                "preferredquality": audio_bitrate.replace("k", "")
            }]

        # --- EXECUTE DOWNLOAD ---
        try:
            with YoutubeDL(opts) as ydl:
                ydl.download([url])
        except Exception as e:
            return False, str(e), None

        # --- ZIP THE RESULT ---
        # Create a zip file of the temp directory
        archive_path = os.path.join(tmp_dir, "download_package")
        shutil.make_archive(archive_path, 'zip', tmp_dir)
        
        # Read the zip file into RAM so we can pass it to the user
        final_zip_path = archive_path + ".zip"
        if os.path.exists(final_zip_path):
            with open(final_zip_path, "rb") as f:
                zip_data = f.read()
            return True, "Success", zip_data
        else:
            return False, "Zip file creation failed.", None


# --- UI LAYOUT ---

st.title("📺 YouTube Playlist Downloader")
st.markdown("Download videos (MP4) or music (MP3) from playlists directly to your device.")

with st.sidebar:
    st.header("⚙️ Settings")
    mode = st.radio("Download Mode", ["Video", "Audio"], index=0)
    st.divider()
    
    if mode == "Video":
        quality_preset = st.selectbox("Max Resolution", ["Best Available", "1080p", "720p", "Worst (Low Data)"])
        # Placeholders for audio vars
        audio_format, audio_bitrate = None, None
        st.info("ℹ️ Videos will be converted to **MP4** automatically.")
    else:
        quality_preset = None
        audio_format = st.selectbox("Format", ["mp3", "m4a", "wav"])
        audio_bitrate = st.selectbox("Bitrate", ["192k", "320k", "128k"])
        st.info(f"ℹ️ Audio will be converted to **{audio_format.upper()}**.")

    with st.expander("Advanced Settings"):
        limit_val = st.number_input("Limit # of items (0 = download all)", min_value=0, value=0)
        limit = limit_val if limit_val > 0 else None
        concurrent = st.slider("Concurrent Fragments", 1, 10, 4, help="More fragments = faster download, but higher CPU usage.")

url_input = st.text_input("Paste Playlist or Video URL:")

if url_input:
    if st.button(f"🚀 Prepare {mode} Download"):
        
        with st.status("Processing on server... please wait.", expanded=True) as status:
            st.write("1. Initializing download engine...")
            
            success, msg, zip_data = process_download(
                url_input, mode, quality_preset, 
                audio_format, audio_bitrate, limit, concurrent
            )
            
            if success:
                status.update(label="Processing Complete!", state="complete", expanded=False)
                
                # Success Message
                st.success("✅ Files are ready!")
                
                # The actual download button
                st.download_button(
                    label="📦 Click here to Save ZIP",
                    data=zip_data,
                    file_name="my_playlist.zip",
                    mime="application/zip",
                    type="primary"
                )
            else:
                status.update(label="Download Failed", state="error")
                st.error(f"Error: {msg}")