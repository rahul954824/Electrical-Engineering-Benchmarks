FROM python:3.11-slim

RUN pip install --no-cache-dir \
    numpy==1.26.4 \
    scipy==1.11.4 \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

# Runtime of the submitted program (SPEC.md section 4): the same Python 3.11 with NumPy 1.26.4 and
# SciPy 1.11.4 and no other package; `python` on the program's PATH resolves to it.
RUN python -m venv --without-pip /opt/program-python \
    && pip install --no-cache-dir --no-deps --target /opt/program-python/lib/python3.11/site-packages \
       numpy==1.26.4 scipy==1.11.4 \
    && rm -rf /opt/program-python/lib/python3.11/site-packages/bin

# Parent directory of every artifact of task.toml (/root/results/tool.py, /root/results/example_report.json).
RUN mkdir -p /root/results
RUN useradd --create-home --uid 10001 runner && \
    mkdir -p /logs/verifier /sandbox && \
    chmod 755 /sandbox

COPY . /tests/
RUN chmod -R 700 /tests
WORKDIR /tests
