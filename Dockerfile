# Stage 1: init
FROM python:3.13 AS init

# Pass `--build-arg API_URL=http://app.example.com:8000` during build 
ARG API_URL

# Copy local context to `/app` inside container (see .dockerignore)
WORKDIR /app
COPY . .

# Reflex will install bun, nvm, and node to `$HOME/.reflex` (/app/.reflex)
ENV HOME=/app

# Create virtualenv which will be copied into final container
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN python -m venv $VIRTUAL_ENV

# Install app requirements and reflex inside virtualenv
RUN pip install -r requirements.txt
# Install suneditor plugin without pulling old reflex dependency
RUN pip install reflex-suneditor==0.0.11 --no-deps

# Deploy templates and prepare app
RUN reflex init

# Export static copy of frontend to /app/.web/_static (and pre-install frontend packages)
RUN reflex export --frontend-only --no-zip

# Copy static files out of /app to save space in backend image
#RUN mv .web/_static /tmp/_static
#RUN rm -rf .web && mkdir .web
#RUN mv /tmp/_static .web/_static

# Stage 2: copy artifacts into slim image 
FROM python:3.13-slim
ARG API_URL
RUN apt-get update && apt-get install -y curl && apt-get update && apt-get install -y unzip && apt-get update && apt-get install -y libpq-dev
WORKDIR /app
RUN adduser --disabled-password --home /app reflex
COPY --chown=reflex --from=init /app /app
USER reflex
ENV PATH="/app/.venv/bin:$PATH" API_URL=$API_URL

CMD ["sh", "-c", "if [ \"${RUN_MIGRATIONS_ON_START:-1}\" = \"1\" ]; then reflex db migrate; fi && reflex run --env prod"]
