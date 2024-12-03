import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit, QPushButton, QLabel, QTextEdit, QTreeWidget, QTreeWidgetItem
)
import threading
import asyncio
import requests
import subprocess
import tempfile
import os
from pydub import AudioSegment
from pydub.utils import make_chunks
from shazamio import Shazam
import json

SLSKD_URL = "http://localhost:5150/jsonrpc"


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.tracks = []

    def init_ui(self):
        self.setWindowTitle("YouTube to Soulseek Pipeline")
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()

        # YouTube URL Input
        self.url_input = QLineEdit(self)
        self.url_input.setPlaceholderText("Enter YouTube URL here...")
        layout.addWidget(self.url_input)

        # Process Button
        self.process_button = QPushButton("Process", self)
        self.process_button.clicked.connect(self.start_processing)
        layout.addWidget(self.process_button)

        # Status Label
        self.status_label = QLabel("Waiting for input...", self)
        layout.addWidget(self.status_label)

        # Recognized Tracks TreeView
        self.track_list = QTreeWidget(self)
        self.track_list.setHeaderLabels(["Track Name", "Artist", "Timestamp"])
        self.track_list.itemDoubleClicked.connect(self.on_track_click)
        layout.addWidget(self.track_list)

        # Soulseek Search Results
        self.results_text = QTextEdit(self)
        self.results_text.setReadOnly(True)
        layout.addWidget(self.results_text)

        self.setLayout(layout)

    def start_processing(self):
        threading.Thread(target=self.process_pipeline, daemon=True).start()

    def process_pipeline(self):
        url = self.url_input.text()
        if not url:
            self.status_label.setText("Error: Please enter a YouTube URL.")
            return

        self.status_label.setText("Downloading audio...")
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                audio_file = self.download_youtube_audio(url, temp_dir)
                self.status_label.setText("Splitting audio into chunks...")
                chunks = self.split_audio_into_chunks(audio_file)

                self.status_label.setText("Analyzing audio chunks...")
                results = []
                for chunk in chunks:
                    result = asyncio.run(self.analyze_chunk_with_shazam(chunk["file"]))
                    if result:
                        results.append({"data": result, "chunk_timestamp": chunk["timestamp"]})

                self.tracks = [
                    self.extract_track_info(result["data"], result["chunk_timestamp"])
                    for result in results
                ]
                self.update_track_list()
                self.status_label.setText("Processing complete. Double-click a track to search Soulseek.")
            except Exception as e:
                self.status_label.setText(f"Error: {e}")

    def update_track_list(self):
        self.track_list.clear()
        for track in self.tracks:
            item = QTreeWidgetItem([track["Track Name"], track["Artist"], track["Timestamp"]])
            self.track_list.addTopLevelItem(item)

    def on_track_click(self, item):
        track_name = item.text(0)  # Track Name is in the first column
        self.results_text.setPlainText(f"Searching Soulseek for: {track_name}\n")
        results = self.slskd_search(track_name)
        if results:
            for result in results:
                self.results_text.append(f"User: {result['username']}")
                self.results_text.append(f"File: {result['path']}")
                self.results_text.append(f"Size: {result['filesize']} bytes")
                self.results_text.append("-" * 40)
        else:
            self.results_text.append(f"No results found for '{track_name}'.")

    @staticmethod
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

    @staticmethod
    def split_audio_into_chunks(audio_file, chunk_duration=40):
        audio = AudioSegment.from_file(audio_file)
        chunks = make_chunks(audio, chunk_duration * 1000)
        chunk_paths = []
        for i, chunk in enumerate(chunks):
            start_time = f"{(i * chunk_duration) // 60}:{(i * chunk_duration) % 60:02}"
            chunk_filename = f"{os.path.splitext(audio_file)[0]}_chunk_{start_time}.mp3"
            chunk.export(chunk_filename, format="mp3")
            chunk_paths.append({"file": chunk_filename, "timestamp": start_time})
        return chunk_paths

    @staticmethod
    async def analyze_chunk_with_shazam(file_path):
        shazam = Shazam()
        try:
            return await shazam.recognize(file_path)
        except Exception as e:
            print(f"Error analyzing file {file_path}: {e}")
            return None

    @staticmethod
    def extract_track_info(entry, chunk_timestamp):
        track_info = entry.get("track", {})
        return {
            "Track Name": track_info.get("title", "Unknown"),
            "Artist": track_info.get("subtitle", "Unknown"),
            "Timestamp": chunk_timestamp
        }

    @staticmethod
    def slskd_search(track_name):
        payload = {"jsonrpc": "2.0", "method": "search", "params": {"query": track_name}, "id": 1}
        try:
            response = requests.post(SLSKD_URL, json=payload)
            response.raise_for_status()
            return response.json().get("result", [])
        except requests.RequestException as e:
            return [{"username": "Error", "path": str(e), "filesize": "N/A"}]


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec_())
