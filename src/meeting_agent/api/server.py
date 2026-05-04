from __future__ import annotations


def create_app():
    """Optional FastAPI app factory.

    Install optional dependency: `pip install .[api]`.
    """
    try:
        from fastapi import FastAPI
    except ImportError as exc:
        raise RuntimeError("FastAPI is not installed. Run `pip install .[api]`.") from exc

    from meeting_agent.core.schemas import minutes_from_dict, transcript_from_dict, to_dict
    from meeting_agent.intelligence.rule_minutes import RuleBasedMinutesGenerator
    from meeting_agent.intelligence.verifier import MinutesVerifier

    app = FastAPI(title="AI Meeting Agent Community API", version="0.1.0")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/minutes")
    def generate_minutes(payload: dict):
        transcript = transcript_from_dict(payload["transcript"])
        minutes = RuleBasedMinutesGenerator().generate(transcript)
        report = MinutesVerifier().verify(transcript, minutes)
        return {"minutes": to_dict(minutes), "verification": to_dict(report)}

    return app
