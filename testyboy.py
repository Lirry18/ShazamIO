import os
from pydub import AudioSegment
from pydub.utils import make_chunks
import tempfile
from datetime import timedelta
import subprocess
import asyncio
from shazamio import Shazam

def download_youtube_audio(youtube_url, temp_dir):
    """
    Downloads audio from a YouTube URL using youtube-dl and saves it to the temporary directory.
    
    Args:
        youtube_url (str): URL of the YouTube video.
        temp_dir (str): Path to the temporary directory.
    
    Returns:
        str: File path of the downloaded audio file.
    """
    output_template = os.path.join(temp_dir, "audio_file.%(ext)s")
    command = [
        "yt_dlp",
        "--verbose",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "192K",
        "-o", output_template,
        youtube_url
    ]
    
    try:
        subprocess.run(["python3", "-m", "yt_dlp"] + command[1:], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for file in os.listdir(temp_dir):
            if file.startswith("audio_file") and file.endswith(".mp3"):
                return os.path.join(temp_dir, file)
    except subprocess.CalledProcessError as e:
        raise Exception(f"Error downloading audio: {e.stderr.decode()}")

def format_time(milliseconds):
    """
    Formats milliseconds into a human-readable time format (hh_mm_ss).
    
    Args:
        milliseconds (int): Time in milliseconds.
    
    Returns:
        str: Formatted time string.
    """
    seconds = milliseconds // 1000
    time_format = str(timedelta(seconds=seconds))
    return time_format.replace(":", "_")

def split_audio_into_chunks(audio_file, chunk_duration=40):
    """
    Splits the audio file into chunks of specified duration.
    
    Args:
        audio_file (str): Path to the audio file.
        chunk_duration (int): Duration of each chunk in seconds.
    
    Returns:
        list: List of paths to the audio chunks.
    """
    audio = AudioSegment.from_file(audio_file)
    chunks = make_chunks(audio, chunk_duration * 1000)  # Duration in milliseconds
    chunk_paths = []
    
    for i, chunk in enumerate(chunks):
        start_time = format_time(i * chunk_duration * 1000)
        chunk_filename = f"{os.path.splitext(audio_file)[0]}_chunk_{start_time}.mp3"
        chunk.export(chunk_filename, format="mp3")
        chunk_paths.append(chunk_filename)
    
    return chunk_paths

async def analyze_chunk_with_shazam(file_path):
    """
    Analyzes an audio chunk using ShazamIO and returns the recognized track details.
    
    Args:
        file_path (str): Path to the audio file chunk.
    
    Returns:
        dict: JSON object containing the recognized song details, or None if no match.
    """
    shazam = Shazam()
    try:
        result = await shazam.recognize(file_path)
        return result
    except Exception as e:
        print(f"Error analyzing file {file_path}: {e}")
        return None
    
def extract_track_info(entry, timestamp):
    """
    Extracts track details such as artist, album, track name, genre, year of release, and timestamp.
    """
    track_info = entry.get("track", {})
    
    title = track_info.get("title", "Unknown Track Name")
    artist = track_info.get("subtitle", "Unknown Artist")
    genre = track_info.get("genres", {}).get("primary", "Unknown Genre")
    
    sections = track_info.get("sections", [])
    album = "Unknown Album"
    year_released = "Unknown Year"
    for section in sections:
        metadata = section.get("metadata", [])
        for meta in metadata:
            if meta.get("title") == "Album":
                album = meta.get("text", "Unknown Album")
            if meta.get("title") == "Released":
                year_released = meta.get("text", "Unknown Year")
    
    return {
        "Track Name": title,
        "Artist": artist,
        "Album": album,
        "Genre": genre,
        "Year Released": year_released,
        "Timestamp": timestamp
    }

def deduplicate_results(results):
    """
    Removes duplicates from the list of song recognition results.
    
    Args:
        results (list): List of JSON objects containing song details.
    
    Returns:
        list: Deduplicated list of JSON objects.
    """
    seen = set()
    deduplicated = []
    for result in results:
        if result and result.get('track') and result['track']['key'] not in seen:
            seen.add(result['track']['key'])
            print('FOUND DUPLICATE')
            deduplicated.append(result)
    return deduplicated

async def main():
    youtube_url = input("Enter the YouTube URL: ")
    
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            print("Downloading audio from YouTube...")
            audio_file = download_youtube_audio(youtube_url, temp_dir)
            print(f"Audio file downloaded to {audio_file}")
            
            print("Splitting audio into chunks...")
            chunks = split_audio_into_chunks(audio_file)
            print("Audio split into chunks:")
            for chunk in chunks:
                print(chunk)
            
            print("Analyzing audio chunks with Shazam...")
            results = []
            for chunk in chunks:
                print("Readin chunk ..")
                print(chunk)
                result = await analyze_chunk_with_shazam(chunk)
                if result:
                    results.append(result)
            
            print("Deduplicating results...")
            deduplicated_results = deduplicate_results(results)

            print("Extracting track information...")
            extracted_info = [
                extract_track_info(result, chunk["timestamp"])
                for result, chunk in zip(deduplicated_results, results)
            ]
            
            print("Final list of recognized tracks:")
            print(extracted_info)
        
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
