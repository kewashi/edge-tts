/*
 * Edge TTS App
 * Uses Edge TTS server to generate speech and plays on Sonos via static MP3 URL
 * the /stream-tts.mp3 endpoint is range-aware and has the .mp3 extension for Sonos compatibility
 */

definition(
    name: "Edge TTS App",
    namespace: "kenw",
    author: "Ken Washington",
    description: "Edge TTS integration for Sonos using /generate and /stream-tts.mp3",
    category: "Convenience",
    iconUrl: "",
    iconX2Url: "",
    singleInstance: true
)

preferences {
    page(name: "mainPage", title: "Edge TTS Settings", install: true, uninstall: true) {

        section("TTS Server Settings") {
            input "baseUrl", "text",
                title: "TTS server base URL",
                required: true,
                defaultValue: "http://192.168.4.161:5005",
                description: "Base URL and port for generating mp3 and invoking TTS (e.g. http://192.168.1.50:5005)"

            input "sharedSecretToken", "password",
                title: "Shared secret token for /generate",
                required: true,
                description: "Must match EDGE_TTS_TOKEN on the server (or use token-not-set to disable token check)"
             
            input "ttsDelayMs", "number",
                title: "Delay after generate before play (ms)",
                required: true,
                defaultValue: 1000

            input "restoreDelayMs", "number",
                title: "Delay before restoring original volumes (ms)",
                required: true,
                defaultValue: 5000

            input "defaultVoiceId", "enum",
                title: "Default Edge TTS voice",
                required: true,
                defaultValue: "en-US-AriaNeural",
                options: [
                    "en-US-AriaNeural"    : "Aria (F)",
                    "en-US-JennyNeural"   : "Jenny (F)",
                    "en-US-MichelleNeural": "Michelle (F)",
                    "en-US-CoraNeural"    : "Cora (F)",
                    "en-US-GuyNeural"     : "Guy (M)",
                    "en-US-RogerNeural"   : "Roger (M)",
                    "en-US-SteffanNeural" : "Steffan (M)",
                    "en-US-EricNeural"    : "Eric (M)"
                ]
        }

        section("Sonos Speakers") {
            input "sonosSpeakers", "capability.musicPlayer",
                title: "Select Sonos speakers to use (one virtual TTS device will be created per Sonos)",
                multiple: true,
                required: true
        }

        section("Virtual TTS Device Base Name") {
            input "childDeviceBaseName", "text",
                title: "Base name for virtual TTS devices",
                required: true,
                defaultValue: "Edge TTS"
        }

        section("Logging") {
            input "logEnable", "bool", title: "Enable debug logging?", defaultValue: true
        }
    }
}

def installed() {
    logDebug "Installed"
    initialize()
}

def updated() {
    logDebug "Updated"
    unsubscribe()
    initialize()
}

def initialize() {
    createChildDevicesForSonos()
}

/**
 * Create one child TTS device per selected Sonos speaker.
 * Child DNI format: edge-tts-<sonos.id>
 */
private createChildDevicesForSonos() {
    if (!sonosSpeakers) {
        logDebug "No Sonos speakers selected; no child devices created"
        return
    }

    def existingChildren = getChildDevices()
    def desiredIds = sonosSpeakers.collect { it.id.toString() }

    // Create or update children for each Sonos
    sonosSpeakers.each { spk ->
        String sonosId = spk.id.toString()
        String dni = "edge-tts-${sonosId}"
        def child = getChildDevice(dni)
        String label = "${childDeviceBaseName ?: 'Edge TTS'} - ${spk.displayName}"

        if (!child) {
            logDebug "Creating child TTS device for Sonos: ${spk.displayName} (dni: ${dni})"
            try {
                addChildDevice("kenw", "Edge TTS Speaker", dni,
                    [label: label, isComponent: true, name: label])
            } catch (e) {
                log.error "Error creating child device for ${spk.displayName}: ${e}"
            }
        } else {
            if (child.displayName != label) {
                logDebug "Updating child device label for ${spk.displayName} to ${label}"
                child.setLabel(label)
            }
        }
    }

    // Remove children that no longer correspond to selected Sonos
    existingChildren.each { child ->
        String dni = child.deviceNetworkId
        if (dni?.startsWith("edge-tts-")) {
            String sonosId = dni.replace("edge-tts-", "")
            if (!desiredIds.contains(sonosId)) {
                logDebug "Deleting child device ${child.displayName} (removed Sonos)"
                deleteChildDevice(dni)
            }
        }
    }
}

