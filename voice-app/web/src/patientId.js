const MAX_PATIENT_ID_LENGTH = 10

export function keepOnlyDigits(text) {
  return text.replace(/\D/g, '').slice(0, MAX_PATIENT_ID_LENGTH)
}

export function findPatientIdProblem(patientId) {
  const trimmed = patientId.trim()
  if (!trimmed) return 'Enter a patient ID.'
  if (!/^\d+$/.test(trimmed)) return 'Patient ID uses digits only.'
  if (trimmed.length > MAX_PATIENT_ID_LENGTH) return 'Patient ID is too long.'
  return null
}
