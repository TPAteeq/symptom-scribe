import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { VoiceWebSocket, type MessageHandler } from '../services/websocket';

type VoiceStatus =
  | 'permission_request'
  | 'connecting'
  | 'initializing'
  | 'listening'
  | 'processing'
  | 'speaking'
  | 'completed'
  | 'emergency';

function VoiceInterface() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const patientName = (location.state as { patientName?: string } | null)?.patientName ?? '';

  const [status, setStatus] = useState<VoiceStatus>('permission_request');
  const [currentAiText, setCurrentAiText] = useState('');
  const [currentPartial, setCurrentPartial] = useState('');
  const [lastUserText, setLastUserText] = useState('');
  const [emergencyInfo, setEmergencyInfo] = useState<{ keywords: string[]; message: string } | null>(null);
  const [summaryId, setSummaryId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Playback
  const wsRef = useRef<VoiceWebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Audio capture (raw PCM via ScriptProcessorNode → AWS Transcribe on backend)
  const captureCtxRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<{ processor: ScriptProcessorNode; source: MediaStreamAudioSourceNode } | null>(null);
  const captureStreamRef = useRef<MediaStream | null>(null);
  const pcmBufferRef = useRef<Int16Array[]>([]);
  const isSpeakingRef = useRef(false);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Stale-closure guards
  const statusRef = useRef<VoiceStatus>('permission_request');
  const isListeningRef = useRef(false);

  useEffect(() => {
    statusRef.current = status;
    isListeningRef.current = status === 'listening';
  }, [status]);

  const stopAudioCapture = useCallback(() => {
    if (silenceTimerRef.current) { clearTimeout(silenceTimerRef.current); silenceTimerRef.current = null; }
    if (idleTimerRef.current) { clearTimeout(idleTimerRef.current); idleTimerRef.current = null; }
    if (processorRef.current) {
      try { processorRef.current.processor.disconnect(); } catch { /* ignore */ }
      try { processorRef.current.source.disconnect(); } catch { /* ignore */ }
      processorRef.current = null;
    }
    if (captureCtxRef.current && captureCtxRef.current.state !== 'closed') {
      captureCtxRef.current.close().catch(() => {});
      captureCtxRef.current = null;
    }
    if (captureStreamRef.current) {
      captureStreamRef.current.getTracks().forEach(t => t.stop());
      captureStreamRef.current = null;
    }
    pcmBufferRef.current = [];
    isSpeakingRef.current = false;
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (audioTimerRef.current) clearTimeout(audioTimerRef.current);
      wsRef.current?.disconnect();
      stopAudioCapture();
      if (audioContextRef.current?.state !== 'closed') {
        audioContextRef.current?.close();
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const playAudio = useCallback(async (base64Audio: string): Promise<void> => {
    if (!base64Audio) return;
    try {
      const bytes = Uint8Array.from(atob(base64Audio), (c) => c.charCodeAt(0));
      const ctx = audioContextRef.current ?? new AudioContext();
      audioContextRef.current = ctx;
      if (ctx.state === 'suspended') await ctx.resume();
      const buffer = await ctx.decodeAudioData(bytes.buffer);
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);
      return new Promise((resolve) => {
        const timeoutMs = buffer.duration * 1000 + 500;
        const timer = setTimeout(resolve, timeoutMs);
        source.onended = () => { clearTimeout(timer); resolve(); };
        source.start(0);
      });
    } catch {
      return;
    }
  }, []);

  const startAudioCapture = useCallback(() => {
    if (processorRef.current || !wsRef.current) return;

    navigator.mediaDevices
      .getUserMedia({ audio: { channelCount: 1, sampleRate: 16000 } })
      .then(stream => {
        captureStreamRef.current = stream;

        // 16 kHz AudioContext so PCM samples are already at the right rate for AWS Transcribe
        const ctx = new AudioContext({ sampleRate: 16000 });
        captureCtxRef.current = ctx;
        const source = ctx.createMediaStreamSource(stream);

        // ScriptProcessorNode: bufferSize 4096, 1 input ch, 1 output ch
        const processor = ctx.createScriptProcessor(4096, 1, 1);
        processorRef.current = { processor, source };

        processor.onaudioprocess = (e: AudioProcessingEvent) => {
          if (!isListeningRef.current) return;

          const float32 = e.inputBuffer.getChannelData(0);

          // RMS for voice activity detection
          let sumSq = 0;
          for (let i = 0; i < float32.length; i++) sumSq += float32[i] * float32[i];
          const rms = Math.sqrt(sumSq / float32.length);

          if (rms > 0.015) {
            // Active speech — reset idle timer
            isSpeakingRef.current = true;
            if (silenceTimerRef.current) { clearTimeout(silenceTimerRef.current); silenceTimerRef.current = null; }
            if (idleTimerRef.current) { clearTimeout(idleTimerRef.current); idleTimerRef.current = null; }

            // float32 → int16 PCM (16-bit little-endian)
            const int16 = new Int16Array(float32.length);
            for (let i = 0; i < float32.length; i++) {
              int16[i] = Math.max(-32768, Math.min(32767, Math.round(float32[i] * 32768)));
            }
            pcmBufferRef.current.push(int16);

          } else if (!isSpeakingRef.current && !idleTimerRef.current) {
            // No speech yet on this turn — start 2-minute idle timeout
            idleTimerRef.current = setTimeout(() => {
              idleTimerRef.current = null;
              wsRef.current?.disconnect();
              navigate('/');
            }, 2 * 60 * 1000);
          }

          if (rms <= 0.015 && isSpeakingRef.current && !silenceTimerRef.current) {
            // Silence after speech — start 2 s end-of-utterance timer
            silenceTimerRef.current = setTimeout(() => {
              silenceTimerRef.current = null;
              isSpeakingRef.current = false;

              const chunks = pcmBufferRef.current;
              pcmBufferRef.current = [];
              if (chunks.length === 0) return;

              // Concatenate all PCM chunks
              const totalLen = chunks.reduce((s, c) => s + c.length, 0);
              const combined = new Int16Array(totalLen);
              let offset = 0;
              for (const chunk of chunks) { combined.set(chunk, offset); offset += chunk.length; }

              // Close gate before status change to prevent any stale audio processing
              isListeningRef.current = false;
              setCurrentPartial('');
              setStatus('processing');
              wsRef.current?.sendAudioBlob(combined.buffer);
            }, 2000);
          }
        };

        source.connect(processor);
        // Must connect to destination for onaudioprocess to fire in Chrome
        processor.connect(ctx.destination);
      })
      .catch(() => {
        setError('Microphone access failed. Please allow mic access and try again.');
      });
  }, []);

  // Manage capture lifecycle based on status
  useEffect(() => {
    if (status === 'listening') {
      startAudioCapture();
    } else if (['speaking', 'processing', 'completed', 'emergency'].includes(status)) {
      stopAudioCapture();
    }
  }, [status, startAudioCapture, stopAudioCapture]);

  const connectAndStart = useCallback(async () => {
    if (!sessionId) return;
    setStatus('connecting');

    // Create playback AudioContext during user gesture so it's not blocked later
    try { audioContextRef.current = new AudioContext(); } catch { /* ignore */ }

    const handlers: MessageHandler = {
      onConnectionEstablished: () => {
        setStatus('initializing');
        wsRef.current?.startSession(sessionId, patientName);
      },
      onTranscriptionResult: (result) => {
        if (result.is_final && result.text) {
          setLastUserText(result.text);
          setCurrentPartial('');
        }
      },
      onAIResponse: (response) => {
        isListeningRef.current = false;
        setCurrentAiText(response.text);
        setLastUserText('');
        setCurrentPartial('');
        setStatus('speaking');
        if (response.audio_data) {
          playAudio(response.audio_data).then(() => {
            audioTimerRef.current = setTimeout(() => {
              audioTimerRef.current = null;
              setStatus('listening');
            }, 500);
          });
        } else {
          const pauseMs = Math.max(2000, response.text.split(' ').length * 220);
          audioTimerRef.current = setTimeout(() => {
            audioTimerRef.current = null;
            setStatus('listening');
          }, pauseMs);
        }
      },
      onEmergencyDetected: (emergency) => {
        stopAudioCapture();
        wsRef.current?.disconnect();
        setEmergencyInfo({ keywords: emergency.keywords, message: emergency.message });
        setStatus('emergency');
        if (emergency.audio_data) playAudio(emergency.audio_data);
      },
      onSessionComplete: (data) => {
        if (audioTimerRef.current) { clearTimeout(audioTimerRef.current); audioTimerRef.current = null; }
        stopAudioCapture();
        wsRef.current?.disconnect();
        setSummaryId(data.summary_id);
        setStatus('completed');
      },
      onStatusUpdate: (s) => {
        if (s === 'listening') setStatus('listening');
      },
      onError: (err) => {
        console.error('WebSocket error:', err);
        setError(err);
      },
      onDisconnect: () => {},
    };

    wsRef.current = new VoiceWebSocket(sessionId, handlers);
    wsRef.current.connect();
  }, [sessionId, playAudio]);

  const statusLabels: Record<VoiceStatus, string> = {
    permission_request: '',
    connecting: 'Connecting...',
    initializing: 'Starting your session...',
    listening: 'Listening',
    processing: 'Thinking...',
    speaking: 'Speaking...',
    completed: '',
    emergency: '',
  };

  const isActive = !['permission_request', 'completed', 'emergency'].includes(status);

  return (
    <div className="voice-interface">
      {/* Start screen */}
      {status === 'permission_request' && (
        <div className="permission-prompt">
          <h2>Pre-visit Check-in</h2>
          <p>Symptom Scribe will have a brief conversation with you before your doctor comes in.</p>
          {error && <p style={{ color: '#dc2626', marginBottom: '1rem' }}>{error}</p>}
          <button className="btn btn-primary" onClick={connectAndStart}>
            Start Check-in
          </button>
        </div>
      )}

      {/* Emergency */}
      {status === 'emergency' && emergencyInfo && (
        <div className="emergency-alert">
          <h2>Emergency Detected</h2>
          <p style={{ fontWeight: 600, fontSize: '1.1rem' }}>{emergencyInfo.message}</p>
          <p style={{ color: '#64748b', fontSize: '0.85rem', marginTop: '0.5rem' }}>
            Detected: {emergencyInfo.keywords.join(', ')}
          </p>
          <button className="btn btn-secondary" onClick={() => navigate('/')} style={{ marginTop: '1rem' }}>
            Return to Appointments
          </button>
        </div>
      )}

      {/* Active session */}
      {isActive && (
        <div className="active-session">
          <div className="session-status">
            <span className={`status-dot ${status}`} />
            <span className="status-label">{statusLabels[status]}</span>
          </div>

          {currentAiText && (
            <div className="message-bubble scribe-bubble">
              <span className="bubble-speaker">Symptom Scribe</span>
              <p>{currentAiText}</p>
            </div>
          )}

          {(currentPartial || lastUserText) && (
            <div className={`message-bubble user-bubble${currentPartial ? ' partial' : ''}`}>
              <span className="bubble-speaker">You</span>
              <p>{currentPartial || lastUserText}</p>
            </div>
          )}
        </div>
      )}

      {/* Completion */}
      {status === 'completed' && (
        <div className="completion-panel">
          <h2>Check-in Complete</h2>
          <p>Your summary has been prepared for your doctor.</p>
          {summaryId && <p style={{ fontSize: '0.8rem', color: '#64748b' }}>Summary ID: {summaryId}</p>}
          <div>
            <button className="btn btn-primary" onClick={() => navigate('/')}>
              Return to Appointments
            </button>
            <button className="btn btn-secondary" onClick={() => navigate('/doctor/doctor_001')}>
              View Doctor Dashboard
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default VoiceInterface;
