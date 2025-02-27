import yaml # type: ignore
import logging
import asyncio
from datetime import datetime
from pathlib import Path

from inspect_ai.solver import Solver, TaskState, solver, Generate
from inspect_ai.util import sandbox
from inspect_ai.log import transcript

from .utils import parse_env_var_values, stream_logs, AideAgentType

logger = logging.getLogger(__name__)

@solver
def aide_solver(timeout: int | None = 60, aide_agent: AideAgentType = "aide") -> Solver:
    print(timeout)
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        log_task = asyncio.create_task(stream_logs("/home/output.log"))

        try:
            with open(Path(__file__).parent / "config.yaml", "r") as f:
                cfg = yaml.safe_load(f)

            kwargs = parse_env_var_values(cfg[aide_agent]["kwargs"])
            env_vars = parse_env_var_values(cfg[aide_agent]["env_vars"])

            # overwrite of TIME_LIMIT_SECS for convenience, default is 24h
            if timeout is not None:
                env_vars["TIME_LIMIT_SECS"] = timeout

            # export all env vars inside sandbox
            env_cmd = "export " + " ".join([f"{key}={value}" for key, value in env_vars.items()]) + ";"
            
            # command to run agent
            cmd = ["bash /home/agent/start.sh"]
            cmd += [f"{key}={value}" for key, value in kwargs.items()]

            await(sandbox().exec(["bash", "--login", "-c", f"{' '.join([env_cmd, *cmd])}"], user="nonroot"))

        finally:
            await asyncio.sleep(3) # wait for the final logs to be written
            log_task.cancel()
            try:
                await log_task
            except asyncio.CancelledError:
                pass

        try:
            tree_plot = await(sandbox().read_file("/home/agent/logs/exp/tree_plot.html"))

            aide_logs_directory = Path("aide_logs")
            aide_logs_directory.mkdir(parents=True, exist_ok=True)

            filename = f"tree_plot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

            with open(aide_logs_directory / filename, "w") as f:
                f.write(tree_plot)

            transcript().info(f"AIDE has terminated successfully. Full logs are available at file://{(aide_logs_directory / filename).resolve()}. Please open in the browser.")
        
        except FileNotFoundError:
            transcript().info(f"AIDE has terminated unsuccessfully. No logs were found. It is possible that {timeout=} is too small for any logs to be generated.")

        return state
    return solve
