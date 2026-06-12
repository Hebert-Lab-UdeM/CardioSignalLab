#!/usr/bin/env sh
# CardioSignalLab launcher for macOS / Linux
#
# Tries, in order:
#   1. The installed `cardio-signal-lab` console script (pip install)
#   2. The conda env `cardio-signal-lab`
#   3. A venv in the project directory
#
# Usage:  ./CardioSignalLab.sh
#         sh CardioSignalLab.sh

set -eu

if command -v cardio-signal-lab >/dev/null 2>&1; then
    exec cardio-signal-lab
fi

CONDA_ENV="cardio-signal-lab"

for CONDA_BASE in "$HOME/miniconda3" "$HOME/Miniconda3" "$HOME/anaconda3" "$HOME/Anaconda3" "/opt/miniconda3" "/opt/anaconda3" "/opt/homebrew/Caskroom/miniconda/base"; do
    if [ -f "$CONDA_BASE/envs/$CONDA_ENV/bin/python" ]; then
        exec "$CONDA_BASE/envs/$CONDA_ENV/bin/python" -m cardio_signal_lab.app
    fi
done

if [ -f ./venv/bin/python ]; then
    exec ./venv/bin/python -m cardio_signal_lab.app
fi

cat <<EOF
Error: Could not find the installed application or the "$CONDA_ENV" conda environment.

To install, open a terminal and run:

    conda create -n $CONDA_ENV python=3.12
    conda activate $CONDA_ENV
    pip install https://github.com/SDevrajK/CardioSignalLab/archive/refs/heads/main.zip
    ./CardioSignalLab.sh

Or using pip in a virtual environment:

    python3 -m venv venv
    source venv/bin/activate
    pip install https://github.com/SDevrajK/CardioSignalLab/archive/refs/heads/main.zip
    ./CardioSignalLab.sh
EOF
