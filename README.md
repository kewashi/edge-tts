# Edge-TTS for Hubitat + Sonos  
### A Fully Local, Token-Secured Neural TTS Engine for Home Automation

This project provides a **local**, **secure**, **Sonos-compatible** text-to-speech (TTS) system for Hubitat Elevation using Microsoft’s **Edge-TTS neural voices**. It is designed as a modern alternative to Echo Speaks, especially after recent Amazon / Alexa changes that broke cookie-based authentication and device discovery for many users.

If you have Sonos speakers and want fast, high-quality TTS without relying on Alexa logins, cookies, Heroku, or cloud services — this project is for you.

---

## ✨ Features

- 100% **local** (runs on any Linux machine: DGX, Pi, NUC, VM, etc.)
- Uses **Microsoft Edge-TTS** neural voices — free and high-quality  
- Works with **any Sonos speaker** connected to Hubitat  
- Per-Sonos **virtual TTS devices** (one virtual per physical speaker)
- Simple `speak()` support:
  - `speak(text)`
  - `speak(text, volume)`
  - `speak(text, volume, voiceId)`
- Optional per-call volume override with automatic volume restore  
- Optional per-call voice override while still supporting a default voice  
- Secure shared-secret token for `/generate` endpoint  
- Tiny footprint — just Flask + edge-tts + ffmpeg  
- No cookies, no Amazon login, no Heroku deployment

---

## 🧱 Architecture Overview

High-level flow:

1. Hubitat (Edge TTS App) sends **POST** to `/generate` on your Linux box:  
   `{"text": "...", "voiceId": "...", "token": "..."}`  

2. The Python server:
   - Calls Edge-TTS to generate speech
   - Uses `ffmpeg` to normalize the audio
   - Writes a small MP3 file named `tts.mp3` on disk

3. Hubitat then calls `playTrack("http://<server>:5005/stream-tts.mp3")` on your chosen Sonos device(s)

4. Sonos connects directly to the Python server and streams `tts.mp3` via `/stream-tts.mp3`

The `/stream-tts.mp3` endpoint responds like a proper MP3 file service:
- `Content-Type: audio/mpeg`
- `Content-Length: ...`
- `Accept-Ranges: bytes`
- Optional `Range` support / 206 responses

Sonos behaves happily because:
- The URL ends in `.mp3`
- The HTTP headers are in a format it understands

---

## 📁 Project Files

Place these in your project/repository:

| File | Description |
|------|-------------|
| `server_dgx.py` | Main Python TTS server (Flask + edge-tts + ffmpeg + streaming) |
| `edge-tts.service` | systemd service unit to run the TTS server on boot |
| `edgetts.groovy` | Hubitat App: manages Sonos devices and sends TTS requests |
| `edgespeaker.groovy` | Hubitat Driver: virtual TTS speaker devices for each Sonos |
| `README.md` | This documentation |

---

## 🔧 1. Linux Server Setup

These instructions assume:

- Linux OS (e.g., AlmaLinux 8 / RHEL / Rocky / Ubuntu / Debian)
- Python 3.9+ installed
- You have SSH access

### 1.1 Install system dependencies

On AlmaLinux / RHEL / Rocky:

```bash
sudo dnf install -y ffmpeg
```

On Debian / Ubuntu:

```bash
sudo apt update
sudo apt install -y ffmpeg
```

### 1.2 Create a project folder

```bash
mkdir -p ~/edge-tts-server
cd ~/edge-tts-server
```

Copy the following files into this folder:

- `server_dgx.py`
- (Optional now, but recommended later) `edge-tts.service`

### 1.3 Create and activate a Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

Install Python dependencies:

```bash
pip install --upgrade pip
pip install flask edge-tts
```

### 1.4 Environment variables (optional for manual testing)

You can set environment variables for testing like this:

