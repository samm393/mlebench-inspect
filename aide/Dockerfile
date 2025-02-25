FROM mlebench-inspect-env

RUN conda run -n agent pip install git+https://github.com/thesofakillers/aideml@v6.3.3 && \
    conda run -n agent pip install --upgrade openai && \
    conda clean -afy

RUN mkdir /home/agent