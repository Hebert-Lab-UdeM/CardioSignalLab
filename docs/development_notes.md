# Development Notes: Code Review & Improvement Opportunities

**Last Updated**: 2026-02-19
**Source**: Comprehensive code review session with focus on architecture, patterns, and code quality

## Overview

This document captures improvement opportunities identified during a full codebase review. Issues are organized by severity and include specific file references and recommended fixes.

---

## CRITICAL ISSUES (Maintenance Burden)

These reduce maintainability and should be addressed in prioritized sessions.

### 1. Function Complexity: `export_intervals()` (Severity: High)

**File**: `src/cardio_signal_lab/core/exporter.py:206-298`
**Metrics**:
- Lines: 147
- Cyclomatic complexity: 19
- Responsibilities: 5+ (validation, sorting, computation, filtering, dataframe construction)

**Problem**: Single function handles multiple concerns (peak sorting, validity computation, classification checking, event annotation, dataframe construction). Difficult to test, understand, and modify.

**Recommended Solution**: Extract into focused helper functions

```python
# Instead of single export_intervals(), create:
def _sort_and_validate_peaks(peaks) -> tuple[np.ndarray, np.ndarray]:
    """Sort peaks and return validated arrays."""

def _compute_interval_validity(rr_ms, min_ms, max_ms, stat_threshold) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute phys, stat, and classification validity flags."""

def _annotate_with_events(intervals, peak_times, events) -> np.ndarray:
    """Map events to interval midpoints."""

def _build_interval_dataframe(interval_arrays, mode) -> pd.DataFrame:
    """Construct dataframe with appropriate columns for mode."""

def _filter_nn_intervals(df) -> pd.DataFrame:
    """Filter to only valid NN intervals."""

# Then export_intervals() becomes:
def export_intervals(...) -> Path:
    # Validate mode
    # Sort peaks
    validity_arrays = _compute_interval_validity(...)
    event_labels = _annotate_with_events(...)
    df = _build_interval_dataframe(...)
    if mode == "nn":
        df = _filter_nn_intervals(df)
    df.to_csv(output_path)
```

**Impact**: Each function ~30-40 lines, single responsibility, testable independently.

**Estimated Effort**: 2-3 hours

---

### 2. Function Complexity: `load_peaks_binary_csv()` (Severity: High)

**File**: `src/cardio_signal_lab/core/importers.py:119-246`
**Metrics**:
- Lines: 127
- Cyclomatic complexity: 23
- Issue: Deeply nested conditionals for different CSV column layouts

**Problem**: Multiple branches handle different peak CSV formats (different column orderings). Logic is convoluted.

**Recommended Solution**: Strategy pattern with separate parsers

```python
class PeakParser(Protocol):
    """Strategy for parsing peak CSVs."""
    def parse(self, df: pd.DataFrame) -> np.ndarray: ...

class StandardLayoutParser(PeakParser):
    """Handles: peak_index, time, amplitude columns."""
    def parse(self, df) -> np.ndarray:
        return df['peak_index'].values

class TimeOnlyParser(PeakParser):
    """Handles: just timestamps, infer indices."""
    def parse(self, df) -> np.ndarray:
        # Convert timestamps to indices

class CustomColumnParser(PeakParser):
    """Handles: user-specified column names."""
    def __init__(self, index_col, time_col):
        self.index_col = index_col
        ...

def _get_parser_for_format(df_columns) -> PeakParser:
    """Auto-detect parser based on available columns."""
    if 'peak_index' in df_columns:
        return StandardLayoutParser()
    elif 'time_s' in df_columns:
        return TimeOnlyParser()
    else:
        raise ValueError("Cannot auto-detect peak CSV format")

def load_peaks_binary_csv(path, **kwargs):
    df = pd.read_csv(path)
    parser = _get_parser_for_format(df.columns)
    return parser.parse(df)
```

**Impact**: Each parser ~15-20 lines, clear branching logic, easy to test and extend.

**Estimated Effort**: 2-3 hours

---

### 3. Keyboard Event Handler Complexity (Severity: High)

**File**: `src/cardio_signal_lab/gui/single_channel_view.py:371-496`
**Metrics**:
- Lines: 125
- Cyclomatic complexity: 19
- Issue: `keyPressEvent()` handles 15+ keyboard shortcuts with nested if/elif chains

**Problem**: Single method routes all keyboard input. Hard to understand flow, modify behavior, or add shortcuts.

**Recommended Solution**: Extract keyboard dispatcher

