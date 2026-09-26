# Voice agent frontend: plan

## Goal
You type a patient ID, press a button, and talk to a voice agent that answers questions about that patient's demographics.

## What's decided so far
- **Branch:** `frontend` (already created). When the work is done: push it, then open a pull request to `main`.
- **Frontend:** React (Vite).
- **Voice:** Vapi, using its web kit in the browser.
- **Backend:** a small Python Flask server on port 5000. It serves the React app, holds the secret keys, and receives Vapi's webhook.
- **Hosting:** Cloudflare Tunnel, which gives Vapi a public URL to call.
- **Data:** the backend calls the Integuru `ecw_demographics` API. Only the `read` action is allowed, so nothing in the medical records system can change.
- **Design:** mockup A (centered card): header, patient ID box, one Start call button that becomes End call, transcript, and status line.
- **Code style:** function names that explain themselves, and no comments. A review agent checks this after the build.

## How it works
1. You enter a patient ID and press **Start call**.
2. The backend checks that the patient exists before the call starts.
3. The browser starts the Vapi call and passes the patient ID along.
4. When you ask a question, Vapi calls our webhook. The webhook fetches the record and returns only the demographic fields.
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
- The Vapi key is missing → the start button shows a setup message instead of failing silently.

**Webhook (backend)**
- Rejects any request that doesn't carry our shared secret.
- Checks that the request has the expected shape. Bad input gets a safe reply; the webhook never crashes.
- If the records lookup fails, the agent says "I couldn't get that record right now" instead of going quiet.

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
- A Vapi account: public key, private key, and an assistant (I can create the assistant through the API).
