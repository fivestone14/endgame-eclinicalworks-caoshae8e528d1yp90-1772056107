from __future__ import annotations

import logging
from typing import Optional

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from demographics import build_display_name, extract_shareable_demographics
from integuru_client import InteguruClient, LookupOutcome
from settings import Settings, load_settings
from vapi_webhook import build_tool_call_results, clean_patient_id, is_request_from_vapi
from verified_patients import VerifiedPatientCache

logger = logging.getLogger(__name__)

FAILED_LOOKUP_RESPONSES = {
    LookupOutcome.NOT_FOUND: (404, "No patient with that ID."),
    LookupOutcome.UNAVAILABLE: (503, "Couldn't reach patient records. Try again."),
    LookupOutcome.AUTH_FAILED: (503, "Patient records aren't available right now. Try again later."),
}


def create_app(settings: Optional[Settings] = None, integuru: Optional[InteguruClient] = None) -> Flask:
    settings = settings or load_settings()
    integuru = integuru or InteguruClient(settings)
    verified_patients = VerifiedPatientCache()
    app = Flask(__name__, static_folder=None)

    @app.get("/api/config")
    def read_client_config():
        return jsonify(
            voiceReady=settings.is_voice_configured,
            publicKey=settings.vapi_public_key if settings.is_voice_configured else "",
            assistantId=settings.vapi_assistant_id if settings.is_voice_configured else "",
        )

    @app.post("/api/patients/verify")
    def verify_patient():
        body = request.get_json(silent=True)
        patient_id = clean_patient_id(body.get("patientId")) if isinstance(body, dict) else None
        if patient_id is None:
            return jsonify(status="invalid", message="Patient ID uses digits only."), 400

        lookup = integuru.read_patient(patient_id)
        if lookup.outcome is not LookupOutcome.FOUND:
            http_status, message = FAILED_LOOKUP_RESPONSES[lookup.outcome]
            return jsonify(status=lookup.outcome.value, message=message), http_status

        demographics = extract_shareable_demographics(lookup.record)
        verified_patients.remember(patient_id, demographics)
        return jsonify(status="found", patientId=patient_id, displayName=build_display_name(demographics))

    @app.post("/api/vapi/webhook")
    def receive_vapi_webhook():
        received_secret = request.headers.get("X-Vapi-Secret")
        if not is_request_from_vapi(received_secret, settings.vapi_webhook_secret):
            logger.warning("Rejected webhook: secret header %s", "missing" if not received_secret else "did not match")
            return jsonify(error="unauthorized"), 401
        tool_call_results = build_tool_call_results(request.get_json(silent=True), verified_patients)
        return jsonify(tool_call_results or {})

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def serve_web_app(path: str):
        requested_file = settings.web_build_dir / path
        if path and requested_file.is_file():
            return send_from_directory(settings.web_build_dir, path)
        if (settings.web_build_dir / "index.html").is_file():
            return send_from_directory(settings.web_build_dir, "index.html")
        return "Web app isn't built yet. Run `npm run build` in voice-app/web.", 503

    @app.errorhandler(Exception)
    def respond_with_safe_error(error: Exception):
        if isinstance(error, HTTPException):
            return jsonify(message=error.description), error.code
        logger.exception("Unhandled server error")
        return jsonify(message="Something went wrong. Try again."), 500

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    current_settings = load_settings()
    create_app(current_settings).run(host="127.0.0.1", port=current_settings.port)
