"""Results of the detectors of ultrasonic vocalizations (USVSEG, DeepSqueak...), read as they come.

Every call keeps the same few columns whatever the tool, so the tools can be put side by side, and
all the variables the tool gave in `native`: people choose their own classification from them.
Only the standard library is used (a DeepSqueak result is an .xlsx, read here without a package).
"""

import csv
import io
import math
import ntpath
import re
import statistics
import zipfile

from defusedxml import ElementTree  # a result file comes from outside: no entity tricks

# the tools that can be shown, with their publication
TOOLS = {
    "usvseg": {
        "label": "USVSEG",
        "color": "#8c564b",
        "formats": [".csv", ".txt"],
        "help": "The table written by USVSEG (start, end, maxfreq, meanfreq...).",
        "reference": "10.1371/journal.pone.0228907",
        "citation": "Tachibana et al., 2020, PLoS ONE 15(2): e0228907",
    },
    "deepsqueak": {
        "label": "DeepSqueak",
        "color": "#e377c2",
        "formats": [".xlsx", ".csv"],
        "help": "The table exported by DeepSqueak (Begin Time, End Time, frequencies...).",
        "reference": "10.1038/s41386-018-0303-6",
        "citation": "Coffey, Marx and Neumaier, 2019, Neuropsychopharmacology 44: 859-868",
    },
    "avisoft": {
        "label": "Avisoft SASLab Pro",
        "color": "#1f77b4",
        "formats": [".csv", ".txt"],
        "help": "The table exported by SASLab Pro (start time, end time, peak freq...).",
        "reference": "",
        "citation": "Avisoft SASLab Pro, Avisoft Bioacoustics",
    },
    "sonotrack": {
        "label": "SonoTrack",
        "color": "#2ca02c",
        "formats": [".txt", ".csv"],
        "help": "The table exported by SonoTrack (Start Time, End Time, PF. Min, PF. Max...).",
        "reference": "",
        "citation": "SonoTrack",
    },
    "ratrec": {
        "label": "RatRec",
        "color": "#ff7f0e",
        "formats": [".csv", ".txt"],
        "help": "The table exported by RatRec (Start [s], End [s], Minimum frequency [kHz]...).",
        "reference": "",
        "citation": "RatRec",
    },
    "usvtoolbox": {
        "label": "LMT USV Toolbox",
        "color": "#9467bd",
        "formats": [".csv"],
        "help": "The table of the LMT USV Toolbox (Voc number, startOffset, duration...).",
        "reference": "10.3389/fnbeh.2021.735920",
        "citation": "de Chaumont et al., 2021, Front. Behav. Neurosci. 15: 735920",
    },
}
COLUMNS = (
    "start_s",
    "end_s",
    "duration_s",
    "freq_min_khz",
    "freq_max_khz",
    "freq_mean_khz",
    "freq_peak_khz",
)
MAX_XLSX_BYTES = (
    100 * 1024 * 1024
)  # unpacked: a small file must not unpack to gigabytes
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _float(value):
    try:
        number = float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number  # "nan" is nothing


def _clean(value):
    """A number when it is one; a path becomes its file name (the folders of someone's computer,
    often with their user name, are not ours to show)."""
    number = _float(value)
    if number is not None:
        return number
    if isinstance(value, str) and ("\\" in value or value.startswith("/")):
        return ntpath.basename(value.replace("/", "\\"))
    return value


def _call(start, end, **frequencies):
    call = {"start_s": start, "end_s": end, "duration_s": round(end - start, 6)}
    call.update({name: frequencies.get(name) for name in COLUMNS[3:]})
    return call


