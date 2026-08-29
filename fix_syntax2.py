with open('newfile.py', 'r') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if line.strip() == "," and "region_2" in lines[i+1]:
        skip = True
        continue
    if skip and "}" in line and i < len(lines)-1 and "def show_territory_attack_menu" in lines[i+2]:
        skip = False
        continue
    if not skip:
        new_lines.append(line)

with open('newfile.py', 'w') as f:
    f.writelines(new_lines)
