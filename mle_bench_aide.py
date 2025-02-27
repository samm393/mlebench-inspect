"""Convenience function for CLI usage of AIDE solver"""

import logging
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.scorer import Scorer
from aide.solver import aide_solver
from aide.utils import AideAgentType
from mle_bench import mle_bench

logger = logging.getLogger(__name__)

@task
def mle_bench_aide(
    split: Path | str = "spaceship-titanic.txt",
    scorer: Scorer | list[Scorer] | None = None,
    instructions: str | None = None,
    epochs: int = 1,
    docker_image_name: str | None = None,
    force_rebuild: bool = False,
    data_dir: Path | str | None = None,
    timeout: int | None = 60,
    aide_agent: AideAgentType = "aide"
) -> Task:
    return mle_bench(
        split=split,
        solver=aide_solver(timeout=timeout, aide_agent=aide_agent),
        scorer=scorer,
        instructions=instructions,
        epochs=epochs,
        docker_image_name=docker_image_name,
        force_rebuild=force_rebuild,
        data_dir=data_dir
    )