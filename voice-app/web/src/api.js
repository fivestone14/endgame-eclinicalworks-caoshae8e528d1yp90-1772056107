const VERIFY_TIMEOUT_MS = 45000
const CONFIG_TIMEOUT_MS = 8000
const RECORDS_UNREACHABLE = "Couldn't reach patient records. Try again."

async function fetchJsonWithTimeout(url, options, timeoutMs) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(url, { ...options, signal: controller.signal })
    const body = await response.json().catch(() => ({}))
    return { ok: response.ok, body }
  } finally {
    clearTimeout(timer)
  }
}

export async function fetchVoiceConfig() {
  try {
    const { ok, body } = await fetchJsonWithTimeout('/api/config', {}, CONFIG_TIMEOUT_MS)
    return { voiceReady: ok && body.voiceReady === true }
  } catch (error) {
    console.error('Could not load voice config', error)
    return { voiceReady: false }
  }
}

export async function verifyPatientAndOpenCall(patientId) {
  try {
    const { ok, body } = await fetchJsonWithTimeout(
      '/api/patients/verify',
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ patientId }) },
      VERIFY_TIMEOUT_MS,
    )
    if (ok && body.status === 'found' && body.serverUrl && body.participantToken) {
      return {
        found: true,
        displayName: body.displayName || 'this patient',
        serverUrl: body.serverUrl,
        participantToken: body.participantToken,
      }
    }
    return { found: false, message: body.message || RECORDS_UNREACHABLE }
  } catch (error) {
    console.error('Patient check failed', error)
    return { found: false, message: RECORDS_UNREACHABLE }
  }
}
