# Patient voice assistant

Type a patient ID, press **Start call**, and ask a LiveKit voice agent about that patient's demographics.

- `web/`: React (Vite) frontend using `livekit-client`
- `server/app.py`: Flask on port 5000. It serves the built page, checks the patient through Integuru, and hands the browser a LiveKit call token.
- `server/agent.py`: the LiveKit voice agent. It joins the call, loads the patient's record, and answers questions about it.

## How a call works

1. The page sends the patient ID to `/api/patients/verify`.
2. The server looks the patient up (Integuru `read` action). If found, it creates a private LiveKit room and returns a token. The token asks LiveKit to send the `patient-demographics` agent, with only the patient ID attached.
3. The page joins the room with the microphone on.
4. The agent joins, loads the record, and answers using a tool that returns whitelisted demographic fields only.

The agent connects out to LiveKit Cloud, so no webhook or tunnel is needed.

## Models

Speech-to-text, the LLM, and text-to-speech run on LiveKit Inference, billed through your LiveKit Cloud project. No other provider keys are needed. The defaults are fast, low-cost models, and you can change them in `.env`:

- `LIVEKIT_LLM_MODEL=google/gemini-2.5-flash-lite`
- `LIVEKIT_STT_MODEL=deepgram/nova-3`
- `LIVEKIT_TTS_MODEL=cartesia/sonic-3`

## Setup

Requires Python 3.12 and Node 20+.

```bash
cp .env.example .env
```

Fill in `INTEGURU_API_KEY`, `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` (from your LiveKit Cloud project settings).

```bash
cd server && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
cd web && npm install && npm run build
```

## Run

Use two terminals:

```bash
cd server && .venv/bin/python app.py
```

```bash
cd server && .venv/bin/python agent.py dev
```

Open http://localhost:5000 in Chrome or Safari and allow the microphone.

## Tests

```bash
cd server && .venv/bin/pytest -q
```

## Safety

- Only the `read` action is ever called, so patient records can't change.
- The call token carries only the patient ID. It never carries the name or any record data, and each call gets its own room.
- The agent's tool takes no arguments, so it can only answer about the patient on this call.
- The agent only receives name, DOB, sex, phone, address, marital status, race, ethnicity, language, and PCP. The SSN, insurance, and billing data are never sent.
