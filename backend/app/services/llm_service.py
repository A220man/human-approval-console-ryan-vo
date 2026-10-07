"""Grounded LLM advisory analysis engine."""
import json
import logging
from typing import Any, Dict
import httpx
from app.core.config import settings
from app.models.schemas import AdvisoryResponse
from app.services.risk_engine import RiskEngine

logger = logging.getLogger(__name__)

class LLMService:
    @classmethod
    def _deterministic_offline(cls, action: Dict[str, Any], risk_data: Dict[str, Any]) -> AdvisoryResponse:
        score = risk_data.get("risk_score", 0)
        level = risk_data.get("risk_level", "low").upper()
        reasons = risk_data.get("reasons", [])
        target = action.get("target_resource", "unknown")
        act_type = action.get("action_type", "unknown")

        return AdvisoryResponse(
            action_id=action.get("id", ""), provider="offline-deterministic", model="heuristic-rule-engine-v1",
            is_advisory=True,
            summary=f"[OFFLINE DETERMINISTIC ADVISORY] Action '{action.get('id')}' is classified as {level} risk ({score}/100) based on pattern heuristics.",
            blast_radius_assessment=f"Blast radius impacts target '{target}'. Category: {act_type}. Impact: {risk_data.get('impact_score', 0)}/100, Reversibility: {risk_data.get('reversibility_score', 0)}/100.",
            security_concerns=reasons if reasons else ["No high-severity policy flags triggered."],
            suggested_modifications="Wrap commands in transaction blocks or apply least-privilege resource constraints.",
            offline_deterministic=True
        )

    @classmethod
    async def get_advisory(cls, action: Dict[str, Any]) -> AdvisoryResponse:
        payload = action.get("payload") or {}
        if isinstance(payload, str):
            try: payload = json.loads(payload)
            except Exception: payload = {}

        risk_eval = RiskEngine.analyze(
            action_type=action.get("action_type", ""), target_resource=action.get("target_resource", ""),
            payload=payload, context_metadata=action.get("context_metadata")
        )
        risk_data = risk_eval.model_dump()

        if not settings.llm_api_key:
            return cls._deterministic_offline(action, risk_data)

        prompt = f"Security Policy Advisory:\nAction: {action.get('id')}\nType: {action.get('action_type')}\nTarget: {action.get('target_resource')}\nPayload: {json.dumps(payload)}\nRisk: {risk_data.get('risk_score')}/100 ({risk_data.get('risk_level')})\nConcerns: {', '.join(risk_data.get('reasons', []))}\nRespond with JSON: summary, blast_radius_assessment, security_concerns (list), suggested_modifications."
        timeout = httpx.Timeout(settings.llm_timeout_seconds)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                provider = settings.llm_provider.lower().strip()
                if provider in ("openai-compatible", "ollama"):
                    resp = await client.post(
                        f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                        json={"model": settings.llm_model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2},
                        headers={"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"}
                    )
                    resp.raise_for_status()
                    content = resp.json()["choices"][0]["message"]["content"]
                elif provider == "anthropic":
                    resp = await client.post(
                        f"{settings.llm_base_url.rstrip('/')}/v1/messages",
                        json={"model": settings.llm_model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1000},
                        headers={"x-api-key": settings.llm_api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
                    )
                    resp.raise_for_status()
                    content = resp.json()["content"][0]["text"]
                elif provider == "gemini":
                    resp = await client.post(
                        f"{settings.llm_base_url.rstrip('/')}/models/{settings.llm_model}:generateContent?key={settings.llm_api_key}",
                        json={"contents": [{"parts": [{"text": prompt}]}]},
                        headers={"Content-Type": "application/json"}
                    )
                    resp.raise_for_status()
                    content = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    raise ValueError(f"Unknown provider: {provider}")

                clean = content.strip().replace("```json", "").replace("```", "").strip()
                parsed = json.loads(clean)
                return AdvisoryResponse(
                    action_id=action.get("id", ""), provider=settings.llm_provider, model=settings.llm_model,
                    is_advisory=True, summary=parsed.get("summary", "Analysis generated."),
                    blast_radius_assessment=parsed.get("blast_radius_assessment", "Assessment complete."),
                    security_concerns=parsed.get("security_concerns", []),
                    suggested_modifications=parsed.get("suggested_modifications"), offline_deterministic=False
                )
        except Exception as exc:
            logger.warning(f"Online LLM error: {exc}")
            fallback = cls._deterministic_offline(action, risk_data)
            fallback.summary += f" (Online query note: {type(exc).__name__})"
            return fallback
