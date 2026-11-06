# The VoiceMitra API (backend/ + the agent in core/ and domains/), as deployed to the cloud server.
# Built and pushed by .github/workflows/backend.yml; run by deploy/docker-compose.yml. See deploy/README.md.
#
# One process, one worker, on purpose: live calls, escalations and dose/reminder timers live in this
# process's memory, so a second worker or replica would split them.

FROM python:3.12-slim

# Links the image to the repo on ghcr.io, so the deploy can pull it with the workflow's own token.
LABEL org.opencontainers.image.source=https://github.com/Apoorv012/VoiceMitra

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first, so a code-only change reuses this layer.
COPY requirements.lock .
RUN pip install -r requirements.lock

COPY backend ./backend
COPY core ./core
COPY domains ./domains

RUN useradd --create-home --uid 10001 app
USER app

# Which commit this image was built from; shown in the logs at startup by the deploy step.
ARG GIT_SHA=unknown
ENV GIT_SHA=$GIT_SHA

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

# --proxy-headers: requests arrive through the Cloudflare tunnel, which is the only way in (the port is
# bound to the server's localhost in docker-compose.yml).
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
