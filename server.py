import os
import asyncio
import tempfile
import subprocess
import ssl

from flask import Flask, request, send_file, abort, Response
import edge_tts

app = Flask(__name__)

# BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.path.expanduser("~/public_html/wp-content/uploads")
DEFAULT_VOICE = os.environ.get("EDGE_VOICE", "en-US-AriaNeural")
DEFAULT_PORT = int(os.environ.get("PORT", "5005"))


@app.route("/")
def index():
    return "Edge TTS server is running"

async def generate_tts_file(text: str, voice: str, out_path: str):
    """Generate TTS with Edge TTS and re-encode to Sonos-friendly MP3."""
    communicate = edge_tts.Communicate(text=text, voice=voice)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp_raw_path = tmp.name
    tmp.close()

    try:
        # Raw MP3 from edge-tts
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
            check=False,
        )
    finally:
        if os.path.exists(tmp_raw_path):
            os.unlink(tmp_raw_path)


@app.route("/tts")
def tts():
    """GET /tts?text=Hello+world[&voiceId=en-US-GuyNeural]"""
    text = request.args.get("text", "").strip()
    voice = request.args.get("voiceId", DEFAULT_VOICE)
    filename = os.path.join(UPLOAD_DIR, "tts.mp3")

    # If no text provided, serve existing tts.mp3 if it exists
    if not text:
        if os.path.exists(filename):
            return send_file(filename, mimetype="audio/mpeg")
        return abort(400, "Missing 'text' parameter and no existing tts.mp3 available")
    # Otherwise generate a new tts.mp3 overwriting any previous one

    try:
        asyncio.run(generate_tts_file(text, voice, filename))
    except Exception as e:
        print("TTS error:", e)
        if os.path.exists(filename):
            os.unlink(filename)
        return Response("Internal TTS error", status=500)

    if os.path.exists(filename):
        return send_file(filename, mimetype="audio/mpeg")
    else:
        return Response("TTS generation failed", status=500)

@app.route("/generate")
def generate():
    """GET /generate?text=Hello+world[&voiceId=en-US-GuyNeural]"""
    text = request.args.get("text", "").strip()
    voice = request.args.get("voiceId", DEFAULT_VOICE)
    filename = os.path.join(UPLOAD_DIR, "tts.mp3")

    # If no text provided, serve existing tts.mp3 if it exists
    if not text:
        if os.path.exists(filename):
            return send_file(filename, mimetype="audio/mpeg")
        return abort(400, "Missing 'text' parameter and no existing tts.mp3 available")
    # Otherwise generate a new tts.mp3 overwriting any previous one


    try:
        asyncio.run(generate_tts_file(text, voice, filename))
    except Exception as e:
        print("TTS error:", e)
        if os.path.exists(filename):
            os.unlink(filename)
        return Response("Internal TTS error", status=500)

    if os.path.exists(filename):
        return Response(f"TTS file {filename} in voice {voice} generated successfully.", status=200)
    else:
        return Response("TTS generation failed", status=500)

if __name__ == "__main__":
    port = DEFAULT_PORT
    app.run(host="0.0.0.0", port=port, debug=False)

    # Same HTTPS pattern you already use in main.py
    # if os.path.exists("ftserver.crt") and os.path.exists("ftserver.key"):
    #     ssl_context = ("ftserver.crt", "ftserver.key")
    #     try:
    #         print("Starting secure TTS server at port", port)
    #         app.run(host="0.0.0.0", port=port, debug=False, ssl_context=ssl_context)
    #     except Exception as e:
    #         print(f"Error launching secure TTS server at port {port}: {e}")
    #         print(f"Starting insecure TTS server at port: {port}")
    #         app.run(host="0.0.0.0", port=port, debug=False)
    # else:
    #     print(f"Starting insecure TTS server at port: {port}")
    #     app.run(host="0.0.0.0", port=port, debug=True)