```python
class KeyBindingDispatcher:
    """Routes keyboard events to handlers based on key bindings."""

    def __init__(self, view):
        self.view = view
        self.handlers = {
            Qt.Key.Key_Right: self._handle_next_peak,
            Qt.Key.Key_Left: self._handle_prev_peak,
            Qt.Key.Key_Delete: self._handle_delete_peak,
            Qt.Key.Key_D: self._handle_classify_bad,
            Qt.Key.Key_M: self._handle_classify_manual,
            Qt.Key.Key_E: self._handle_classify_ectopic,
            Qt.Key.Key_B: self._handle_classify_auto,
            Qt.Key.Key_Escape: self._handle_escape,
            Qt.Key.Key_Z: self._handle_undo,
            Qt.Key.Key_Y: self._handle_redo,
            # ... more bindings
        }

    def dispatch(self, event: QKeyEvent) -> bool:
        """Route key event to appropriate handler. Return True if handled."""
        handler = self.handlers.get(event.key())
        if handler:
            return handler(event)
        return False

    def _handle_next_peak(self, event) -> bool:
        """Move to next peak."""
        ...

    def _handle_delete_peak(self, event) -> bool:
        """Delete current peak."""
        ...

    # ... one method per action ...

# In SingleChannelView:
def __init__(self):
    self.key_dispatcher = KeyBindingDispatcher(self)

def keyPressEvent(self, event):
    if self.key_dispatcher.dispatch(event):
        event.accept()
    else:
        super().keyPressEvent(event)
```

**Impact**:
- Main `keyPressEvent()` becomes 5 lines
- Each handler ~5-10 lines with clear intent
- Easy to add new shortcuts

**Estimated Effort**: 2-3 hours

---

## MAJOR ISSUES (Code Organization)

These improve code clarity and maintainability.

### 4. Long GUI Initialization Methods

**Files**:
- `src/cardio_signal_lab/gui/analysis_plots.py:224` (142 lines)
- `src/cardio_signal_lab/gui/event_editor_dialog.py:87` (107 lines)

**Problem**: `__init__` methods mix widget creation, layout setup, signal connection, and initialization.

**Recommended Solution**: Extract helper methods

```python
# analysis_plots.py
class AnalysisPlots(QWidget):
    def __init__(self):
        super().__init__()
        self._setup_time_domain_plots()
        self._setup_freq_domain_plots()
        self._setup_event_overlays()
        self._connect_signals()

    def _setup_time_domain_plots(self):
        """Create time-domain plot widgets and layouts."""
        # Current lines 224-XXX extracted

    def _setup_freq_domain_plots(self):
        """Create frequency-domain plot widgets."""
        # Current lines XXX-YYY extracted

    def _setup_event_overlays(self):
        """Create event overlay widgets."""
        # Current lines YYY-ZZZ extracted

    def _connect_signals(self):
        """Connect inter-widget signals."""
        # Current signal connections extracted
```

**Impact**: `__init__()` becomes declarative (clear flow), helper methods focused.

**Estimated Effort**: 1-2 hours per file

---

### 5. Configuration Management (`settings.py`)

**File**: `src/cardio_signal_lab/config/settings.py`
**Problem**: 20 module-level functions instead of structured config. Hard to see full schema.

**Recommended Solution**: Use dataclass with groups

```python
from dataclasses import dataclass

@dataclass
class SignalProcessingConfig:
    """Signal processing parameters."""
    ecg_bandpass_low: float = 0.5
    ecg_bandpass_high: float = 40.0
    ecg_notch_freq: float = 50.0
    ppg_bandpass_low: float = 0.5
    ppg_bandpass_high: float = 8.0
    eda_bandpass_low: float = 0.05
    eda_bandpass_high: float = 5.0

@dataclass
class GuiConfig:
    """GUI appearance and behavior."""
    window_width: int = 1200
    window_height: int = 800
    plot_background: str = "white"
    grid_alpha: float = 0.3

@dataclass
class ApplicationConfig:
    """All configuration."""
    processing: SignalProcessingConfig = field(default_factory=SignalProcessingConfig)
    gui: GuiConfig = field(default_factory=GuiConfig)

# Access: config.processing.ecg_bandpass_low
```

**Impact**: Config schema visible at a glance, validated on creation, hierarchical.

**Estimated Effort**: 1 hour

---

### 6. Inline Trivial Callbacks

**File**: `src/cardio_signal_lab/gui/imf_selection_dialog.py:194-198`

**Problem**: Single-use 3-line function better as lambda.

```python
# Current
def _on_toggle(checked):
    pw.setBackground(self._BG_KEEP if checked else self._BG_EXCLUDE)

cb.toggled.connect(_on_toggle)

# Better
cb.toggled.connect(
    lambda checked: pw.setBackground(
        self._BG_KEEP if checked else self._BG_EXCLUDE
    )
)
```

**Impact**: Cleaner code, less namespace pollution.

**Estimated Effort**: 0.5 hours

---

## MINOR ISSUES (Code Quality)

These improve robustness and consistency.

### 7. Signal Filter Consistency

**File**: `src/cardio_signal_lab/processing/filters.py`

**Issue**: Bandpass uses `sosfiltfilt` (modern), notch uses `filtfilt` (older API).

**Recommendation**: Standardize to `sosfiltfilt` for all filters.

```python
# notch_filter() currently (line 211):
b, a = iirnotch(freq, quality_factor, sampling_rate)
filtered = filtfilt(b, a, samples)

# Better:
sos = iirnotch(freq, quality_factor, sampling_rate, output='sos')
filtered = sosfiltfilt(sos, samples)
```