```bash
export EDGE_VOICE="en-US-AriaNeural"
export EDGE_TTS_TOKEN="change-me-to-a-secret"
export PORT=5005
```

> **Note:** The token must match what you configure later in the Hubitat app.

### 1.5 Run the server manually (for testing)

From inside your project folder, with the venv active:

```bash
python server_dgx.py
```

You should see Flask start and listen on port 5005.

In a browser (from your LAN):

```text
http://<server-ip>:5005/stream-tts.mp3
```

On first run (before a TTS file exists) this may 404 or return an error; after you generate at least one TTS clip, it should serve `tts.mp3`.

You can test TTS generation using a tool like `curl` or Postman:

```bash
curl -X POST   -H "Content-Type: application/json"   -d '{"text": "Hello from Edge TTS", "voiceId": "en-US-AriaNeural", "token": "change-me-to-a-secret"}'   http://<server-ip>:5005/generate
```

After that, `http://<server-ip>:5005/stream-tts.mp3` should play the generated audio.

---

## 🛎 2. Install as a systemd Service

To have the TTS server start automatically on boot, use the included `edge-tts.service` file.

### 2.1 Edit the service file

Open `edge-tts.service` and adjust:

- `User=` and `Group=` to your Linux username
- `WorkingDirectory=` to your project folder (e.g., `/home/youruser/edge-tts-server`)
- `ExecStart=` to point to your venv Python and server script:
  ```ini
  ExecStart=/home/youruser/edge-tts-server/venv/bin/python server_dgx.py
  ```
- `Environment=` lines:
  ```ini
  Environment=PORT=5005
  Environment=EDGE_VOICE=en-US-AriaNeural
  Environment=EDGE_TTS_TOKEN=change-me-to-a-secret
  ```

### 2.2 Install and enable the service

```bash
sudo cp edge-tts.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable edge-tts
sudo systemctl start edge-tts
sudo systemctl status edge-tts
```

You should see `Active: active (running)`.

To view logs:

```bash
sudo journalctl -u edge-tts -f
```

---

## 🟦 3. Hubitat App Setup (Edge TTS App)

### 3.1 Install the App Code

1. In Hubitat UI, go to **Drivers Code** → (we’ll use this for the driver next).
2. For the app:
   - Go to **Apps Code** → **New App**
   - Paste the contents of `edgetts.groovy`
   - Click **Save**

### 3.2 Add the App Instance

1. Go to **Apps** → **Add User App**
2. Select **Edge TTS App**
3. Configure the settings:

- **Base URL**  
  `http://<server-ip>:5005`  
  (Do not include `/generate` or `/stream-tts.mp3` — the app appends those paths)

- **Shared Secret Token**  
  Must match `EDGE_TTS_TOKEN` in your systemd service (e.g., `change-me-to-a-secret`)

- **Default Voice**  
  Choose from the dropdown list, e.g. `en-US-AriaNeural`

- **Delay after generate before play (ms)**  
  Typically `600–1200` ms is safe (depends on your network/CPU)

- **Delay before restoring volume (ms)**  
  Rough length of your typical TTS announcement, e.g. `4000–6000` ms

- **Select Sonos Speakers**  
  Choose one or more Sonos devices already integrated with Hubitat

- **Base name for virtual TTS devices**  
  e.g. `Edge TTS`

Click **Done** to let the app create child devices.

The app will create one child device per Sonos speaker, with names like:

- `Edge TTS - Kitchen`
- `Edge TTS - Living Room`

---

## 🔊 4. Hubitat Driver Setup (Edge TTS Speaker)

### 4.1 Install the Driver Code

1. Go to **Drivers Code** → **New Driver**
2. Paste the contents of `edgespeaker.groovy`
3. Click **Save**

The app will use this driver (`Edge TTS Speaker`) for its child devices.  
You do **not** need to create devices manually; the app handles that.

---

## 🎛 5. Using Edge TTS in Rules

