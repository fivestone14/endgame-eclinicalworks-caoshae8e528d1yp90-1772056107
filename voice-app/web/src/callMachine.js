export const CallPhase = Object.freeze({
  IDLE: 'idle',
  CHECKING: 'checking',
  CONNECTING: 'connecting',
  IN_CALL: 'inCall',
  ENDING: 'ending',
})

export const initialCallState = Object.freeze({
  phase: CallPhase.IDLE,
  fieldError: null,
  notice: null,
  transcript: [],
  endedByUser: false,
  patientName: null,
})

const UNEXPECTED_END = 'Call ended unexpectedly. Try again.'

const VOICE_PHASES = [CallPhase.CONNECTING, CallPhase.IN_CALL, CallPhase.ENDING]

function returnToIdle(state, changes) {
  return { ...initialCallState, transcript: state.transcript, patientName: state.patientName, ...changes }
}

export function callReducer(state, action) {
  switch (action.type) {
    case 'idEdited':
      return state.phase === CallPhase.IDLE ? { ...state, fieldError: null } : state

    case 'idRejected':
      return state.phase === CallPhase.IDLE ? { ...state, fieldError: action.message } : state

    case 'voiceUnavailable':
      return state.phase === CallPhase.IDLE ? { ...state, notice: action.message } : state

    case 'startRequested':
      return state.phase === CallPhase.IDLE
        ? { ...initialCallState, phase: CallPhase.CHECKING }
        : state

    case 'patientRejected':
      return state.phase === CallPhase.CHECKING ? returnToIdle(state, { fieldError: action.message }) : state

    case 'patientVerified':
      return state.phase === CallPhase.CHECKING
        ? { ...state, phase: CallPhase.CONNECTING, patientName: action.displayName }
        : state

    case 'callStarted':
      return state.phase === CallPhase.CONNECTING ? { ...state, phase: CallPhase.IN_CALL, transcript: [] } : state

    case 'transcriptReceived':
      return state.phase === CallPhase.IN_CALL
        ? { ...state, transcript: [...state.transcript, { id: state.transcript.length, role: action.role, text: action.text }] }
        : state

    case 'endRequested':
      return state.phase === CallPhase.IN_CALL || state.phase === CallPhase.CONNECTING
        ? { ...state, phase: CallPhase.ENDING, endedByUser: true }
        : state

    case 'callEnded':
    case 'callFailed':
      return VOICE_PHASES.includes(state.phase)
        ? returnToIdle(state, { notice: state.endedByUser ? null : action.message || UNEXPECTED_END })
        : state

    default:
      return state
  }
}
