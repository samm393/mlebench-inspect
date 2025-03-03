import json
import logging
from pathlib import Path
from textwrap import dedent

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.scorer import Score, Scorer, Target, accuracy, scorer, stderr
from inspect_ai.solver import Solver, TaskState, basic_agent, system_message
from inspect_ai.util import SandboxEnvironmentSpec, sandbox
from inspect_ai._util.registry import registry_info
from inspect_ai.tool import bash
from mlebench.data import (  # type: ignore
    download_and_prepare_dataset,
    is_dataset_prepared,
)
from mlebench.registry import registry  # type: ignore
from platformdirs import user_cache_dir

from compose_utils import get_compose_file, get_compose_file_aide

FILE_DIR = Path(__file__).parent
DEFAULT_DATA_DIR = Path(user_cache_dir("inspect_mlebench_eval")) / "data"

DEFAULT_IMAGE_NAME = "mlebench-inspect-env"
DEFAULT_AIDE_IMAGE_NAME = "mlebench-inspect-env-aide"


logger = logging.getLogger(__name__)

with open(Path(__file__).parent / "instructions.txt", "r") as f:
    DEFAULT_INSTRUCTIONS = f.read()


@task
def mle_bench(
    split: Path | str = "spaceship-titanic.txt",
    solver: Solver | None = None,
    scorer: Scorer | list[Scorer] | None = None,
    instructions: str | None = None,
    epochs: int = 1,
    docker_image_name: str | None = None,
    force_rebuild: bool = False,
    data_dir: Path | str | None = None,
) -> Task:
    compose_file_fn = get_compose_file

    # select correct compose and image for aide solver
    if solver and isinstance(solver, Solver):
        if registry_info(solver).name == "aide_solver":
            docker_image_name = docker_image_name or DEFAULT_AIDE_IMAGE_NAME
            compose_file_fn = get_compose_file_aide
        

    # If the split is a path, we assume it is a path to a custom split file and leave it as is.
    if Path(split).parent == Path("."):
        split = FILE_DIR / "splits" / split

    with open(split) as f:
        competition_ids = f.read().splitlines()

    new_registry = registry.set_data_dir(data_dir or DEFAULT_DATA_DIR)
    samples = []

    for competition_id in competition_ids:
        competition = new_registry.get_competition(competition_id)
        if not is_dataset_prepared(competition):
            print(f"Preparing competition {competition_id}")
            download_and_prepare_dataset(competition)


        samples.append(
            Sample(
                input=instructions or DEFAULT_INSTRUCTIONS,
                id=competition_id,
                sandbox=SandboxEnvironmentSpec(
                    type="docker",
                    config=compose_file_fn(
                        competition_id=competition_id,
                        data_dir=data_dir or DEFAULT_DATA_DIR,
                        docker_image_name=docker_image_name or DEFAULT_IMAGE_NAME,
                        force_rebuild=force_rebuild,
                    ),
                ),
            )
        )

    return Task(
        dataset=MemoryDataset(samples=samples),
        solver=solver or default_solver(),
        epochs=epochs,
        scorer=scorer or mle_bench_scorer(),
    )


@scorer(
    metrics={
        "valid_submission": [accuracy(), stderr()],
        "above_median": [accuracy(), stderr()],
        "any_medal": [accuracy(), stderr()],
    }
)
def mle_bench_scorer() -> Scorer:
    async def scorer(state: TaskState, target: Target) -> Score:
        grading_script = dedent(f"""
            from pathlib import Path
            import json
            from mlebench.grade import grade_csv
            from mlebench.registry import registry
            competition = registry.set_data_dir(Path("/private/data")).get_competition("{state.sample_id}")
            report = grade_csv(Path("/home/submission/submission.csv"), competition)
            print(json.dumps(report.to_dict()))
        """)
        result = await sandbox().exec(["python", "-c", grading_script])

        try:
            report_data = json.loads(result.stdout)
        except json.JSONDecodeError:
            logger.info("Failed to parse grading report")
            report_data = {}

        return Score(
            value={
                "valid_submission": report_data.get("valid_submission", False),
                "above_median": report_data.get("above_median", False),
                "any_medal": report_data.get("any_medal", False),
            },
            explanation=result.stdout,
        )

    return scorer


def default_solver(max_messages: int = 30) -> Solver:
    return basic_agent(
        init=[
            system_message(
                "Please solve the coding task below. Once you are done, use your submit tool."
            )
        ],
        tools=[bash(timeout=180, user="nonroot")],
        max_messages=max_messages,
    )
