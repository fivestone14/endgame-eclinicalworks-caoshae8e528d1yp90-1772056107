# Voice agent frontend: plan

## Goal
You type a patient ID, press a button, and talk to a voice agent that answers questions about that patient's demographics.

## What's decided so far
- **Branch:** `frontend` (already created). When the work is done: push it, then open a pull request to `main`.
- **Frontend:** React (Vite).
- **Voice:** LiveKit. The browser joins a LiveKit room, and a Python LiveKit agent (`server/agent.py`) answers. Models run on LiveKit Inference, with Gemini 2.5 Flash Lite as the LLM.
- **Backend:** a small Python Flask server on port 5000. It serves the React app, holds the secret keys, checks the patient, and issues LiveKit call tokens.
- **Hosting:** localhost. The agent connects out to LiveKit Cloud, so no tunnel is needed.
- **Data:** the backend calls the Integuru `ecw_demographics` API. Only the `read` action is allowed, so nothing in the medical records system can change.
- **Design:** mockup A (centered card): header, patient ID box, one Start call button that becomes End call, transcript, and status line.
- **Code style:** function names that explain themselves, and no comments. A review agent checks this after the build.

## How it works
1. You enter a patient ID and press **Start call**.
2. The backend checks that the patient exists before the call starts.
3. The server returns a LiveKit token for a private room. The token sends the agent with only the patient ID attached.
4. The agent loads the record, and its no-argument tool returns only the demographic fields.
5. The agent answers out loud, and the page shows the live transcript.

## Option A details to add in the build
- The button shows "Checking…" and then "Connecting…" while waiting, becomes **End call** during the call, and goes back to **Start call** when idle.
- Pressing Enter in the ID box starts the call. On phones the box opens the number keypad.
- The ID box has a proper label, and errors are read aloud by screen readers.
- Only one blue (accent) button on screen; flat, light style.

## Validation and error handling
The rule: the page never shows a broken or half-finished state. Every failure turns into a clear message and the page goes back to a usable screen.

**Patient ID box**
- Spaces are trimmed and only digits are allowed. Anything else is blocked as you type.
- If the box is empty or badly formatted when you press Start, a short error appears under the box and no call starts.
- The error clears as soon as you edit the ID.

**Patient check (before the call)**
- Patient not found → "No patient with that ID." The call doesn't start.
- API slow (over 20 seconds per try) or down → retry once, then "Couldn't reach patient records. Try again."
- Bad API key or server problem → a friendly message on the page. The details go to the server log only.

**Voice call**
- Microphone access blocked → tell the user how to allow it, and go back to the start screen.
- The call fails to start, or drops partway through → "Call ended unexpectedly." The page resets cleanly.
- The LiveKit keys are missing → the start button shows a setup message instead of failing silently.
- The agent doesn't join within 20 seconds → "The assistant isn't available. Try again."
- The browser blocks the agent's audio → a "Tap to hear the assistant" button appears.

**Agent (backend)**
- Only the server can start a call for a patient: the signed LiveKit token carries the patient ID, and nothing else.
- The agent's tool takes no arguments, so it can't be asked about a different patient.
- If the records lookup fails or runs slow, the agent says "I couldn't get that record right now" instead of going quiet.

**Page state**
- The page is always in exactly one of these states: idle, checking, connecting, in call, ending, or error. Buttons and labels follow from that state, so mixed states can't happen.
- Missing fields show "—", never "undefined" or blank.
- A top-level error boundary catches any crash and shows a fallback card with a **Reset** button.

## Privacy and secrets
- API keys live in `.env`, which is never committed. A `.env.example` file shows which keys are needed.
- Only demographic fields are sent to the agent: name, DOB, sex, contact details, address, language, race, ethnicity, and primary care provider. The SSN and billing data are never sent.

## Needed from you
- Pick a design: A or B.
- An Integuru API key (from the interviewer).
- A LiveKit account: public key, private key, and an assistant (I can create the assistant through the API).
