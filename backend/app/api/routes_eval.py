"""Evaluation benchmark and metric execution endpoints."""
from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from app.core.auth import get_current_user, require_role, verify_csrf
from app.eval.dataset import get_benchmark_dataset
from app.eval.evaluate_policy import run_evaluation
from app.models.schemas import BenchmarkAction, EvaluationMetrics, UserProfile

router = APIRouter(prefix="/api/eval", tags=["Evaluation"])


@router.get("/benchmark", response_model=List[BenchmarkAction])
def get_benchmark(
    user: UserProfile = Depends(require_role(["viewer", "analyst", "admin"]))
) -> List[BenchmarkAction]:
    """Returns the labeled safety benchmark dataset for AI Agent actions."""
    return get_benchmark_dataset()


@router.post("/run", response_model=EvaluationMetrics)
def execute_benchmark_evaluation(
    user: UserProfile = Depends(require_role(["viewer", "analyst", "admin"])),
    csrf: None = Depends(verify_csrf)
) -> EvaluationMetrics:
    """Executes the risk evaluation engine over the benchmark dataset and returns metrics."""
    return run_evaluation()
