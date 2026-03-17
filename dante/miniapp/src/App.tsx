import { useState, useEffect, useCallback } from 'react'
import { VoiceUI } from './components/VoiceUI'

declare global {
  interface Window {
    Telegram?: {
      WebApp: {
        initData: string
        ready: () => void
        expand: () => void
        close: () => void
        MainButton: {
          text: string
          show: () => void
          hide: () => void
          onClick: (cb: () => void) => void
        }
      }
    }
  }
}

// Gateway URL — same origin in production, configurable for dev
const GATEWAY_URL = import.meta.env.VITE_GATEWAY_URL || 'http://localhost:8765'

interface SessionInfo {
  sessionId: string
  signedUrl: string
}

export default function App() {
  const [initData, setInitData] = useState<string>('')
  const [session, setSession] = useState<SessionInfo | null>(null)
  const [error, setError] = useState<string>('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const tg = window.Telegram?.WebApp
    if (tg) {
      tg.ready()
      tg.expand()
      setInitData(tg.initData)
    } else {
      setError('Not running inside Telegram')
      setLoading(false)
    }
  }, [])

  const initSession = useCallback(async () => {
    if (!initData) return

    setLoading(true)
    setError('')

    const headers = {
      'Authorization': `tma ${initData}`,
      'Content-Type': 'application/json',
    }

    try {
      // Step 1: Create/resume session
      const sessionRes = await fetch(`${GATEWAY_URL}/api/session`, {
        method: 'POST',
        headers,
      })
      if (!sessionRes.ok) {
        const detail = await sessionRes.json().catch(() => ({}))
        throw new Error(detail.detail || `Session failed: ${sessionRes.status}`)
      }
      const sessionData = await sessionRes.json()

      // Step 2: Get signed WebRTC URL (use session token to avoid replay rejection)
      const tokenRes = await fetch(`${GATEWAY_URL}/api/token`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionData.session_token}`,
          'Content-Type': 'application/json',
        },
      })
      if (!tokenRes.ok) {
        const detail = await tokenRes.json().catch(() => ({}))
        throw new Error(detail.detail || `Token failed: ${tokenRes.status}`)
      }
      const tokenData = await tokenRes.json()

      setSession({
        sessionId: sessionData.session_id,
        signedUrl: tokenData.signed_url,
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Connection failed')
    } finally {
      setLoading(false)
    }
  }, [initData])

  // Auto-init when initData is available
  useEffect(() => {
    if (initData) {
      initSession()
    }
  }, [initData, initSession])

  if (error) {
    return (
      <div style={styles.container}>
        <div style={styles.error}>
          <p>{error}</p>
          <button style={styles.retryButton} onClick={initSession}>
            Retry
          </button>
        </div>
      </div>
    )
  }

  if (loading || !session) {
    return (
      <div style={styles.container}>
        <div style={styles.connecting}>Connecting...</div>
      </div>
    )
  }

  return (
    <div style={styles.container}>
      <VoiceUI signedUrl={session.signedUrl} sessionId={session.sessionId} />
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
    backgroundColor: '#1a1a2e',
    color: '#e0e0e0',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    padding: 16,
  },
  connecting: {
    fontSize: 18,
    opacity: 0.7,
  },
  error: {
    textAlign: 'center' as const,
  },
  retryButton: {
    marginTop: 16,
    padding: '12px 24px',
    fontSize: 16,
    backgroundColor: '#4a90d9',
    color: 'white',
    border: 'none',
    borderRadius: 8,
    cursor: 'pointer',
  },
}
