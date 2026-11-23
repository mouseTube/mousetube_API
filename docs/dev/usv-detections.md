# Detections of ultrasonic vocalizations

A file can come with the results of the detection tools that were run on it: the calls each tool found,
shown in the list of vocalizations next to the recording. mouseTube does not run any detector: the author
runs the tool and gives its table, mouseTube reads it and shows it. Tools do not agree with each other, so
each one is shown with its own figures and every variable it wrote, and people choose the one they trust.

## The tools

| Tool | Table |
|---|---|
| USVSEG | `.csv`, `.txt` |
| DeepSqueak | `.xlsx`, `.csv` |
| Avisoft SASLab Pro | `.csv`, `.txt` |
| SonoTrack | `.txt`, `.csv` |
| RatRec | `.csv`, `.txt` |
| LMT USV Toolbox | `.csv` |

`GET /api/usv-detection/tools/` lists them with their colour, formats and publication. A tool is added in
`mousetube_api/utils/usv.py`: an entry in `TOOLS` and a description of its columns in `READERS` (which
columns hold the start and end, in which unit, and the frequencies).

## What the author does

In the form that adds an **audio** file, a card per tool takes its table. The server reads it at once and the
form shows a preview (calls, rate, a timeline, the table) of what people will see; nothing is saved at that
point (`POST /api/usv-detection/preview/`). The tables are attached when the file is created
(`POST /api/file/<id>/usv-detections/`, the creator of the file only; sending a tool again replaces its
result). The creator can remove a result (`DELETE /api/usv-detection/<id>/`).

## What is kept

One row per file and tool (`UsvDetection`): the tool, its version and settings when known, a summary
(number of calls, rate, median duration, frequencies) and the calls. Each call has the same few columns
whatever the tool (start and end in seconds, minimum, maximum, mean and peak frequency in kHz) and, in
`native`, all the variables the tool gave, untouched. A path of the computer of the author (DeepSqueak writes
one) is reduced to the name of the file.

The list of files gives the summaries; the calls are read when someone opens a result
(`GET /api/usv-detection/<id>/`). Results follow the visibility of their file.

Limits: a table of 20 MB at most, 50 000 calls at most, the extension of the tool; an `.xlsx` is read with
`defusedxml` and refused if it unpacks to more than 100 MB.

## Sending the tables to the repository

The table of the author is **not** sent to Zenodo unless the author ticks *Also send this table to Zenodo
with the recording* (unticked by default). Only then is the original table kept on the server
(`media/usv_results/`), and it is put in the draft of the record just before it is published, named
`<file>_<tool>.<ext>` (see [published sessions](publication.md)). Otherwise the table is read, its values
are kept in the database, and the file is dropped.

## Importing published results

`python manage.py import_usv_detections --dir DIR` links results to files that already exist. `DIR` has one
folder per recording, named like the file without `.wav`, holding the results (`usvseg.csv`,
`deepsqueak.xlsx`, `avisoft.csv`, `sonotrack.txt`, `ratrec.csv`, `usvtoolbox.csv`) and, when there is one,
`parameters_analysis.csv` (`label;settings` per tool, for the version and settings). Options:
`--tools usvseg,deepsqueak` to take some of them, `--created-by USERNAME`, `--dry-run`. Running it again
replaces the same results.
