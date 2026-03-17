import { useConversation } from '@11labs/react'
import { useCallback, useRef, useState } from 'react'

export type VoiceStatus = 'idle' | 'connecting' | 'listening' | 'thinking' | 'speaking' | 'error'

interface UseVoiceSessionOptions {
  signedUrl: string
  sessionId: string
}

type ConversationModeChange = {
  mode: 'speaking' | 'listening'
}

type ConversationStatusChange = {
  status: string
}

export function useVoiceSession({ signedUrl, sessionId }: UseVoiceSessionOptions) {
  const [status, setStatus] = useState<VoiceStatus>('idle')
  const [transcript, setTranscript] = useState('')
  const [error, setError] = useState<string>('')

  // Track whether we're waiting for the agent to respond after user finishes speaking.
  // The @11labs/react hook has no explicit "thinking" event, so we derive it:
  // user transcript finalizes → "thinking" → agent starts speaking → "speaking"
  const waitingForAgent = useRef(false)

  const conversation = useConversation({
    onConnect: () => {
      setStatus('listening')
      setError('')
      waitingForAgent.current = false
    },
    onDisconnect: () => {
      setStatus('idle')
      waitingForAgent.current = false
    },
    onMessage: (message) => {
      if (message.source === 'user') {
        // User transcript update (partial or final)
        setTranscript(message.message)
      }
      if (message.source === 'ai') {
        // Agent is responding — transition out of thinking
        waitingForAgent.current = false
      }
    },
    onModeChange: (mode: ConversationModeChange) => {
      if (mode.mode === 'speaking') {
        // Agent is speaking — clear thinking state
        waitingForAgent.current = false
        setStatus('speaking')
      } else {
        // Mode changed to listening
        if (waitingForAgent.current) {
          // We were listening but the user's turn just ended and
          // the agent hasn't started speaking yet — this is "thinking"
          setStatus('thinking')
        } else {
          setStatus('listening')
        }
      }
    },
    onError: (err) => {
      setError(typeof err === 'string' ? err : 'Voice connection error')
      setStatus('error')
      waitingForAgent.current = false
    },
    onStatusChange: (statusChange: ConversationStatusChange) => {
      // ElevenLabs reports agent processing status changes
      // When the agent is processing (between user speech end and agent speech start),
      // this is our "thinking" window
      if (statusChange.status === 'processing') {
        waitingForAgent.current = true
        setStatus('thinking')
      }
    },
  })

  const start = useCallback(async () => {
    setStatus('connecting')
    setError('')
    setTranscript('')
    waitingForAgent.current = false
    try {
      await conversation.startSession({
        signedUrl,
        overrides: {
          agent: {
            prompt: {
              prompt: `Session ID: ${sessionId}. Route all responses through the backend webhook.`,
            },
          },
        },
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to connect')
      setStatus('error')
    }
  }, [conversation, signedUrl, sessionId])

  const stop = useCallback(async () => {
    await conversation.endSession()
    setStatus('idle')
    waitingForAgent.current = false
  }, [conversation])

  return {
    status,
    transcript,
    error,
    start,
    stop,
    isMuted: conversation.isSpeaking,
  }
}
