FROM lgax-retrieval-base-01a10600
USER root
COPY requirements.txt /opt/lgax-retrieval-requirements.txt
RUN UV_OFFLINE=0 uv pip install --python /opt/lgax-venv/bin/python --no-cache --index https://download.pytorch.org/whl/cpu --index https://pypi.org/simple --index-strategy unsafe-best-match -r /opt/lgax-retrieval-requirements.txt
USER 1000:1000
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 TOKENIZERS_PARALLELISM=false
