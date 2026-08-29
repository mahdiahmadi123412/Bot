with open('newfile.py', 'r') as f:
    content = f.read()

bad_territory = "TERRITORY_REGIONS = {\n    'region_1': {'name': 'روستای مرزی 🏕️', 'defense': 500}\n"
good_territory = """TERRITORY_REGIONS = {
    'region_1': {'name': 'روستای مرزی 🏕️', 'defense': 500},
    'region_2': {'name': 'دشت‌های حاصلخیز 🌾', 'defense': 2500},
    'region_3': {'name': 'کوهستان طلایی ⛰️', 'defense': 8000},
    'region_4': {'name': 'دره اژدها 🐉', 'defense': 20000}
}"""

content = content.replace(bad_territory, good_territory + "\n")

with open('newfile.py', 'w') as f:
    f.write(content)
