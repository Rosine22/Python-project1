# Log Analyzer CLI

A Python CLI that reads a log file and prints a summary of errors,  warnings, and when they happened.

---

## Requirements

- Python 3.10+
- There is No installs needed

---

## Usage

```bash
# Basic
python log_analyzer.py -file "path/to/file.log"

# Filter by level
python log_analyzer.py -file "path/to/file.log" --level ERROR

# Filter by time
python log_analyzer.py -file "path/to/file.log" --from "2024-01-15 10:00:00" --to "2024-01-15 11:00:00"

# Export to CSV
python log_analyzer.py -file "path/to/file.log" -export summary.csv
```

---

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `-file` | | Path to your log file |
| `--level` | No | Filter by `ERROR`, `WARNING`, or `INFO` |
| `--from` | No | Start of time range |
| `--to` | No | End of time range |
| `-export` | No | Save summary to a CSV file |

---

## Supported Formats

**Plain text**
```
2024-01-15 10:03:10 ERROR Database timeout
2024-01-15 10:04:33 WARNING High memory usage
```

**JSON**
```json
{"timestamp": "2024-01-15T10:03:50", "level": "ERROR", "message": "Database timeout"}
```