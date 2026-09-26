import { MediaDeviceFailure, Room, RoomEvent, Track } from 'livekit-client'
import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import { fetchVoiceConfig, verifyPatientAndOpenCall } from './api.js'
import { CallPhase, callReducer, initialCallState } from './callMachine.js'

const AGENT_JOIN_TIMEOUT_MS = 20000
const END_FALLBACK_MS = 3000
const TRANSCRIPTION_TOPIC = 'lk.transcription'
const VOICE_NOT_SET_UP = "Voice calls aren't set up yet. Add the LiveKit keys and restart the server."
const MIC_BLOCKED = 'Microphone access is blocked. Allow it in your browser settings, then try again.'
const MIC_UNSUPPORTED = 'This browser can’t use the microphone here. Open the page over https or on localhost.'
const CONNECT_FAILED = "Couldn't connect to the call. Try again."
const AGENT_UNAVAILABLE = "The assistant isn't available. Try again."

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

function describeMediaFailure(error) {
  const failure = MediaDeviceFailure.getFailure(error)
  return failure === MediaDeviceFailure.PermissionDenied ? MIC_BLOCKED : CONNECT_FAILED
}

function findAgentParticipant(room) {
  return [...room.remoteParticipants.values()].find((participant) => participant.isAgent)
}

export function useVoiceCall() {
  const [state, dispatch] = useReducer(callReducer, initialCallState)
  const [isAudioBlocked, setIsAudioBlocked] = useState(false)
  const phaseRef = useRef(state.phase)
  const configRef = useRef(null)
  const roomRef = useRef(null)
  const agentJoinTimerRef = useRef(null)
  const audioElementsRef = useRef([])

  phaseRef.current = state.phase

  const clearAgentJoinTimer = useCallback(() => {
    clearTimeout(agentJoinTimerRef.current)
    agentJoinTimerRef.current = null
  }, [])

  const removeAgentAudio = useCallback(() => {
    audioElementsRef.current.forEach((element) => element.remove())
    audioElementsRef.current = []
  }, [])

  const leaveRoom = useCallback(() => {
    clearAgentJoinTimer()
    const room = roomRef.current
    roomRef.current = null
    setIsAudioBlocked(false)
    removeAgentAudio()
    room?.disconnect().catch((error) => console.error('Leaving the call failed', error))
  }, [clearAgentJoinTimer, removeAgentAudio])

  const markAgentJoined = useCallback(() => {
    clearAgentJoinTimer()
    dispatch({ type: 'callStarted' })
  }, [clearAgentJoinTimer])

  const listenToRoom = useCallback(
    (room) => {
      room.on(RoomEvent.ParticipantConnected, (participant) => {
        if (participant.isAgent) markAgentJoined()
      })
      room.on(RoomEvent.ParticipantDisconnected, (participant) => {
        if (participant.isAgent && roomRef.current === room) {
          leaveRoom()
          dispatch({ type: 'callEnded' })
        }
      })
      room.on(RoomEvent.Disconnected, () => {
        if (roomRef.current === room) leaveRoom()
        dispatch({ type: 'callEnded' })
      })
      room.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind !== Track.Kind.Audio) return
        const element = track.attach()
        document.body.appendChild(element)
        audioElementsRef.current.push(element)
      })
      room.on(RoomEvent.AudioPlaybackStatusChanged, () => setIsAudioBlocked(!room.canPlaybackAudio))
      room.on(RoomEvent.MediaDevicesError, (error) => {
        console.error('Media device error', error)
        leaveRoom()
        dispatch({ type: 'callFailed', message: describeMediaFailure(error) })
      })
      room.registerTextStreamHandler(TRANSCRIPTION_TOPIC, async (reader, participantInfo) => {
        const isFinal = reader.info.attributes?.['lk.transcription_final'] !== 'false'
        const text = (await reader.readAll()).trim()
        if (!isFinal || !text) return
        const role = participantInfo.identity === room.localParticipant.identity ? 'user' : 'assistant'
        dispatch({ type: 'transcriptReceived', role, text })
      })
    },
    [leaveRoom, markAgentJoined],
  )

  useEffect(() => {
    fetchVoiceConfig().then((config) => {
      configRef.current = config
    })
    return () => leaveRoom()
  }, [leaveRoom])

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
      const call = await verifyPatientAndOpenCall(patientId)
      if (!call.found) {
        dispatch({ type: 'patientRejected', message: call.message })
        return
      }
      dispatch({ type: 'patientVerified', displayName: call.displayName })

      const microphoneProblem = await findMicrophoneProblem()
      if (microphoneProblem) {
        dispatch({ type: 'callFailed', message: microphoneProblem })
        return
      }
      if (phaseRef.current !== CallPhase.CONNECTING) return

      const room = new Room({ adaptiveStream: true, dynacast: true })
      roomRef.current = room
      listenToRoom(room)
      try {
        await room.connect(call.serverUrl, call.participantToken)
        if (roomRef.current !== room) return
        await room.localParticipant.setMicrophoneEnabled(true)
        setIsAudioBlocked(!room.canPlaybackAudio)
        if (findAgentParticipant(room)) {
          markAgentJoined()
          return
        }
        agentJoinTimerRef.current = setTimeout(() => {
          leaveRoom()
          dispatch({ type: 'callFailed', message: AGENT_UNAVAILABLE })
        }, AGENT_JOIN_TIMEOUT_MS)
      } catch (error) {
        console.error('Joining the call failed', error)
        leaveRoom()
        dispatch({ type: 'callFailed', message: describeMediaFailure(error) })
      }
    },
    [leaveRoom, listenToRoom, markAgentJoined],
  )

  const endCall = useCallback(() => {
    if (phaseRef.current !== CallPhase.IN_CALL && phaseRef.current !== CallPhase.CONNECTING) return
    dispatch({ type: 'endRequested' })
    leaveRoom()
    setTimeout(() => {
      if (phaseRef.current === CallPhase.ENDING) dispatch({ type: 'callEnded' })
    }, END_FALLBACK_MS)
  }, [leaveRoom])

  const resumeAgentAudio = useCallback(() => {
    roomRef.current
      ?.startAudio()
      .then(() => setIsAudioBlocked(false))
      .catch((error) => console.error('Starting audio failed', error))
  }, [])

  const markIdEdited = useCallback(() => dispatch({ type: 'idEdited' }), [])
  const rejectId = useCallback((message) => dispatch({ type: 'idRejected', message }), [])

  return { state, isAudioBlocked, startCall, endCall, resumeAgentAudio, markIdEdited, rejectId }
}
