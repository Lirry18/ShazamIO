import json

def extract_track_info(data):
    """
    Extracts track details such as artist, album, track name, genre, and year of release from the given data.
    
    Args:
        data (list): List of track result dictionaries starting with 'matches'.
    
    Returns:
        list: List of dictionaries containing the extracted information.
    """
    extracted_tracks = []
    for item in data:
        # Access 'track' dictionary if it exists
        track = item.get("track", {})
        if track:  # Proceed only if track data exists
            title = track.get("title", "Unknown Title")
            subtitle = track.get("subtitle", "Unknown Artist")
            album = next(
                (meta.get("text") for meta in track.get("sections", [{}])[0].get("metadata", []) if meta.get("title") == "Album"),
                "Unknown Album"
            )
            genre = track.get("genres", {}).get("primary", "Unknown Genre")
            release_year = next(
                (meta.get("text") for meta in track.get("sections", [{}])[0].get("metadata", []) if meta.get("title") == "Released"),
                "Unknown Year"
            )
            extracted_tracks.append({
                "Artist": subtitle,
                "Album": album,
                "Track Name": title,
                "Genre": genre,
                "Year Released": release_year
            })
    return extracted_tracks

# Load your data here. Replace 'final_list.txt' with your file's name.
with open("final_list.txt", "r") as file:
    data = json.load(file)

# Extract the relevant information.
tracks_info = extract_track_info(data)

# Print or save the extracted information.
for track in tracks_info:
    print(track)
