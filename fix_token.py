with open('newfile.py', 'r') as f:
    content = f.read()

content = content.replace('TOKEN = "7892171145:AAGPQUThtMfP6QXYPUyciYaU2RgGMh82M8Q"', 'import os\nTOKEN = os.getenv("BOT_TOKEN", "YOUR_TOKEN_HERE")')

with open('newfile.py', 'w') as f:
    f.write(content)
