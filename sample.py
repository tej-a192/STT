import requests

DEEPGRAM_API_KEY = "9f65dad738baa6edcfad7d4a1a6b88b30c5bdaf9"

url = "https://api.deepgram.com/v1/listen?model=nova-3-general&detect_language=true"

audio_file = r"C:\Users\balan\OneDrive\Documents\Sound Recordings\Recording (2).m4a"

headers = {
    "Authorization": f"Token {DEEPGRAM_API_KEY}",
    "Content-Type": "audio/mp4"
}

with open(audio_file, "rb") as f:
    response = requests.post(url, headers=headers, data=f)

result = response.json()

channel = result["results"]["channels"][0]

print("\nDetected Language:", channel["detected_language"])
print("Language Confidence:", channel["language_confidence"])
print("Transcript:", channel["alternatives"][0]["transcript"])
