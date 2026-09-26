import { useEffect, useState } from 'react'
import { CallPhase } from './callMachine.js'
import { findPatientIdProblem, keepOnlyDigits } from './patientId.js'
import { useVoiceCall } from './useVoiceCall.js'

const BUTTON_LABELS = {
  [CallPhase.IDLE]: 'Start call',
  [CallPhase.CHECKING]: 'Checking…',
  [CallPhase.CONNECTING]: 'Connecting…',
  [CallPhase.IN_CALL]: 'End call',
  [CallPhase.ENDING]: 'Ending…',
}

const STATUS_LABELS = {
  [CallPhase.IDLE]: 'Ready',
  [CallPhase.CHECKING]: 'Looking up patient',
  [CallPhase.CONNECTING]: 'Connecting to agent',
  [CallPhase.ENDING]: 'Ending call',
}

function formatElapsed(totalSeconds) {
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, '0')
  const seconds = String(totalSeconds % 60).padStart(2, '0')
  return `${minutes}:${seconds}`
}

function useElapsedSeconds(isRunning) {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    if (!isRunning) return undefined
    const interval = setInterval(() => setElapsed((value) => value + 1), 1000)
    return () => {
      clearInterval(interval)
      setElapsed(0)
    }
  }, [isRunning])
  return elapsed
}

function MicrophoneBadge() {
  return (
    <div className="badge" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <rect x="9" y="3" width="6" height="11" rx="3" />
        <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
      </svg>
    </div>
  )
}

function Transcript({ lines, notice, patientName }) {
  if (notice) return <p className="notice" role="status">{notice}</p>
  if (lines.length === 0) {
    return <p className="placeholder">{patientName ? `Ask about ${patientName}.` : 'Transcript appears here during the call.'}</p>
  }
  return (
    <ol className="transcript" aria-live="polite">
      {lines.map((line) => (
        <li key={line.id} className={line.role === 'assistant' ? 'agent' : 'caller'}>
          <span className="speaker">{line.role === 'assistant' ? 'Agent' : 'You'}</span>
          {line.text}
        </li>
      ))}
    </ol>
  )
}

export default function App() {
  const [patientId, setPatientId] = useState('')
  const { state, isAudioBlocked, startCall, endCall, resumeAgentAudio, markIdEdited, rejectId } = useVoiceCall()
  const isInCall = state.phase === CallPhase.IN_CALL
  const isBusy = state.phase !== CallPhase.IDLE && !isInCall
  const elapsed = useElapsedSeconds(isInCall)

  function handleIdChange(event) {
    setPatientId(keepOnlyDigits(event.target.value))
    markIdEdited()
  }

  function handleSubmit(event) {
    event.preventDefault()
    if (isInCall) {
      endCall()
      return
    }
    if (isBusy) return
    const problem = findPatientIdProblem(patientId)
    if (problem) {
      rejectId(problem)
      return
    }
    startCall(patientId.trim())
  }

  return (
    <main className="page">
      <form className="card" onSubmit={handleSubmit} noValidate>
        <header className="card-header">
          <MicrophoneBadge />
          <div>
            <h1>Patient voice assistant</h1>
            <p className="subtitle">Ask about demographics</p>
          </div>
        </header>

        <label htmlFor="patient-id">Patient ID</label>
        <input
          id="patient-id"
          inputMode="numeric"
          autoComplete="off"
          placeholder="298724"
          value={patientId}
          onChange={handleIdChange}
          readOnly={state.phase !== CallPhase.IDLE}
          aria-invalid={Boolean(state.fieldError)}
          aria-describedby="patient-id-error"
        />
        <p id="patient-id-error" className="field-error" role="alert">{state.fieldError ?? ''}</p>

        <button type="submit" className={isInCall ? 'call-button end' : 'call-button'} aria-busy={isBusy}>
          {BUTTON_LABELS[state.phase]}
        </button>

        {isInCall && isAudioBlocked && (
          <button type="button" className="audio-button" onClick={resumeAgentAudio}>
            Tap to hear the assistant
          </button>
        )}

        <section className="call-panel" aria-label="Call transcript">
          <Transcript lines={state.transcript} notice={state.notice} patientName={state.patientName} />
          <p className={`status ${isInCall ? 'live' : ''}`}>
            <span className="dot" />
            {isInCall ? `Listening · ${formatElapsed(elapsed)}` : STATUS_LABELS[state.phase]}
          </p>
        </section>
      </form>
    </main>
  )
}
