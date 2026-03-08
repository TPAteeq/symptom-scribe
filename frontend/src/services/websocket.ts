/**
 * WebSocket client for voice streaming.
 * Connects to /api/voice/ws/{sessionId} via Vite proxy.
 */

export interface MessageHandler {
  onConnectionEstablished: () => void;
  onTranscriptionResult: (result: { text: string; confidence: number; is_final: boolean }) => void;
  onAIResponse: (response: { text: string; audio_data: string }) => void;
  onEmergencyDetected: (emergency: { keywords: string[]; message: string; audio_data: string }) => void;
  onSessionComplete: (data: { summary_id: string; severity_flag: string; message: string }) => void;
  onStatusUpdate: (status: string) => void;
  onError: (error: string) => void;
  onDisconnect: () => void;
}

export class VoiceWebSocket {
  private ws: WebSocket | null = null;
  private sessionId: string;
  private handlers: MessageHandler;
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 3;

  constructor(sessionId: string, handlers: MessageHandler) {
    this.sessionId = sessionId;
    this.handlers = handlers;
  }

  connect(): void {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.ws = new WebSocket(`${protocol}//${window.location.host}/api/voice/ws/${this.sessionId}`);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.startPing();
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.handleMessage(data);
      } catch {
        console.error('Failed to parse WebSocket message');
      }
    };

    this.ws.onclose = () => {
      this.stopPing();
      this.handlers.onDisconnect();
    };

    this.ws.onerror = () => {
      this.handlers.onError('WebSocket connection error');
    };
  }

  private handleMessage(data: { type: string; [key: string]: unknown }): void {
    switch (data.type) {
      case 'connection_established':
        this.handlers.onConnectionEstablished();
        break;
      case 'transcription_result':
        this.handlers.onTranscriptionResult({
          text: data.text as string,
          confidence: data.confidence as number,
          is_final: data.is_final as boolean,
        });
        break;
      case 'ai_response':
        this.handlers.onAIResponse({
          text: data.text as string,
          audio_data: data.audio_data as string,
        });
        break;
      case 'emergency_detected':
        this.handlers.onEmergencyDetected({
          keywords: data.keywords as string[],
          message: data.message as string,
          audio_data: data.audio_data as string,
        });
        break;
      case 'session_complete':
        this.handlers.onSessionComplete({
          summary_id: data.summary_id as string,
          severity_flag: data.severity_flag as string,
          message: data.message as string,
        });
        break;
      case 'status_update':
        this.handlers.onStatusUpdate(data.status as string);
        break;
      case 'error':
        this.handlers.onError(data.error_message as string || 'Unknown error');
        break;
      case 'pong':
        break;
      default:
        console.log('Unknown message type:', data.type);
    }
  }

  startSession(symptomSessionId: string, patientName?: string): void {
    this.send({ type: 'start_session', symptom_session_id: symptomSessionId, patient_name: patientName ?? '' });
  }

  startTranscription(sampleRate = 16000): void {
    this.send({ type: 'start_transcription', sample_rate: sampleRate, language_code: 'en-US' });
  }

  sendAudioChunk(audioData: ArrayBuffer): void {
    const base64 = arrayBufferToBase64(audioData);
    this.send({ type: 'audio_chunk', audio_data: base64 });
  }

  // Send a complete utterance (raw PCM) for backend transcription
  sendAudioBlob(audioData: ArrayBuffer): void {
    const base64 = arrayBufferToBase64(audioData);
    this.send({ type: 'audio_chunk', audio_data: base64, is_final: true });
  }

  sendTextInput(text: string): void {
    this.send({ type: 'text_input', text });
  }

  endTranscription(): void {
    this.send({ type: 'end_transcription' });
  }

  disconnect(): void {
    this.maxReconnectAttempts = 0; // Prevent reconnect on intentional disconnect
    this.stopPing();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  private send(data: object): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  private startPing(): void {
    this.pingInterval = setInterval(() => {
      this.send({ type: 'ping' });
    }, 30000);
  }

  private stopPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}
