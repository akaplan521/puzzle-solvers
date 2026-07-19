# Start from an official image: Debian Linux with Python 3.12 preinstalled.
# "slim" = minimal variant, smaller download.
FROM python:3.12-slim

# HF Spaces runs containers as user id 1000; create that user and switch
# to it so file permissions line up.
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# All following commands run in /app inside the container.
WORKDIR /app

# Copy in exactly what the app needs — dependency manifest and source.
# (Tests, fixtures, scripts, .venv stay out; see .dockerignore.)
COPY --chown=user pyproject.toml ./
COPY --chown=user src ./src

# Install the project + dependencies INSIDE the container.
# This is the whole point of Docker: the box carries its own environment,
# so "works on my machine" becomes "works anywhere the box runs".
RUN pip install --no-cache-dir --user .

# Documentation of which port the app listens on (HF expects 7860).
EXPOSE 7860

# What runs when the container starts. --host 0.0.0.0 means "accept
# connections from outside the container" — inside-localhost-only would
# make the app unreachable, a classic first-deploy bug.
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "7860"]