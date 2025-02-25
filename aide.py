
import os
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from textwrap import dedent

import docker  # type: ignore
from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.scorer import Score, Scorer, Target, accuracy, scorer, stderr
from inspect_ai.solver import Solver, TaskState, basic_agent, system_message, solver, Generate
from inspect_ai.tool import bash
from inspect_ai.util import SandboxEnvironmentSpec, sandbox
from inspect_ai.log import transcript
from mlebench.data import (  # type: ignore
    download_and_prepare_dataset,
    is_dataset_prepared,
)
from mlebench.registry import registry  # type: ignore
from platformdirs import user_cache_dir

FILE_DIR = Path(__file__).parent
DEFAULT_DATA_DIR = Path(user_cache_dir("inspect_mlebench_eval")) / "data"
COMPOSE_FILES_DIR = Path(user_cache_dir("inspect_mlebench_eval")) / "compose_files"
DEFAULT_IMAGE_NAME = "mlebench-inspect-env-aide"


logger = logging.getLogger(__name__)

with open(Path(__file__).parent / "instructions.txt", "r") as f:
    DEFAULT_INSTRUCTIONS = f.read()


@task
def mle_bench(
    split: Path | str = "spaceship-titanic.txt",
    solver: Solver | None = None,
    timeout: int = 60,
    scorer: Scorer | list[Scorer] | None = None,
    instructions: str = DEFAULT_INSTRUCTIONS,
    epochs: int = 1,
    docker_image_name: str | None = None,
    force_rebuild: bool = False,
    data_dir: Path | str | None = None,
) -> Task:
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
                input=instructions,
                id=competition_id,
                sandbox=SandboxEnvironmentSpec(
                    type="docker",
                    config=get_compose_file(
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
        solver=solver or aide_solver(timeout=timeout),
        epochs=epochs,
        scorer=scorer or mle_bench_scorer(),
    )

async def wait_for_log_file(log_path, timeout=5):
    """Wait until the log file exists, with a timeout."""
    elapsed = 0
    while elapsed < timeout:
        try:
            log_content = await sandbox().read_file(log_path)
            if log_content is not None:
                return True
        except Exception:
            pass  # Ignore errors and keep waiting
        
        await asyncio.sleep(0.5)
        elapsed += 0.5

    print(f"Warning: Log file {log_path} not found after {timeout} seconds.")
    return False

async def stream_logs(log_path):
    """Continuously fetch and print new logs from the container."""
    if not await wait_for_log_file(log_path):
        return  # Stop if the log file was never found

    last_position = 0

    while True:
        try:
            log_content = await sandbox().read_file(log_path)

            if not log_content or len(log_content) <= last_position:
                await asyncio.sleep(1)
                continue

            new_logs = log_content[last_position:]
            last_position = len(log_content)
            for line in new_logs.split("\n"):
                if line:
                    transcript().info(line)

        except Exception as e:
            print(f"Error reading logs: {e}")
            await asyncio.sleep(2)  # Backoff on errors


@solver
def aide_solver(timeout: int) -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        log_task = asyncio.create_task(stream_logs("/home/output.log"))

        try:
            result = await(sandbox().exec(["bash", "--login", "-c",
                                        dedent(f"""
                                                cd /home/agent
                                                mkdir -p /home/agent/workspaces/exp
                                                ln -s /home/submission /home/agent/workspaces/exp/best_submission
                                                export OPENAI_API_KEY="{os.environ.get('OPENAI_API_KEY')}"
                                                timeout {timeout}s aide data_dir='/home/data' desc_file='/home/data/description.md' exp_name='exp' > /home/output.log 2>&1
                                                """)], user="nonroot"))
        finally:
            await asyncio.sleep(3) # wait for the final logs to be written
            log_task.cancel()
            try:
                await log_task
            except asyncio.CancelledError:
                pass

        tree_plot = await(sandbox().read_file("/home/agent/logs/exp/tree_plot.html"))

        aide_logs_directory = Path("aide_logs")
        aide_logs_directory.mkdir(parents=True, exist_ok=True)

        filename = f"tree_plot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

        with open(aide_logs_directory / filename, "w") as f:
            f.write(tree_plot)

        transcript().info(f"AIDE has terminated successfully. Full logs are available at file://{(aide_logs_directory / filename).resolve()}. Please open in the browser.")

        return state
    return solve

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

def get_compose_file(competition_id: str, data_dir: Path | str, docker_image_name: str, force_rebuild: bool = False) -> str:
    image_compose_file = COMPOSE_FILES_DIR / f"{competition_id}.yaml"
    image_compose_file.parent.mkdir(parents=True, exist_ok=True)

    with image_compose_file.open(mode="w+") as f:
        f.write(dedent(f"""\
            services:
              default:
                image: {docker_image_name}
                platform: linux/amd64
                volumes:
                  - {Path(data_dir) / competition_id / "prepared/public"}:/home/data:ro
                  - {Path(data_dir) / competition_id / "prepared/private"}:/private/data/{competition_id}/prepared/private:ro
                environment:
                  - COMPETITION_ID={competition_id}
                x-local: true
                deploy:
                  resources:
                    limits:
                      cpus: '1'
        """))


        try:
            docker.from_env().images.get(docker_image_name)
            image_exists = True
        except docker.errors.ImageNotFound:
            image_exists = False

        if force_rebuild or not image_exists:
            f.write(f"    build: {Path(__file__).parent / 'aide'}")

    return str(image_compose_file)