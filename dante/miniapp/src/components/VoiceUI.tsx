import { useVoiceSession, type VoiceStatus } from '../hooks/useVoiceSession'

interface VoiceUIProps {
  signedUrl: string
  sessionId: string
}

export function VoiceUI({ signedUrl, sessionId }: VoiceUIProps) {
  const { status, transcript, error, start, stop } = useVoiceSession({
    signedUrl,
    sessionId,
  })

  const isActive = status !== 'idle' && status !== 'error'

  return (
    <div style={styles.wrapper}>
      {/* Status label */}
      <div style={styles.statusLabel}>{statusLabels[status]}</div>

      {/* Transcript */}
      {transcript && (
        <div style={styles.transcript}>{transcript}</div>
      )}

      {/* Error */}
      {error && (
        <div style={styles.error}>{error}</div>
      )}

      {/* Mic button */}
      <button
        style={{
          ...styles.micButton,
          ...(status === 'listening' ? styles.micPulsing : {}),
          ...(status === 'speaking' ? styles.micSpeaking : {}),
          ...(status === 'connecting' || status === 'thinking' ? styles.micWaiting : {}),
        }}
        onClick={isActive ? stop : start}
        disabled={status === 'connecting'}
      >
        {isActive ? '■' : '🎙'}
      </button>

      {/* Hint text */}
      <div style={styles.hint}>
        {isActive ? 'Tap to end' : 'Tap to start voice chat'}
      </div>
    </div>
  )
}

const statusLabels: Record<VoiceStatus, string> = {
  idle: 'Ready',
  connecting: 'Connecting...',
  listening: 'Listening',
  thinking: 'Thinking...',
  speaking: 'Speaking',
  error: 'Error',
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 24,
    width: '100%',
    maxWidth: 400,
  },
  statusLabel: {
    fontSize: 20,
    fontWeight: 600,
    opacity: 0.9,
    letterSpacing: 1,
    textTransform: 'uppercase' as const,
  },
  transcript: {
    fontSize: 16,
    opacity: 0.7,
    textAlign: 'center' as const,
    maxHeight: 120,
    overflow: 'auto',
    padding: '8px 16px',
    borderRadius: 8,
    backgroundColor: 'rgba(255,255,255,0.05)',
    width: '100%',
  },
  error: {
    fontSize: 14,
    color: '#ff6b6b',
    textAlign: 'center' as const,
  },
  micButton: {
    width: 120,
    height: 120,
    borderRadius: '50%',
    border: '3px solid rgba(255,255,255,0.2)',
    backgroundColor: 'rgba(74, 144, 217, 0.3)',
    color: 'white',
    fontSize: 48,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 0.3s ease',
  },
  micPulsing: {
    backgroundColor: 'rgba(74, 217, 144, 0.4)',
    borderColor: 'rgba(74, 217, 144, 0.6)',
    boxShadow: '0 0 30px rgba(74, 217, 144, 0.3)',
    animation: 'pulse 1.5s ease-in-out infinite',
  },
  micSpeaking: {
    backgroundColor: 'rgba(217, 144, 74, 0.4)',
    borderColor: 'rgba(217, 144, 74, 0.6)',
    boxShadow: '0 0 30px rgba(217, 144, 74, 0.3)',
  },
  micWaiting: {
    backgroundColor: 'rgba(144, 144, 217, 0.3)',
    borderColor: 'rgba(144, 144, 217, 0.4)',
    opacity: 0.7,
  },
  hint: {
    fontSize: 14,
    opacity: 0.5,
  },
}
