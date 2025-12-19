# This script lists all files in the project directory that were modified yesterday.

import os
import datetime

root_dir = "."

exclude = {".venv", "__pycache__", ".git"}

days_to_lookback = 1  # change as needed

today = datetime.date.today()
start_date = today - datetime.timedelta(days=days_to_lookback)

# Collect files with their modification times
files_with_times = []

for dirpath, dirnames, filenames in os.walk(root_dir):
    dirnames[:] = [d for d in dirnames if d not in exclude]

    for filename in filenames:
        filepath = os.path.join(dirpath, filename)
        mtime = os.path.getmtime(filepath)
        modified_date = datetime.date.fromtimestamp(mtime)

        if start_date <= modified_date <= today:
            files_with_times.append((filepath, mtime))

# Sort by modification time (most recent first)
files_with_times.sort(key=lambda x: x[1], reverse=True)

# Print the sorted files
for filepath, mtime in files_with_times:
    modified_datetime = datetime.datetime.fromtimestamp(mtime)
    print(f"{modified_datetime.strftime('%Y-%m-%d %H:%M:%S')} - {filepath}")
