"""Load the bundled, labeled AI action safety benchmark."""
import json
from pathlib import Path
from typing import Any, Dict, List
from app.models.schemas import BenchmarkAction

BENCHMARK_ACTIONS: List[Dict[str, Any]] = json.loads(
    Path(__file__).with_name("benchmark.json").read_text(encoding="utf-8")
)

def get_benchmark_dataset() -> List[BenchmarkAction]:
    return [BenchmarkAction(**item) for item in BENCHMARK_ACTIONS]
