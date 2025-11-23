# Edge-TTS for Hubitat + Sonos  
### A Fully Local, Token-Secured Neural TTS Engine for Home Automation

This project provides a **local**, **secure**, **Sonos-compatible** text-to-speech system for Hubitat Elevation using Microsoft’s **Edge-TTS neural voices**. It is designed as a modern alternative to Echo Speaks, especially after recent Amazon changes that broke cookie-based authentication.

If you have Sonos speakers and want fast, high-quality TTS without relying on cloud logins, cookies, or external services — this project is for you.

---

# ✨ Features

- 100% **local** (runs on any Linux machine: DGX, Pi, NUC, VM, etc.)
- Uses **Microsoft Edge-TTS** neural voices — free and high-quality  
- Works with **any Sonos speaker** connected to Hubitat  
- Per-speaker child devices with simple `speak()`  
- Optional per-call volume overrides with automatic volume restore  
- Custom per-call voice selection (`speak(text, volume, voiceId)`)  
- Secure shared-secret token for `/generate`  
- Tiny footprint — just Flask + edge-tts + ffmpeg  
- No cookies, no Amazon login, no Heroku

---

# 🧱 Architecture

Hubitat → POST /generate (text, voiceId, token)  
→ Python server generates tts.mp3 locally  
→ Hubitat → Sonos.playTrack("http://server:5005/stream-tts.mp3")  
→ Sonos streams tts.mp3 directly from your server  

---

# 📁 Project Files

| File | Description |
|------|-------------|
| **server_dgx.py** | Main Python TTS server |
| **edge-tts.service** | Systemd service |
| **edgetts.groovy** | Hubitat App |
| **edgespeaker.groovy** | Hubitat Driver |

---

# Installation instructions, hubitat setup, and usage examples omitted here for brevity.
