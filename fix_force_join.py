import re

with open('newfile.py', 'r', encoding='utf-8') as f:
    content = f.read()

# process_admin_force_join already matched using the diff tool?
# Let's check:
