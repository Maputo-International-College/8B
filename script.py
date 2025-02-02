import os
import re
import requests
import yt_dlp
import musicbrainzngs
from mutagen.mp4 import MP4, MP4Cover
from bs4 import BeautifulSoup
from pydub import AudioSegment

# Configure MusicBrainz for album lookup
musicbrainzngs.set_useragent("MusicDownloader", "1.0", "myemail@example.com")

# Function to create directory structure
def create_folder(artist, album):
    folder_path = os.path.join(artist, album)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path

# Extract metadata from YouTube
def get_metadata(video_url):
    ydl_opts = {'quiet': True, 'skip_download': True, 'extract_flat': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        return {
            "title": info.get("title", "Unknown"),
            "artist": info.get("artist", "Unknown"),
            "album": info.get("album", "Unknown"),
            "duration": info.get("duration", 0)
        }

# Download highest quality audio
def download_audio(video_url, save_path):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': save_path,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'm4a', 'preferredquality': '0'}],
        'quiet': False
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

# Search for correct album name
def get_correct_album(song_title, artist):
    try:
        result = musicbrainzngs.search_recordings(recording=song_title, artist=artist, limit=1)
        if result["recording-list"]:
            return result["recording-list"][0]["release-list"][0]["title"]
    except:
        return "Unknown Album"
    return "Unknown Album"

# Download album art
def download_album_art(album, save_path="cover.jpg"):
    search_url = f"https://www.google.com/search?tbm=isch&q={album}+album+cover"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(search_url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        images = soup.find_all("img")
        if images:
            img_url = images[1]["src"]
            img_data = requests.get(img_url).content
            with open(save_path, "wb") as handler:
                handler.write(img_data)
            print(f"Album art saved: {save_path}")
        else:
            print("No album art found.")

# Fetch lyrics
def download_lyrics(song_title, artist):
    search_url = f"https://www.lyrics.com/serp.php?st={song_title}+{artist}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(search_url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        links = soup.find_all("a", href=True)
        for link in links:
            if "/lyric/" in link["href"]:
                lyrics_url = "https://www.lyrics.com" + link["href"]
                lyrics_page = requests.get(lyrics_url, headers=headers)
                lyrics_soup = BeautifulSoup(lyrics_page.text, "html.parser")
                lyrics_div = lyrics_soup.find("pre", {"id": "lyric-body-text"})
                if lyrics_div:
                    return lyrics_div.text.strip()
    return None

# Embed metadata into .m4a files (album art & lyrics)
def embed_metadata(audio_file, image_file, lyrics):
    audio = MP4(audio_file)
    
    # Embed album art
    if os.path.exists(image_file):
        with open(image_file, "rb") as img:
            audio["covr"] = [MP4Cover(img.read(), MP4Cover.FORMAT_JPEG)]

    # Embed lyrics
    if lyrics:
        audio["\xa9lyr"] = lyrics  # '©lyr' tag is for storing lyrics in MP4 metadata

    audio.save()
    print(f"Metadata embedded into {audio_file}")

# Trim silence
def trim_audio(file_path, original_duration):
    audio = AudioSegment.from_file(file_path)
    current_duration = len(audio) / 1000
    if current_duration > original_duration + 2:
        trimmed_audio = audio[:original_duration * 1000]
        trimmed_audio.export(file_path, format="m4a")
        print(f"Trimmed: {file_path}")

# Process playlists
def process_playlist(playlist_url, artist, album):
    ydl_opts = {'quiet': True, 'extract_flat': True, 'skip_download': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        playlist_info = ydl.extract_info(playlist_url, download=False)
        for entry in playlist_info["entries"]:
            process_song(entry["url"], artist, album)

# Process individual songs
def process_song(video_url, artist, album):
    metadata = get_metadata(video_url)
    if not artist:
        artist = metadata["artist"]
    if not album or album == "Unknown Album":
        album = get_correct_album(metadata["title"], artist)

    folder = create_folder(artist, album)
    file_name = f"{metadata['title']}.m4a"
    save_path = os.path.join(folder, file_name)

    print(f"Downloading: {metadata['title']} to {folder}")
    download_audio(video_url, save_path)

    trim_audio(save_path, metadata["duration"])
    album_art_path = os.path.join(folder, "cover.jpg")
    download_album_art(album, album_art_path)

    # Fetch lyrics
    lyrics = download_lyrics(metadata["title"], artist)

    # Embed album art & lyrics
    embed_metadata(save_path, album_art_path, lyrics)

# Main function (uses url.txt by default)
def process_txt_file():
    txt_file = "url.txt"
    if not os.path.exists(txt_file):
        print("Error: 'url.txt' not found.")
        return

    with open(txt_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    artist, album = None, None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        elif "Album name" in line:
            album = line.replace("Album name", "").strip()
        elif "Links" in line:
            continue
        elif re.match(r"https?://", line):
            if "playlist" in line:
                process_playlist(line, artist, album)
            else:
                process_song(line, artist, album)

# Run script (automatically reads url.txt)
if __name__ == "__main__":
    process_txt_file()