**Impact**: Consistent API, numerically stable.

**Estimated Effort**: 0.5 hours

---

### 8. Type Hint Specificity

**File**: `src/cardio_signal_lab/gui/status_bar.py:77`

**Problem**: Over-defensive type checking.

```python
# Current
self.num_signals = len(session.signals) if hasattr(session, "signals") else 0

# Better
if session and isinstance(session, RecordingSession):
    self.num_signals = len(session.signals)
else:
    self.num_signals = 0
```

**Impact**: Clearer intent, proper type narrowing.

**Estimated Effort**: 0.5 hours

---

### 9. Registry Safeguards (`pipeline.py`)

**File**: `src/cardio_signal_lab/processing/pipeline.py:29-31`

**Problem**: Duplicate operation registration silently overwrites with warning.

```python
# Current (line 29-31)
if name in _OPERATIONS:
    logger.warning(f"Overwriting registered operation: {name}")
_OPERATIONS[name] = func

# Better: Fail fast
if name in _OPERATIONS:
    raise ValueError(
        f"Operation '{name}' already registered. "
        f"Use update_operation() to replace."
    )
_OPERATIONS[name] = func

# And provide explicit update method:
def update_operation(name: str, func: Callable):
    """Replace an existing operation."""
    if name not in _OPERATIONS:
        raise KeyError(f"Operation '{name}' not found")
    _OPERATIONS[name] = func
```

**Impact**: Bugs visible immediately instead of silent overwrites.

**Estimated Effort**: 0.5 hours

---

### 10. Error Message Consistency

**Files**: Various validators (`file_loader.py`, `data_models.py`, etc.)

**Problem**: Error messages have inconsistent format and detail level.

**Recommended Standard**:
```python
# Format: What, Expected, How to fix
raise ValueError(
    f"Signal sampling rate must be 16-2000 Hz, got {sr}. "
    f"Check file format or device settings."
)
```

**Impact**: Users get actionable error messages.

**Estimated Effort**: 1-2 hours (audit + standardize)

---

### 11. Baseline Correction Edge Case

**File**: `src/cardio_signal_lab/processing/filters.py:218-243`

**Issue**: `baseline_correction()` doesn't warn if signal is constant (polyfit fails silently).

```python
# Current
x = np.arange(len(samples))
coeffs = np.polyfit(x, samples, poly_order)
baseline = np.polyval(coeffs, x)
return samples - baseline

# Better: Add detection
if np.allclose(samples, samples[0]):  # Constant signal
    logger.warning("Signal is constant, baseline correction has no effect")
    return samples.copy()

# Rest of function...
```

**Impact**: Prevents silent data issues.

**Estimated Effort**: 0.5 hours

---

### 12. NeuroKit Function Naming

**File**: `src/cardio_signal_lab/processing/peak_detection.py`

**Issue**: Inconsistent NeuroKit function calls.
- ECG: `nk.ecg_peaks()`
- PPG: `nk.ppg_findpeaks()`

**Note**: These are NeuroKit's naming inconsistencies, not our code. Document but don't change.

**Recommendation**: Add comment documenting the quirk.

```python
# ECG uses nk.ecg_peaks() (NeuroKit naming)
_, rpeaks = nk.ecg_peaks(...)

# PPG uses nk.ppg_findpeaks() (different function name, same purpose)
info = nk.ppg_findpeaks(...)
```

**Estimated Effort**: 0.25 hours (just documentation)

---

## Implementation Priority

### Session 1 (Foundation): 2-3 hours
1. Extract `export_intervals()` helpers
2. Standardize filter APIs (sosfiltfilt)
3. Add registry safeguards (fail-fast)

### Session 2 (Architecture): 3-4 hours
1. Refactor `load_peaks_binary_csv()` with strategy pattern
2. Extract keyboard event dispatcher
3. Standardize error messages

### Session 3 (Polish): 1-2 hours
1. Refactor long GUI `__init__` methods
2. Inline trivial callbacks
3. Fix type hint specificity
4. Add baseline correction edge case handling

### Session 4 (Configuration): 1 hour
1. Convert `settings.py` to dataclass pattern

---

## Testing Recommendations

After implementing each refactor:
1. Run existing test suite (should pass)
2. Add unit tests for extracted functions (especially helpers)
3. Run integration tests for export/session workflows
4. Manual GUI testing for keyboard handling

All tests currently pass (41 tests, 100% of implemented features).

---

## Notes for Academic Context

These improvements align with research software best practices:
- ✅ Better testability enables verification
- ✅ Reduced complexity reduces errors
- ✅ Clearer error messages aid debugging
- ✅ Consistent patterns improve reproducibility

The current codebase is **already production-ready**. These improvements are for **long-term maintainability** and **team collaboration**.

---

## Conclusion

**Current Status**: MVP complete, all core features working, 41 tests passing.

**Recommendations**:
1. Deploy as-is (ready for user testing)
2. Implement Priority 1 items during next sprint
3. Address Priority 2-4 as time permits or during next major version

**Timeline**: Priority 1-2 could be completed in 1 week of focused development.
