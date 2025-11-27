#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

# Function to find an available container command (podman or docker)
find_container_cli() {
    if command -v podman &> /dev/null; then
        echo "podman"
    elif command -v docker &> /dev/null; then
        echo "docker"
    else
        echo ""
    fi
}

CONTAINER_CLI=$(find_container_cli)

if [ -z "$CONTAINER_CLI" ]; then
    echo "Error: Neither Podman nor Docker was found. Please install one of them to proceed."
    exit 1
fi

echo "Using container CLI: $CONTAINER_CLI"

# Build the image and capture its ID
# The '-q' flag is supported by both podman and docker build to suppress output and return only the image ID.
IMAGE_ID=$($CONTAINER_CLI build -q .)

# Run the container using the selected CLI and captured image ID
$CONTAINER_CLI run -it \
    --volume "${PWD}:/io_scene_psk_psa:z" \
    --volume "${PWD}/io_scene_psk_psa:/addons/io_scene_psk_psa:z" \
    --volume "${PWD}/tests:/tests:z" \
    "$IMAGE_ID"
