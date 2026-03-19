import AVFoundation
import Foundation
import Speech

@Observable
final class SpeechService {
    var isRecording: Bool = false
    var transcription: String = ""
    var isAvailable: Bool = false

    private let recognizer: SFSpeechRecognizer?
    private var audioEngine = AVAudioEngine()
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?

    private var permissionsRequested = false

    init() {
        recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    }

    // MARK: - Permissions

    func ensurePermissions() async {
        guard !permissionsRequested else { return }
        permissionsRequested = true

        let speechStatus = await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { status in
                continuation.resume(returning: status)
            }
        }

        guard speechStatus == .authorized else {
            isAvailable = false
            return
        }

        let micStatus = await AVAudioApplication.requestRecordPermission()
        isAvailable = micStatus
    }

    // MARK: - Recording

    func startRecording() async {
        await ensurePermissions()
        guard isAvailable, !isRecording else { return }
        transcription = ""

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        recognitionRequest = request

        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { [weak self] buffer, _ in
            self?.recognitionRequest?.append(buffer)
        }

        recognitionTask = recognizer?.recognitionTask(with: request) { [weak self] result, error in
            guard let self else { return }
            if let result {
                self.transcription = result.bestTranscription.formattedString
            }
            if error != nil || result?.isFinal == true {
                self.stopEngine()
            }
        }

        do {
            try audioEngine.start()
            isRecording = true
        } catch {
            stopEngine()
        }
    }

    @discardableResult
    func stopRecording() -> String {
        stopEngine()
        return transcription
    }

    // MARK: - Private

    private func stopEngine() {
        recognitionRequest?.endAudio()
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionTask?.cancel()
        recognitionRequest = nil
        recognitionTask = nil
        isRecording = false
    }
}
