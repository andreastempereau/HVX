#!/bin/bash
# Start Helmet Visor UI

# Load .env file if it exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Suppress ALSA errors
export ALSA_CARD=null
export SDL_AUDIODRIVER=dummy

export QT_QPA_PLATFORM=eglfs
export QT_QPA_EGLFS_HIDECURSOR=1
export HELMET_PROFILE=dev
export PYTHONPATH=/home/hvx/HVX/helmet:/home/hvx/HVX/helmet/libs

# Run the app (suppress ALSA errors on stderr)
python -u apps/visor-ui/main.py 2> >(grep -v "ALSA lib" >&2)