def read_xlsx(data):
    """The rows of the first sheet of an .xlsx, as lists of strings or numbers."""
    with zipfile.ZipFile(io.BytesIO(data)) as book:
        if sum(info.file_size for info in book.infolist()) > MAX_XLSX_BYTES:
            raise ValueError("The spreadsheet is too large once unpacked.")
        names = book.namelist()
        strings = []
        if "xl/sharedStrings.xml" in names:
            root = ElementTree.fromstring(book.read("xl/sharedStrings.xml"))
            strings = [
                "".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")) for si in root
            ]
        sheet = ElementTree.fromstring(book.read("xl/worksheets/sheet1.xml"))
    rows = []
    for row in sheet.iter(f"{{{NS['m']}}}row"):
        cells = {}
        for cell in row.iter(f"{{{NS['m']}}}c"):
            value = cell.find("m:v", NS)
            if value is None or value.text is None:
                continue
            column = re.match(r"[A-Z]+", cell.get("r")).group()
            cells[column] = (
                strings[int(value.text)] if cell.get("t") == "s" else value.text
            )
        if cells:
            width = max(_column_index(c) for c in cells) + 1
            rows.append([cells.get(_column_name(i)) for i in range(width)])
    return rows


def _column_index(name):
    index = 0
    for letter in name:
        index = index * 26 + ord(letter) - 64
    return index - 1


def _column_name(index):
    name = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(65 + rest) + name
    return name


def read_table(data):
    """The rows of a result table: an .xlsx (a zip) or a text table with commas, semicolons or tabs."""
    if data[:2] == b"PK":
        return read_xlsx(data)
    text = data.decode("utf-8-sig", errors="replace")
    delimiter = max(",;\t", key=lambda d: text.split("\n", 1)[0].count(d))
    return [row for row in csv.reader(io.StringIO(text), delimiter=delimiter) if row]


def _hms(value):
    """SonoTrack writes a time as hhh:mm:ss.mmm."""
    try:
        hours, minutes, seconds = str(value).split(":")
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds.replace(",", "."))
    except ValueError:
        return None


# How each tool names its columns. `header` is a column that only the header row holds (a tool can
# write lines before it); `start` and `end` (or `duration`) are the times; `time` reads one (default: a
# number) and `time_scale` brings it to seconds; `freq` maps our columns to the tool's, `freq_scale`
# brings them to kHz.
READERS = {
    "usvseg": {
        "header": "start",
        "start": "start",
        "end": "end",
        "freq": {"freq_mean_khz": "meanfreq", "freq_peak_khz": "maxfreq"},
        "drop": ("#",),
    },
    "deepsqueak": {
        "header": "Begin Time (s)",
        "start": "Begin Time (s)",
        "end": "End Time (s)",
        "freq": {
            "freq_min_khz": "Low Freq (kHz)",
            "freq_max_khz": "High Freq (kHz)",
            "freq_mean_khz": "Principal Frequency (kHz)",
            "freq_peak_khz": "Peak Freq (kHz)",
        },
    },
    "avisoft": {
        "header": "start time",
        "start": "start time",
        "end": "end time",
        "freq": {
            "freq_min_khz": "peak freq(minentire)",
            "freq_max_khz": "peak freq(maxentire)",
            "freq_mean_khz": "peak freq(meanentire)",
            "freq_peak_khz": "peak freq(max)",
        },
        "freq_scale": 0.001,  # Hz
    },
    "sonotrack": {
        "header": "Start Time",
        "start": "Start Time",
        "end": "End Time",
        "time": _hms,
        "freq": {
            "freq_min_khz": "PF. Min",
            "freq_max_khz": "PF. Max",
            "freq_mean_khz": "PF. Mean",
        },
        "freq_scale": 0.001,
    },
    "ratrec": {
        "header": "Start [s]",
        "start": "Start [s]",
        "end": "End [s]",
        "freq": {
            "freq_min_khz": "Minimum frequency [kHz]",
            "freq_max_khz": "Maximum frequency [kHz]",
            "freq_mean_khz": "Mean frequency [kHz]",
        },
    },
    "usvtoolbox": {
        "header": "Voc number",
        "start": "startOffset(ms)",
        "duration": "duration(ms):",
        "time_scale": 0.001,
        "freq": {
            "freq_min_khz": "minFrequency(Hz)",
            "freq_max_khz": "maxFrequency(Hz)",
            "freq_mean_khz": "meanFrequency(Hz)",
            "freq_peak_khz": "peak Frequency(Hz)",
        },
        "freq_scale": 0.001,
    },
}


