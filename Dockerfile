# The offline-ready image: everything the suite needs, including DuckDB's
# full-text-search extension, baked in at build time. Build it once with
# network, run it forever without.
#
#     docker compose run --rm suite     # the full test suite
#     docker compose run --rm shell     # a shell on your working tree
#
# Python is pinned to the version the recorded numbers were produced with.
# CI additionally runs the declared floor (3.11) outside this image, so a
# version-dependent result shows up as a red build rather than as a surprise.
FROM python:3.13-slim

# libgomp1: pymupdf's wheels link against it on slim images.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# uid 1000 matches the usual desktop/CI user, so files written onto a
# bind-mounted working tree do not come back owned by root.
RUN useradd --create-home --uid 1000 app

WORKDIR /app

# Dependencies first, so a source edit does not re-resolve the world.
COPY requirements.lock ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.lock

# The one thing that needs network and is not a pip package. It installs into
# the *user's* home (~/.duckdb/extensions/<duckdb version>/), so it has to be
# done as the user that will run the tests.
USER app
RUN python -c "import duckdb; c = duckdb.connect(); c.execute('INSTALL fts'); c.execute('LOAD fts')"

USER root
COPY . /app
RUN pip install --no-cache-dir --no-deps -e . \
    && chown -R app:app /app
USER app

CMD ["python", "-m", "pytest", "-q"]
