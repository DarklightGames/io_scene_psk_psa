FROM ubuntu:22.04

ARG BLENDER_VERSION=4.4

RUN apt-get update -y && \
    apt-get install -y libxxf86vm-dev libxfixes3 libxi-dev libxkbcommon-x11-0 libgl1 libglx-mesa0 python3 python3-pip \
    libxrender1 libsm6

RUN pip install --upgrade pip
RUN pip install pytest-blender
RUN pip install blender-downloader

# Set BLENDER_EXECUTABLE and BLENDER_PYTHON as environment variables
RUN BLENDER_EXECUTABLE=$(blender-downloader $BLENDER_VERSION --extract --remove-compressed --print-blender-executable) && \
    BLENDER_PYTHON=$(pytest-blender --blender-executable "${BLENDER_EXECUTABLE}") && \
    echo "Blender executable: $BLENDER_EXECUTABLE" && \
    echo "Blender Python: $BLENDER_PYTHON" && \
    echo "export BLENDER_EXECUTABLE=${BLENDER_EXECUTABLE}" >> /etc/environment && \
    echo "export BLENDER_PYTHON=${BLENDER_PYTHON}" >> /etc/environment && \
    echo $BLENDER_EXECUTABLE > /blender_executable_path

# Source the environment variables and install Python dependencies
RUN . /etc/environment && \
    $BLENDER_PYTHON -m ensurepip && \
    $BLENDER_PYTHON -m pip install pytest

# Persist BLENDER_EXECUTABLE as an environment variable
RUN echo $(cat /blender_executable_path) > /tmp/blender_executable_path_env && \
    export BLENDER_EXECUTABLE=$(cat /tmp/blender_executable_path_env)
ENV BLENDER_EXECUTABLE /tmp/blender_executable_path_env

ENTRYPOINT [ "/bin/bash", "-c" ]
CMD ["export BLENDER_EXECUTABLE=$(cat /blender_executable_path) && echo $BLENDER_EXECUTABLE && pytest -svv tests --blender-executable $BLENDER_EXECUTABLE --blender-addons-dirs addons"]
