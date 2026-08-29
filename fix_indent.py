import re

with open('newfile.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if 'logging.error("Exception occurred"' in line:
        # Check previous line's indent
        prev_line = lines[i-1]
        if 'except Exception as e:' in prev_line:
            indent = len(prev_line) - len(prev_line.lstrip())
            new_lines.append(" " * (indent + 4) + line.lstrip())
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

with open('newfile.py', 'w') as f:
    f.writelines(new_lines)
