FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE.md ./
COPY server.py backtest_config.py backtest_engine.py download_market_archive.py http_utils.py mm.py ./

RUN pip install --no-cache-dir .

ENTRYPOINT ["kalshi-research-mcp"]
