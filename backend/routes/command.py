"""
POST /command — receives a voice transcript, runs K's agent, returns a spoken reply.
"""
import logging
import re

from fastapi import APIRouter, HTTPException
from backend.models import CommandRequest, CommandResponse

log = logging.getLogger("k.command")
router = APIRouter()

_MAX_TRANSCRIPT_CHARS = 500


# ── Spoken email normaliser ────────────────────────────────────────────────
# Speech recognition transcribes email addresses in natural language, e.g.:
#   "john dot smith at gmail dot com"  →  "john.smith@gmail.com"
#   "j_o_h_n at example dot com"       →  "john@example.com"
# This runs before the agent so Claude always receives a proper address.

_WORD_MAP = {
    "dot":         ".",
    "period":      ".",
    "hyphen":      "-",
    "dash":        "-",
    "underscore":  "_",
    "plus":        "+",
    "at":          "@",
    "at sign":     "@",
    "at the rate": "@",
}

def _strip_markdown(text: str) -> str:
    """Remove markdown so TTS reads naturally without saying asterisk, pound, etc."""
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-*•]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"`{1,3}(.+?)`{1,3}", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    text = re.sub(r"\n{2,}", " ", text)
    text = re.sub(r"\n", " ", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _normalise_spoken_email(text: str) -> str:
    """
    Find patterns like 'X at Y dot Z' and convert them to X@Y.Z.
    Leaves the rest of the transcript unchanged.
    """
    # Build a regex that matches a spoken email token sequence
    # e.g. "john dot smith at gmail dot com"
    # Strategy: look for <word_chars>(space<connector>space<word_chars>)* at <domain>
    spoken_email_re = re.compile(
        r"""
        (?<!\w)                        # not inside a word
        ([\w]+                         # local-part first token
          (?:\s+(?:dot|period|hyphen|dash|underscore|plus)\s+[\w]+)*)   # more local tokens
        \s+(?:at|at\s+sign|at\s+the\s+rate)\s+   # @ separator
        ([\w]+                         # domain first token
          (?:\s+(?:dot|period)\s+[\w]+)+)         # domain.tld (must have at least one dot)
        (?!\w)
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    def replace_match(m: re.Match) -> str:
        local  = m.group(1)
        domain = m.group(2)

        def flatten(part: str) -> str:
            for word, sym in _WORD_MAP.items():
                part = re.sub(rf"\s+{re.escape(word)}\s+", sym, part, flags=re.IGNORECASE)
            return part.strip()

        return f"{flatten(local)}@{flatten(domain)}"

    return spoken_email_re.sub(replace_match, text)


# ── Route ──────────────────────────────────────────────────────────────────

@router.post("/command", response_model=CommandResponse)
async def handle_command(body: CommandRequest) -> CommandResponse:
    transcript = body.transcript.strip()

    if not transcript:
        return CommandResponse(reply="I didn't catch that. Could you say that again?")

    if len(transcript) > _MAX_TRANSCRIPT_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"Transcript too long ({len(transcript)} chars). Max {_MAX_TRANSCRIPT_CHARS}.",
        )

    # Normalise any spoken email addresses before handing off to the agent
    normalised = _normalise_spoken_email(transcript)
    if normalised != transcript:
        log.info("Email normalised: %r → %r", transcript[:80], normalised[:80])

    log.info("Command received: %r", normalised[:80])

    try:
        from backend.agent.agent import run
        reply, action_taken = run(normalised)
        reply = _strip_markdown(reply)
        return CommandResponse(reply=reply, action_taken=action_taken)

    except EnvironmentError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")
