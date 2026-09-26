# Patient voice assistant

Type a patient ID, press **Start call**, and ask a Vapi voice agent about that patient's demographics.

- `web/`: React (Vite) frontend
- `server/`: Flask backend on port 5000. It serves the built frontend, checks the patient, and handles Vapi's tool webhook.

## Setup

```bash
cp .env.example .env
```

Fill in `INTEGURU_API_KEY`, `VAPI_PUBLIC_KEY`, `VAPI_PRIVATE_KEY`, and a long random `VAPI_WEBHOOK_SECRET`.

```bash
cd server && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
cd web && npm install && npm run build
```

## Run

1. Start the server: `cd server && .venv/bin/python app.py`
2. Start the tunnel: `cloudflared tunnel --url http://localhost:5000`
3. Put the tunnel URL in `.env` as `PUBLIC_BASE_URL`.
4. Create or update the Vapi assistant: `cd server && .venv/bin/python sync_vapi_assistant.py`. On the first run, copy the printed ID into `.env` as `VAPI_ASSISTANT_ID`.
5. Restart the server and open the tunnel URL.

Quick tunnel URLs change on every run, so repeat steps 3–5 after restarting the tunnel.

## Tests

```bash
cd server && .venv/bin/pytest -q
```

## Safety

- Only the `read` action is ever called, so patient records can't change.
- The agent only receives name, DOB, sex, phone, address, marital status, race, ethnicity, language, and PCP. The SSN, insurance, and billing data are never sent.
- The webhook only answers for the patient verified when the call started, and it requires the shared secret.
