with open('newfile.py', 'r') as f:
    content = f.read()

content = content.replace('TOKEN = os.getenv("BOT_TOKEN", "YOUR_TOKEN_HERE")', 'TOKEN = os.getenv("BOT_TOKEN", "1234567890:YOUR_TOKEN_HERE")')

with open('newfile.py', 'w') as f:
    f.write(content)
