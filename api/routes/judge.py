"""
Judge Assistant API endpoint.

POST /api/v1/judge/analyze
  Runs the 4-step AI Judge Assistant pipeline:
    1. Define the legal topic from the case description
    2. Search relevant case law (Slov-lex [SK], EC Decisions [EU], CJEU [EU])
    3. Analyse the retrieved case law
    4. Apply the analysis to the specific case facts
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from api.models import (
    JudgeAnalysisRequest,
    JudgeAnalysisResponse,
    TopicDefinition,
    CaseLawSource,
)
from pipeline.judge import run_judge_analysis
from services.language_service import LanguageService

logger = logging.getLogger(__name__)
router = APIRouter()
_lang_service = LanguageService()


@router.post(
    "/judge/analyze",
    response_model=JudgeAnalysisResponse,
    summary="AI Judge Assistant – 4-step legal analysis",
    description=(
        "Submit a case description and receive a structured legal analysis:\n\n"
        "1. **Topic definition** – Legal domain, key issues, applicable jurisdictions\n"
        "2. **Case law search** – Parallel search of Slov-lex (SK), "
        "EC Competition Decisions (EU), and CJEU / EUR-Lex (EU)\n"
        "3. **Case law analysis** – Key principles, legal tests, hierarchy of norms\n"
        "4. **Application to facts** – Systematic application of precedents to the case\n\n"
        "All source citations are labelled [SK] or [EU]. "
        "Supports Slovak (sk), Hungarian (hu), and English (en)."
    ),
    tags=["Judge Assistant"],
)
async def analyze_case(request: JudgeAnalysisRequest):
    """
    Run the full 4-step AI Judge Assistant analysis.

    The pipeline:
    - Calls Claude Sonnet (deep model) for all four steps
    - Searches Slov-lex, EC Decisions, and CJEU in parallel (Step 2)
    - Returns a structured response with topic, sources, analysis, and application
    """
    try:
        # Auto-detect language if not provided
        language = request.language or _lang_service.detect_language(
            request.case_description
        )
        # Normalise to supported languages
        if language not in ("sk", "hu", "en"):
            language = "sk"

        logger.info(
            f"[Judge] /analyze | lang={language} | "
            f"desc_len={len(request.case_description)} chars"
        )

        result = await run_judge_analysis(
            case_description=request.case_description,
            language=language,
            conversation_id=request.conversation_id,
        )

        # Map topic dict to TopicDefinition model
        raw_topic = result["topic"]
        topic = TopicDefinition(
            legal_domain=raw_topic.get("legal_domain", ""),
            legal_issues=raw_topic.get("legal_issues", []),
            jurisdictions=raw_topic.get("jurisdictions", []),
            search_keywords=raw_topic.get("search_keywords", []),
            topic_summary=raw_topic.get("topic_summary", ""),
        )

        # Map flat source list to CaseLawSource models
        sources = [
            CaseLawSource(
                title=s.get("title", ""),
                case_number=s.get("case_number", ""),
                url=s.get("url", ""),
                source=s.get("source", ""),
                jurisdiction=s.get("jurisdiction", ""),
                date=s.get("date", ""),
            )
            for s in result.get("case_law_sources", [])
        ]

        return JudgeAnalysisResponse(
            topic=topic,
            case_law_sources=sources,
            case_law_analysis=result["case_law_analysis"],
            final_analysis=result["final_analysis"],
            language=result["language"],
            steps_completed=result["steps_completed"],
            conversation_id=request.conversation_id,
            timestamp=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.error(f"[Judge] Analysis error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Judge analysis failed: {str(e)}",
        )
