import os
import hashlib
import asyncio
import tempfile
import subprocess

from flask import Flask, request, abort, Response, abort
from flask import jsonify
import edge_tts

app = Flask(__name__)

# Where we store generated MP3s
BASE_DIR = os.path.dirname(__file__)
OUT_PATH = os.path.join(BASE_DIR, "tts.mp3")
API_TOKEN = os.environ.get("EDGE_TTS_TOKEN", "token-not-set")

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


@app.route("/generate", methods=["POST"])
def generate():
    """POST /generate with JSON or form data: {"text": "Hello world", "voiceId": "en-US-GuyNeural"}"""

    # Try JSON body first, then form data as fallback
    data = request.get_json(silent=True) or {}
    if not data and request.form:
        data = request.form.to_dict()

    text = (data.get("text") or "").strip()
    voice = data.get("voiceId") or DEFAULT_VOICE
    token = data.get("token") or request.headers.get("X-EDGE-TTS-TOKEN")
    filename = OUT_PATH

    # If no text provided, serve existing tts.mp3 if it exists
    if not text:
        return jsonify({"error": "Missing 'text' parameter and no existing tts.mp3 available"}), 400

    # Simple token check
    if not token or token != API_TOKEN:
        print("Unauthorized TTS access attempt to /generate")
        return jsonify({"error": "Unauthorized"}), 401

    try:
        asyncio.run(generate_tts_file(text, voice, filename))
        return jsonify({"status": "ok"})
    except Exception as e:
        print("TTS error in /generate:", e)
        return jsonify({"error": "TTS error"}), 500


def _partial_response(path, start, end, file_size, mime="audio/mpeg"):
    length = end - start + 1
    with open(path, "rb") as f:
        f.seek(start)
        data = f.read(length)

    headers = {
        "Content-Type": mime,
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
    }
    return Response(data, status=206, headers=headers)


@app.route("/stream-tts.mp3", methods=["GET", "HEAD"])
def stream_tts():
    """
    Range-aware streaming endpoint for the last-generated TTS file.
    Sonos-friendly: supports Range requests and 206 responses.
    """
    path = OUT_PATH
    if not os.path.exists(path):
        abort(404)

    file_size = os.path.getsize(path)
    range_header = request.headers.get("Range", None)
    # print (f"file_size: {file_size} range_header: {range_header}")

    # No Range header: return full file
    if not range_header:
        headers = {
            "Content-Type": "audio/mpeg",
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        }

        if request.method == "HEAD":
            return Response(status=200, headers=headers)

        with open(path, "rb") as f:
            data = f.read()

        return Response(data, status=200, headers=headers)

    # Parse "bytes=start-end"
    try:
        _, range_value = range_header.split("=", 1)
        start_str, end_str = range_value.split("-", 1)
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1
    except Exception:
        # Malformed Range header
        print("Malformed Range header:", range_header)
        return Response(status=416)

    if start >= file_size or start < 0:
        # Invalid range
        return Response(status=416)

    if end is None or end >= file_size:
        end = file_size - 1

    # print(f"Serving bytes {start}-{end} of {file_size}")
    # print(f"Request method: {request.method}")
    # HEAD for range: just headers
    if request.method == "HEAD":
        length = end - start + 1
        headers = {
            "Content-Type": "audio/mpeg",
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
        }
        return Response(status=206, headers=headers)

    # Normal partial response for GET
    return _partial_response(path, start, end, file_size)

if __name__ == "__main__":
    # Bind to all interfaces so Sonos can reach it
    app.run(host="0.0.0.0", port=DEFAULT_PORT)
