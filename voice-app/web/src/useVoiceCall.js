import Vapi from '@vapi-ai/web'
import { useCallback, useEffect, useReducer, useRef } from 'react'
import { fetchVoiceConfig, verifyPatient } from './api.js'
import { CallPhase, callReducer, initialCallState } from './callMachine.js'

const CONNECT_TIMEOUT_MS = 20000
const END_FALLBACK_MS = 3000
const VOICE_NOT_SET_UP = "Voice calls aren't set up yet. Add the Vapi keys and restart the server."
const MIC_BLOCKED = 'Microphone access is blocked. Allow it in your browser settings, then try again.'
const MIC_UNSUPPORTED = 'This browser can’t use the microphone here. Open the page over https or on localhost.'
const CONNECT_FAILED = "Couldn't connect to the agent. Try again."

async function findMicrophoneProblem() {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) return MIC_UNSUPPORTED
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    stream.getTracks().forEach((track) => track.stop())
    return null
  } catch (error) {
    console.error('Microphone check failed', error)
    return MIC_BLOCKED
  }
}

function isFinalTranscript(message) {
  return message?.type === 'transcript' && message.transcriptType === 'final' && message.transcript?.trim()
}

export function useVoiceCall() {
  const [state, dispatch] = useReducer(callReducer, initialCallState)
  const phaseRef = useRef(state.phase)
  const configRef = useRef(null)
  const vapiRef = useRef(null)
  const connectTimerRef = useRef(null)

  phaseRef.current = state.phase

  const clearConnectTimer = useCallback(() => {
    clearTimeout(connectTimerRef.current)
    connectTimerRef.current = null
  }, [])

  const stopVapiQuietly = useCallback(() => {
    try {
      vapiRef.current?.stop()
    } catch (error) {
      console.error('Stopping the call failed', error)
    }
  }, [])

  const getVapi = useCallback(
    (publicKey) => {
      if (vapiRef.current) return vapiRef.current
      const vapi = new Vapi(publicKey)
      vapi.on('call-start', () => {
        clearConnectTimer()
        if (phaseRef.current === CallPhase.ENDING) stopVapiQuietly()
        dispatch({ type: 'callStarted' })
      })
      vapi.on('call-end', () => {
        clearConnectTimer()
        dispatch({ type: 'callEnded' })
      })
      vapi.on('error', (error) => {
        console.error('Voice call error', error)
        clearConnectTimer()
        stopVapiQuietly()
        dispatch({ type: 'callFailed' })
      })
      vapi.on('message', (message) => {
        if (isFinalTranscript(message)) {
          dispatch({ type: 'transcriptReceived', role: message.role, text: message.transcript.trim() })
        }
      })
      vapiRef.current = vapi
      return vapi
    },
    [clearConnectTimer, stopVapiQuietly],
  )

  useEffect(() => {
    fetchVoiceConfig().then((config) => {
      configRef.current = config
    })
    return () => {
      clearConnectTimer()
      stopVapiQuietly()
    }
  }, [clearConnectTimer, stopVapiQuietly])

  const startCall = useCallback(
    async (patientId) => {
      if (phaseRef.current !== CallPhase.IDLE) return
      const config = configRef.current ?? (await fetchVoiceConfig())
      configRef.current = config
      if (!config.voiceReady) {
        dispatch({ type: 'voiceUnavailable', message: VOICE_NOT_SET_UP })
        return
      }

      dispatch({ type: 'startRequested' })
      const verification = await verifyPatient(patientId)
      if (!verification.found) {
        dispatch({ type: 'patientRejected', message: verification.message })
        return
      }
      dispatch({ type: 'patientVerified', displayName: verification.displayName })

      const microphoneProblem = await findMicrophoneProblem()
      if (microphoneProblem) {
        dispatch({ type: 'callFailed', message: microphoneProblem })
        return
      }
      if (phaseRef.current !== CallPhase.CONNECTING) return

      try {
        const vapi = getVapi(config.publicKey)
        connectTimerRef.current = setTimeout(() => {
          stopVapiQuietly()
          dispatch({ type: 'callFailed', message: CONNECT_FAILED })
        }, CONNECT_TIMEOUT_MS)
        const call = await vapi.start(config.assistantId, { variableValues: { patientId } })
        if (!call) throw new Error('Vapi returned no call')
      } catch (error) {
        console.error('Starting the call failed', error)
        clearConnectTimer()
        dispatch({ type: 'callFailed', message: CONNECT_FAILED })
      }
    },
    [clearConnectTimer, getVapi, stopVapiQuietly],
  )

  const endCall = useCallback(() => {
    if (phaseRef.current !== CallPhase.IN_CALL && phaseRef.current !== CallPhase.CONNECTING) return
    dispatch({ type: 'endRequested' })
    clearConnectTimer()
    stopVapiQuietly()
    setTimeout(() => {
      if (phaseRef.current === CallPhase.ENDING) dispatch({ type: 'callEnded' })
    }, vapiRef.current ? END_FALLBACK_MS : 0)
  }, [clearConnectTimer, stopVapiQuietly])

  const markIdEdited = useCallback(() => dispatch({ type: 'idEdited' }), [])
  const rejectId = useCallback((message) => dispatch({ type: 'idRejected', message }), [])

  return { state, startCall, endCall, markIdEdited, rejectId }
}
