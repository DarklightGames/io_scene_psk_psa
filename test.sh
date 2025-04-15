# usr/bin/env bash
docker run -it --volume ${PWD}:/io_scene_psk_psa --volume ${PWD}/io_scene_psk_psa:/addons/io_scene_psk_psa --volume ${PWD}/tests:/tests  $(docker build -q .)
