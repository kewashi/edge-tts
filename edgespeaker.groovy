/*
 * Edge TTS Speaker Driver
 * Virtual speech device that sends speak(text) to parent app
 */

metadata {
    definition(name: "Edge TTS Speaker", namespace: "kenw", author: "Ken Washington") {
        capability "SpeechSynthesis"
        capability "Actuator"

        command "speak", [[name: "Speak Text", type: "STRING", description: "Text to speak"], [name: "Set Volume", type: "NUMBER", description: "Sets the volume before playing the message"],[name: "Voice ID", type: "STRING", description: "Voice ID to use for TTS"]]

    }
}

def installed() {
    log.debug "Edge TTS Speaker installed"
}

def updated() {
    log.debug "Edge TTS Speaker updated"
}

def speak(String text, Number volume = null, String voiceId = null) {
    log.debug "speak() called with text: ${text}, volume: ${volume}, voiceId: ${voiceId} on device: ${device.displayName}"
    if (parent) {
        if (volume != null) {
            // log.debug "Volume override provided: ${volume}"
            parent.handleSpeak(device, text, volume as Integer, voiceId)
        } else {
            parent.handleSpeak(device, text, null, voiceId)
        }
    } else {
        log.warn "No parent app; cannot speak"
    }
}
