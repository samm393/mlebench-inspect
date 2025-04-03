from inspect_ai import eval
from mlebench_inspect import mle_bench
import numpy as np
import os
from multiprocessing import Pool
import sys

# task_name = "low.txt"
model_name = "claude-3-7-sonnet-20250219"
provider = "anthropic"
# model_name = "gpt-4o-mini"
# provider = "openai"
prompt_name = "version16"

with open(f"splits/{sys.argv[1]}") as f:
    task_names = f.readlines()
task_names = [x.strip() for x in task_names]


def eval_task(task_name):
    eval(mle_bench,
         model=f"{provider}/{model_name}",
         log_dir=f"trajectories_per_tasks/{task_name}/trajectories/{model_name}/best_performance/prompt/{prompt_name}",
         task_args={
             'max_messages': 100,
             'split': task_name,
             'remove_start_of_instructions': False,
             'system_prompt_name': prompt_name,
             'num_runs_per_sample': 5,
             'timeout': 18000,
         })


for task_name in task_names:
    eval_task(task_name)
# with Pool(2) as p:
#     result = p.map(
#         eval_task, task_names)
