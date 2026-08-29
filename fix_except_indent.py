import re

with open('newfile.py', 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'logging.error("Exception occurred", exc_info=True)' in line:
        # Check previous line
        prev_line = lines[i-1]
        indent = len(prev_line) - len(prev_line.lstrip())
        new_indent = indent + 4
        lines[i] = " " * new_indent + 'logging.error("Exception occurred", exc_info=True)\n'

with open('newfile.py', 'w') as f:
    f.writelines(lines)
