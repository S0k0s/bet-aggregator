from app.models.schemas import SourcePick
import os, json

try:
    from openai import AsyncOpenAI
    _client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


EXTRACTION_PROMPT = """
You are a football betting data extractor. Read the article snippet and extract every clear prediction.

Return ONLY a JSON array. Each element must have:
- home_team: string
- away_team: string
- market: one of [1X2, Over/Under 2.5, Over/Under 1.5, BTTS, Double Chance, Correct Score]
- pick: the specific selection (e.g. "1", "X", "2", "Over 2.5", "Yes", "1X")
- confidence_text: short string if author expresses confidence
- reason_summary: 1-sentence reason from the article
- quoted_odds: float or null

If no clear prediction exists, return [].
"""


async def extract_picks_from_text(text: str, source_name: str, source_url: str) -> list[SourcePick]:
    if not OPENAI_AVAILABLE or not os.getenv("OPENAI_API_KEY"):
        return []
    try:
        resp = await _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": text[:4000]}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        items = data if isinstance(data, list) else data.get("predictions", [])
        return [
            SourcePick(
                source_name=source_name,
                source_url=source_url,
                market=item.get("market", "unknown"),
                pick=item.get("pick", ""),
                quoted_odds=item.get("quoted_odds"),
                confidence_text=item.get("confidence_text"),
                reason_summary=item.get("reason_summary"),
            )
            for item in items
            if item.get("pick")
        ]
    except Exception:
        return []