def _read_calls(data, reader):
    rows = read_table(data)
    header_at = next((i for i, row in enumerate(rows) if reader["header"] in row), None)
    if header_at is None:
        return []
    header = rows[header_at]
    to_seconds, scale = reader.get("time", _float), reader.get("time_scale", 1)
    to_khz = reader.get("freq_scale", 1)
    calls = []
    for row in rows[header_at + 1 :]:
        values = dict(zip(header, row, strict=False))
        start = to_seconds(values.get(reader["start"]))
        end = to_seconds(values.get(reader.get("end")))
        if start is None:
            continue
        start *= scale
        if "duration" in reader:
            length = _float(values.get(reader["duration"]))
            end = None if length is None else start + length * scale
        elif end is not None:
            end *= scale
        if end is None:
            continue
        start, end = round(start, 6), round(end, 6)  # no float noise from the units
        if end <= start:
            continue
        frequencies = {}
        for name, column in reader["freq"].items():
            number = _float(values.get(column))
            frequencies[name] = None if number is None else round(number * to_khz, 6)
        call = _call(start, end, **frequencies)
        call["native"] = {
            k: _clean(v)
            for k, v in values.items()
            if k and v is not None and k not in reader.get("drop", ())
        }
        calls.append(call)
    return sorted(calls, key=lambda c: c["start_s"])


def summarize(calls):
    """A few figures to read at a glance: how many calls, how often, how long, how high.

    The span is where the calls end: the length of the file is not always known, and the one in the
    catalog can be that of the recording the file was trimmed from."""
    if not calls:
        return {"calls": 0}
    durations = [c["duration_s"] * 1000 for c in calls]
    span = max(c["end_s"] for c in calls)
    means = [c["freq_mean_khz"] for c in calls if c["freq_mean_khz"] is not None]
    lows = [c["freq_min_khz"] for c in calls if c["freq_min_khz"] is not None]
    highs = [c["freq_max_khz"] for c in calls if c["freq_max_khz"] is not None]
    return {
        "calls": len(calls),
        "span_s": round(span, 3),
        "calls_per_min": round(len(calls) / span * 60, 1) if span else None,
        "median_duration_ms": round(statistics.median(durations), 1),
        "mean_freq_khz": round(statistics.mean(means), 1) if means else None,
        "freq_min_khz": round(min(lows), 1) if lows else None,
        "freq_max_khz": round(max(highs), 1) if highs else None,
    }


def parse(tool, data):
    """The calls of a result file: `data` is bytes."""
    return _read_calls(data, READERS[tool])


MAX_RESULT_BYTES = 20 * 1024 * 1024
MAX_CALLS = 50000


class ResultError(ValueError):
    """The file cannot be read as the results of that tool: the message is for the person."""


def read_result(tool, filename, data):
    """The calls of an uploaded result file, or a ResultError saying what is wrong with it."""
    if tool not in TOOLS:
        raise ResultError(f"Unknown tool: {tool}.")
    extension = ntpath.splitext(filename or "")[1].lower()
    if extension not in TOOLS[tool]["formats"]:
        wanted = " or ".join(TOOLS[tool]["formats"])
        raise ResultError(f"{TOOLS[tool]['label']} results are a {wanted} file.")
    if len(data) > MAX_RESULT_BYTES:
        raise ResultError("This file is too large to be a table of results.")
    try:
        calls = parse(tool, data)
    except Exception as exc:  # a broken zip, a missing sheet... all mean "not readable"
        raise ResultError(
            f"This file could not be read as {TOOLS[tool]['label']} results."
        ) from exc
    if not calls:
        raise ResultError(f"No call found: is it the table of {TOOLS[tool]['label']}?")
    if len(calls) > MAX_CALLS:
        raise ResultError(f"Too many calls ({len(calls)}) for one file.")
    return calls
