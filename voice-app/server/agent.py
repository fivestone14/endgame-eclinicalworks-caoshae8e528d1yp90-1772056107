from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, RunContext, function_tool, inference

from demographics import build_display_name, extract_shareable_demographics
from integuru_client import InteguruClient, LookupOutcome
from patient_ids import clean_patient_id
from settings import Settings, load_settings

logger = logging.getLogger(__name__)

RECORD_WAIT_SECONDS = 45
RECORD_UNAVAILABLE_REPLY = "I couldn't get that record right now. Please end the call and try again."
MISSING_PATIENT_REPLY = "I couldn't tell which patient this call is for. Please end the call and try again."
DEMOGRAPHICS_TOOL_DESCRIPTION = "Get the demographics of the patient on this call."

INSTRUCTIONS = """You are a front-desk voice assistant for a medical clinic, speaking with staff about one patient.
Before answering any question about the patient, call get_patient_demographics.
Only answer questions about the patient's demographics: name, date of birth, sex, contact details, address, marital status, race, ethnicity, language, and primary care provider.
Answer only what was asked, in one or two short spoken sentences. Say dates as spoken words.
If a field is missing, say it isn't on file. Never guess.
If the tool returns an error message, say that message to the caller.
Politely decline anything outside the patient's demographics."""

settings = load_settings()
server = AgentServer()


def read_patient_id_from_metadata(metadata: Optional[str]) -> Optional[str]:
    try:
        parsed = json.loads(metadata or "")
    except ValueError:
        return None
    return clean_patient_id(parsed.get("patientId")) if isinstance(parsed, dict) else None


async def fetch_shareable_demographics(integuru: InteguruClient, patient_id: str) -> Optional[dict]:
    lookup = await asyncio.to_thread(integuru.read_patient, patient_id)
    if lookup.outcome is not LookupOutcome.FOUND:
        logger.warning("Agent lookup for patient %s ended with %s", patient_id, lookup.outcome.value)
        return None
    return extract_shareable_demographics(lookup.record)


async def wait_for_demographics(demographics_task: asyncio.Task, timeout_seconds: float = RECORD_WAIT_SECONDS) -> Optional[dict]:
    try:
        return await asyncio.wait_for(asyncio.shield(demographics_task), timeout_seconds)
    except Exception:
        logger.exception("Patient record wasn't ready in time")
        return None


def describe_demographics_for_agent(demographics: Optional[dict]) -> str:
    if not demographics:
        return RECORD_UNAVAILABLE_REPLY
    return json.dumps({"patient_name": build_display_name(demographics), **demographics})


class PatientDemographicsAgent(Agent):
    def __init__(self, demographics_task: asyncio.Task) -> None:
        super().__init__(instructions=INSTRUCTIONS)
        self._demographics_task = demographics_task

    @function_tool(name="get_patient_demographics", description=DEMOGRAPHICS_TOOL_DESCRIPTION)
    async def get_patient_demographics(self, context: RunContext) -> str:
        return describe_demographics_for_agent(await wait_for_demographics(self._demographics_task))


def build_voice_session(current_settings: Settings) -> AgentSession:
    return AgentSession(
        stt=inference.STT(model=current_settings.stt_model, language="en"),
        llm=inference.LLM(model=current_settings.llm_model),
        tts=inference.TTS(model=current_settings.tts_model),
    )


@server.rtc_session(agent_name=settings.agent_name)
async def run_patient_call(ctx: JobContext) -> None:
    session = build_voice_session(settings)
    patient_id = read_patient_id_from_metadata(ctx.job.metadata)

    if patient_id is None:
        logger.warning("Call started without a valid patient ID in dispatch metadata")
        await session.start(room=ctx.room, agent=Agent(instructions=INSTRUCTIONS))
        await session.say(MISSING_PATIENT_REPLY, allow_interruptions=False).wait_for_playout()
        ctx.shutdown(reason="missing patient id")
        return

    demographics_task = asyncio.create_task(fetch_shareable_demographics(InteguruClient(settings), patient_id))
    await session.start(room=ctx.room, agent=PatientDemographicsAgent(demographics_task))
    await session.generate_reply(instructions="Greet the caller in one short sentence and ask what they'd like to know about the patient.")


if __name__ == "__main__":
    agents.cli.run_app(server)
