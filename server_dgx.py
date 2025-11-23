import os
import hashlib
import asyncio
import tempfile
import subprocess

from flask import Flask, request, send_file, abort, Response
import edge_tts

app = Flask(__name__)

# Where we store generated MP3s
BASE_DIR = os.path.dirname(__file__)
CACHE_DIR = os.path.join(BASE_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Default voice (can override with EDGE_VOICE env or voiceId query param)
DEFAULT_VOICE = os.environ.get("EDGE_VOICE", "en-US-AriaNeural")

# Default port (can override with PORT env)
DEFAULT_PORT = int(os.environ.get("PORT", "5005"))


@app.route("/")
def index():
    return "Edge TTS server is running"


async def generate_tts_file(text: str, voice: str, out_path: str):
    """
    Generate TTS audio using Edge TTS into a temp file,
    then re-encode with ffmpeg into a Sonos-friendly MP3 at out_path.
    """
    # 1) Use edge-tts to create a raw MP3
    communicate = edge_tts.Communicate(text=text, voice=voice)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp_raw_path = tmp.name
    tmp.close()

    try:
        # Save raw TTS MP3
        await communicate.save(tmp_raw_path)

        # 2) Re-encode using ffmpeg to 44.1kHz stereo, 128kbps CBR
        # This helps ensure Sonos compatibility
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",                  # overwrite
            "-i", tmp_raw_path,    # input
            "-ar", "44100",        # audio rate: 44.1 kHz
            "-ac", "2",            # audio channels: stereo
            "-b:a", "128k",        # bitrate
            out_path
        ]

        subprocess.run(
            ffmpeg_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False
        )

    finally:
        # Remove the raw/tmp file
        if os.path.exists(tmp_raw_path):
            os.unlink(tmp_raw_path)


@app.route("/tts")
def tts():
    """
    GET /tts?text=Hello+world[&voiceId=en-US-GuyNeural]

    Returns an MP3 suitable for Sonos playback.
    """
    text = request.args.get("text", "").strip()
    voice = request.args.get("voiceId", DEFAULT_VOICE)
    filename = os.path.join(BASE_DIR, "tts.mp3")

    # If no text provided, serve existing tts.mp3 if it exists
    if not text:
        if os.path.exists(filename):
            return send_file(filename, mimetype="audio/mpeg")
        return abort(400, "Missing 'text' parameter and no existing tts.mp3 available")
    # Otherwise generate a new tts.mp3 overwriting any previous one

    # Generate (overwriting any existing tts.mp3)
    try:
        asyncio.run(generate_tts_file(text, voice, filename))
    except Exception as e:
        print("TTS error:", e)
        if os.path.exists(filename):
            os.unlink(filename)
        return Response("Internal TTS error", status=500)

    if os.path.exists(filename):
        return send_file(filename, mimetype="audio/mpeg")
    return Response("TTS generation failed", status=500)


if __name__ == "__main__":
    # Bind to all interfaces so Sonos can reach it
    app.run(host="0.0.0.0", port=DEFAULT_PORT)