Each virtual speaker (e.g., `Edge TTS - Kitchen`) exposes a `speak` command with up to three parameters:

```groovy
speak(text)
speak(text, volume)
speak(text, volume, voiceId)
```

### 5.1 Simple TTS using default voice / volume

In Rule Machine:

- Action → **Run Custom Action**
- Select capability: **SpeechSynthesis**
- Choose device: `Edge TTS - Kitchen`
- Command: `speak`
- Parameters:
  - Type: `string`
  - Value: `Front door opened`

This will:

1. POST to `/generate` with your default voice, no volume override
2. Wait `ttsDelayMs` milliseconds
3. Call `playTrack("http://<server-ip>:5005/stream-tts.mp3")` on the Kitchen Sonos

### 5.2 TTS with volume override

Same as above, but:

- Parameters:

  1. Type: `string` → `Motion detected in the garage`
  2. Type: `number` → `35` (volume 0–100)

The app will:

1. Capture the current volume of the target Sonos
2. Set volume to 35
3. Play `stream-tts.mp3`
4. After `restoreDelayMs`, restore the original volume

### 5.3 TTS with volume and voice override

You can override the voice per-call while keeping the app’s default for other calls.

Parameters:

1. Type: `string` → `System armed`
2. Type: `number` → `40`
3. Type: `string` → `en-US-JasonNeural`

The app will pass `voiceId` to the Python server; the server will use that voice instead of the default.

---

## 🎤 Voices

The app includes a built-in dropdown of recommended Edge TTS voices:

**Female (en-US)**  
- `en-US-AriaNeural`  
- `en-US-JennyNeural`  
- `en-US-MichelleNeural`  
- `en-US-CoraNeural`  

**Male (en-US)**  
- `en-US-GuyNeural`  
- `en-US-RogerNeural`  
- `en-US-SteffanNeural`  
- `en-US-EricNeural`  

You can also pass **any valid Edge TTS voice ID** as the `voiceId` parameter from rules.

---

## 🔒 Security Considerations

- `/generate` is protected by a **shared secret token**:
  - Set on the server via `EDGE_TTS_TOKEN` environment variable (or systemd service)
  - Set in Hubitat app as “Shared Secret Token”
- `/stream-tts.mp3` must be accessible to Sonos:
  - It is intentionally **not** token-protected
  - It should only be exposed on your LAN (no public port forwarding)
- Best practices:
  - Use a non-trivial token
  - Keep port 5005 restricted to your LAN / VLAN
  - Do not reuse this token for anything else

---

## 🧪 Troubleshooting

- **I can hit `/stream-tts.mp3` from a browser but Sonos won’t play it**
  - Make sure the URL ends in `.mp3`
  - Confirm Sonos and the server are on the same subnet / VLAN
  - Check that Flask is bound to `0.0.0.0` on port 5005

- **`/generate` returns 401 Unauthorized**
  - Verify the token in Hubitat matches `EDGE_TTS_TOKEN` on the server
  - Check systemd environment or shell `export` values

- **Sonos still plays an old track (like Kalimba)**
  - Make sure Hubitat is calling `playTrack("http://<server-ip>:5005/stream-tts.mp3")` correctly
  - Confirm `/generate` is actually being called (watch `journalctl -u edge-tts -f`)

- **I see multiple GETs to `/stream-tts.mp3`**
  - This is normal Sonos behavior (probing, controller vs player, grouped speakers)

---

## 📌 Notes & Future Ideas

Some ideas for future enhancement:

- Cache multiple TTS clips by phrase / hash
- Per-room default voice (Kitchen vs Bedroom voices)
- Multi-language support with automatic voice selection

Contributions and forks are welcome!

---

## ✅ Summary

This project gives you a:

- Local
- Token-secured
- Sonos-native
- High-quality neural TTS pipeline

…integrated directly with Hubitat, without relying on Alexa, cookies, or third-party cloud services.

Enjoy building with it!  
