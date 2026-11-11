FROM ubuntu:22.04

RUN apt-get update -y && \
    apt-get install -y libxxf86vm-dev libxfixes3 libxi-dev libxkbcommon-x11-0 libgl1 libglx-mesa0 \
    libxrender1 libsm6 ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Keep the project environment outside of the source tree, since the source
# tree is mounted over /io_scene_psk_psa at runtime.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy

WORKDIR /io_scene_psk_psa

# Install the host-side tooling (pytest, pytest-blender, blender-downloader, etc.).
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked

ARG BLENDER_VERSION=5.2

# Download Blender and record the paths to its executable and bundled Python.
RUN BLENDER_EXECUTABLE=$(uv run --no-sync blender-downloader $BLENDER_VERSION --output-directory /opt --extract --remove-compressed --print-blender-executable) && \
    BLENDER_PYTHON=$(uv run --no-sync pytest-blender --blender-executable "${BLENDER_EXECUTABLE}") && \
    echo "${BLENDER_EXECUTABLE}" > /blender_executable_path && \
    echo "${BLENDER_PYTHON}" > /blender_python_path

# Install the test dependencies into Blender's bundled Python.
COPY tests/requirements.txt /tmp/requirements.txt
RUN uv pip install --python "$(cat /blender_python_path)" --break-system-packages -r /tmp/requirements.txt

ENTRYPOINT [ "/bin/bash", "-c" ]
CMD ["source tests/test.sh"]
