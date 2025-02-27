FROM mlebench-inspect-env

ENV AGENT_DIR=/home/agent
ENV SUBMISSION_DIR=/home/submission
ENV CONDA_ENV_NAME=agent

RUN conda run -n agent pip install git+https://github.com/thesofakillers/aideml@v6.3.3 && \
    conda run -n agent pip install --upgrade openai && \
    conda clean -afy

RUN mkdir /home/agent

COPY start.sh /home/agent/start.sh
COPY additional_notes.txt /home/agent/additional_notes.txt