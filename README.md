# CardioSignalLab

Desktop application for viewing, processing, and correcting physiological signals (ECG, PPG, EDA) from XDF and CSV files.

## Features

- Load XDF (multi-stream) and CSV signal files
- Interactive signal viewer with zoom/pan
- Bandpass filter, notch filter, EEMD artifact removal
- Automatic peak detection (NeuroKit2) for ECG, PPG, and EDA
- Manual peak correction (add, delete, reclassify)
- Export peaks, annotations, and processed signals to CSV/NPY
- Session save/resume (.csl.json)

## Requirements

- Windows, macOS, or Linux
- Python 3.12 ([python.org](https://www.python.org/downloads/))

## Installation

### For colleagues (no git required)

**macOS** -- run these in a terminal **once** to install dependencies:

```
conda create -n cardio-signal-lab python=3.12
conda activate cardio-signal-lab
pip install https://github.com/SDevrajK/CardioSignalLab/archive/refs/heads/main.zip
```

After that, find `CardioSignalLab.app` in the downloaded folder and **double-click it
in Finder** to launch -- no Terminal window needed. (The `.app` is included in the repo
and ships inside the zip download.)

Alternatively, launch from Terminal with `./CardioSignalLab.sh` (also in the zip).

**Linux** -- run the same install commands, then launch with `./CardioSignalLab.sh`.

**Windows** -- run these in Anaconda Prompt:

```
conda create -n cardio-signal-lab python=3.12
conda activate cardio-signal-lab
pip install https://github.com/SDevrajK/CardioSignalLab/archive/refs/heads/main.zip
```

Then double-click `CardioSignalLab.bat` (download it from the repo) to launch.

To update to the latest version (all platforms):

```
conda activate cardio-signal-lab
pip install --upgrade https://github.com/SDevrajK/CardioSignalLab/archive/refs/heads/main.zip
```

> **Note:** Installing into a dedicated conda environment (not base) avoids DLL conflicts with Qt on Windows.

### For developers (with git)

```
git clone https://github.com/SDevrajK/CardioSignalLab.git
cd CardioSignalLab
pip install -e .
```

## Running the App

```
cardio-signal-lab
```

Or use the provided launcher:

```
CardioSignalLab.app           # macOS: double-click in Finder (no terminal)
./CardioSignalLab.sh          # macOS / Linux: run from Terminal
CardioSignalLab.bat           # Windows: double-click
```

### Using a virtual environment (recommended)

If you prefer to keep dependencies isolated from your base Python:

```
python3 -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate

pip install -e .
cardio-signal-lab
```

Or install with Homebrew on macOS:

```
brew install python@3.12
python3 -m venv venv
source venv/bin/activate
pip install https://github.com/SDevrajK/CardioSignalLab/archive/refs/heads/main.zip
./CardioSignalLab.sh
```

### Using conda

If you have Miniconda or Anaconda:

```
conda env create -f environment.yml
conda activate cardio-signal-lab
pip install -e .
cardio-signal-lab
```

## Supported File Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| XDF | `.xdf` | Multi-stream physiological recordings (LSL) |
| CSV | `.csv` | Single-channel, auto-detects ECG/PPG/EDA from column names |
| Session | `.csl.json` | Saved CardioSignalLab session (resume processing) |

## Workflow

1. **File > Open** - load an XDF or CSV file
2. Select a signal channel from the sidebar
3. **Processing** menu - apply filters or EEMD artifact removal
4. **Peaks** menu - run automatic peak detection
5. Click peaks to correct manually (add/delete/reclassify)
6. **File > Export** - save peaks and processed signal
7. **File > Save Session** - save progress to resume later

## Development Setup

Install dev dependencies and run tests:

```
pip install -e ".[dev]"
pytest
```

See `docs/SETUP.md` for detailed development guidance.
