# README

## Setup

1. Create a Kaggle account and download the API token.
2. Place the downloaded JSON file in `~/.kaggle/kaggle.json` (or the location specified by Kaggle).
3. Your Python version must not be newer than what is supported by inspect. Currently that is 3.11. You can create a conda environment with
   ```sh
   conda create --name mlebench-inspect python=3.11
   ```
   then activate it with
   ```sh
   conda activate mlebench-inspect
   ```
4. Install the required dependencies:
   ```sh
   pip install -r requirements.txt
   ```

## Usage

**Note:** The first time running this may take up to half an hour to build the images. You will also have to manually join all the competitions by clicking the late submission button on the kaggle competition page - a prompt will appear in the terminal with a link asking you to do this.

If you need docker desktop running to get access to the docker in the command line start it now.

By default, it runs the `spaceship-titanic` task.
```sh
inspect eval mle_bench.py --model=openai/gpt-4o
```

If you want to run a different set of tasks, use the following command:
```sh
inspect eval mle_bench.py -T split="mini.txt" --model=openai/gpt-4o
```

mini is the set of tasks I showed in the demo - easy and small download size. You can edit this to try out different tasks or use "low.txt" to run the full MLEBench-Lite (but this is a 250GB download)

## AIDE

This builds a new image from the previous one so make sure you have already run the above.

Inside the Inspect log you will just see the INFO: updates from aide. After completion there will be a .html in aide_logs/. Open this in the browser to see all generated code and plans.

Please note that the Inspect model is not used, and AIDE handles api calls itself. You can specify which model you want with the solver argument `aide_agent`.

```python
AideAgentType = Literal[
    "aide",
    "aide/dev",
    "aide/o1-preview",
    "aide/gpt-4-turbo",
    "aide/gpt-4-turbo-dev",
    "aide/gpt-3.5-turbo-0125",
    "aide/gpt-3.5-dev",
    "aide/claude-3-5-sonnet",
    "aide/claude-3-7-sonnet",
    "aide/llama-3.1-405b-instruct",
    "aide/gemini-1.5-pro",
    "aide/obfuscated"
]
```

You will need an `OPENAI_API_KEY` available in your environment (either through `export` or a `.env` file). If you use one of the claude models you will also need an `ANTHROPIC_API_KEY` - note that agent models still need gpt-4o as the feedback model, so both keys are required.


Run with

```sh
inspect eval mle_bench_aide.py --model=mockllm/model
```

or (for example)

```sh
inspect eval mle_bench_aide.py --model=mockllm/model -T split="low.txt" -T timeout=240 -T aide_agent="aide/claude-3-5-sonnet"
```

where timeout is in seconds and per Sample.