/**
 * Called by a child device when speak(text) is invoked.
 * We map that child back to its Sonos device via the DNI suffix.
 */
def handleSpeak(childDevice, String text, Number volumeOverride = null, String voiceId = null) {
    logDebug "handleSpeak() from ${childDevice?.displayName} with text: ${text}, voiceId: ${voiceId}, volume: ${volumeOverride}"

    if (!baseUrl || !sonosSpeakers) {
        log.warn "Missing configuration; cannot speak"
        return
    }

    String childDni = childDevice.deviceNetworkId
    if (!childDni?.startsWith("edge-tts-")) {
        log.warn "Child DNI not in expected format: ${childDni}  name: ${childDevice.displayName}; cannot map to Sonos"
        return
    }

    String sonosId = childDni.replace("edge-tts-", "")
    def targetSonos = sonosSpeakers.find { it.id.toString() == sonosId }

    if (targetSonos) {
        if (volumeOverride != null && volumeOverride > 0 && volumeOverride <= 100) {
            log.debug "Volume override provided: ${volumeOverride}"
            speakOnSpeakers(text, [targetSonos], volumeOverride as Integer, voiceId)
        } else {
            speakOnSpeakers(text, [targetSonos], null, voiceId)
        }
    }
}

/**
 * Generate TTS and play on provided Sonos device(s).
 * If volumeOverride is not null, set that volume before playing and restore afterward.
 */
private speakOnSpeakers(String text, Collection speakers, Integer volumeOverride = null, String voiceId = null) {
    // URL-encode the text
    String generateUrl = baseUrl + "/generate"
    String voiceToUse = voiceId ?: defaultVoiceId

    Map body = [
        text   : text,
        voiceId: voiceToUse,
        token  : sharedSecretToken ?: "token-not-set"
    ]

    def params = [
        uri               : generateUrl,
        contentType       : "application/json",
        requestContentType: "application/json",
        body              : body
    ]

    logDebug "POSTing to generate endpoint: ${generateUrl} with text=${text}, token=${sharedSecretToken}, voice=${voiceToUse}"
    try {
        httpPost(params) { resp ->
            logDebug "Generate response status: ${resp.status}"
        }
    } catch (e) {
        log.error "Error calling TTS generate endpoint via POST: ${e}"
        return
    }

    // Wait for file to be written
    Long delayMs = (ttsDelayMs ?: 1000) as Long
    logDebug "Waiting ${delayMs} ms before playing MP3"
    pauseExecution(delayMs)

    // Capture original volumes if we're overriding
    Map oldVolumes = [:]
    if (volumeOverride != null && volumeOverride > 0 && volumeOverride <= 100) {
        speakers.each { spk ->
            def curVol = spk.currentValue("volume")
            if (curVol != null) {
                oldVolumes[spk.id] = (curVol as Integer)
                logDebug "Captured original volume ${curVol} for ${spk.displayName}"
            } else {
                logDebug "No current volume reported for ${spk.displayName}"
            }
        }
    }

    // Set override volume (if any) and play
    // set the play URL to the stream-tts endpoint with text and voiceId
    String mp3Url = baseUrl + "/stream-tts.mp3"
    speakers.each { spk ->
        try {
            if (volumeOverride != null && volumeOverride > 0 && volumeOverride <= 100) {
                logDebug "Setting volume ${volumeOverride} on ${spk.displayName}"
                spk.setVolume(volumeOverride as Integer)
            }
            logDebug "Calling playTrack on ${spk.displayName} with URL: ${mp3Url}"
            spk.playTrack(mp3Url)
        } catch (e) {
            log.error "Error calling playTrack on ${spk.displayName}: ${e}"
        }
    }

    // Restore original volumes after TTS if we overrode volume
    if ( (volumeOverride != null && volumeOverride > 0 && volumeOverride <= 100) && !oldVolumes.isEmpty() ) {
        Long restoreMs = (restoreDelayMs ?: 5000) as Long
        logDebug "Waiting ${restoreMs} ms before restoring volumes"
        pauseExecution(restoreMs)

        speakers.each { spk ->
            try {
                def orig = oldVolumes[spk.id]
                if (orig != null) {
                    logDebug "Restoring volume ${orig} on ${spk.displayName}"
                    spk.setVolume(orig as Integer)
                }
            } catch (e) {
                log.error "Error restoring volume on ${spk.displayName}: ${e}"
            }
        }
    }
}

private logDebug(msg) {
    if (logEnable) {
        log.debug "[EdgeTTS] ${msg}"
    }
}