import re

with open('newfile.py', 'r') as f:
    content = f.read()

# We need to extract constants and group them together.
# Let's write a script to move them if they are not already moved.

# Find UNIT_TYPES
unit_types_match = re.search(r'UNIT_TYPES\s*=\s*\{.*?\n\}', content, re.DOTALL)
unit_types = unit_types_match.group(0) if unit_types_match else ""

# Find CASTLE_NAMES
castle_names_match = re.search(r'CASTLE_NAMES\s*=\s*\[.*?\]', content, re.DOTALL)
castle_names = castle_names_match.group(0) if castle_names_match else ""

# Find GACHA_POOL
gacha_pool_match = re.search(r'GACHA_POOL\s*=\s*\[.*?\]', content, re.DOTALL)
gacha_pool = gacha_pool_match.group(0) if gacha_pool_match else ""

# Find TERRITORY_REGIONS
territory_regions_match = re.search(r'TERRITORY_REGIONS\s*=\s*\{.*?\}', content, re.DOTALL)
territory_regions = territory_regions_match.group(0) if territory_regions_match else ""

# Find BUILDING_COSTS
# It's defined inside show_building_menu currently. We'll leave it there or move it up.
building_costs = """BUILDING_COSTS = {
    'wall': 200,
    'barracks': 300,
    'farm': 150,
    'sawmill': 180,
    'quarry': 170,
    'treasury': 250,
    'storage': 220
}

BUILDING_NAMES = {
    'wall': 'دیوار',
    'barracks': 'سربازخانه',
    'farm': 'مزرعه',
    'sawmill': 'کارخانه چوب',
    'quarry': 'معدن سنگ',
    'treasury': 'خزانه',
    'storage': 'انبار'
}

BUILDING_COLUMNS = {
    'wall': 'wall_level',
    'barracks': 'barracks_level',
    'farm': 'farm_level',
    'sawmill': 'sawmill_level',
    'quarry': 'quarry_level',
    'treasury': 'treasury_level',
    'storage': 'storage_level'
}"""

# Remove them from their original locations
if unit_types: content = content.replace(unit_types, "")
if castle_names: content = content.replace(castle_names, "")
if gacha_pool: content = content.replace(gacha_pool, "")
if territory_regions: content = content.replace(territory_regions, "")

# Remove from show_building_menu and callback handler
content = re.sub(r'    BUILDING_COSTS = \{[^}]+\}\n\n    BUILDING_NAMES = \{[^}]+\}\n\n    BUILDING_COLUMNS = \{[^}]+\}\n\n', '', content, flags=re.DOTALL)
content = re.sub(r'            BUILDING_COLUMNS = \{[^}]+\}\n            BUILDING_NAMES = \{[^}]+\}\n            BUILDING_COSTS = \{[^}]+\}\n\n', '', content, flags=re.DOTALL)


game_config_block = f"""
# ============================================================
# ================= GAME CONFIG =================
# ============================================================

{unit_types}

{castle_names}

{gacha_pool}

{territory_regions}

{building_costs}

"""

# Insert right after DB_PATH and other config
content = content.replace("# ضرایب بازی", game_config_block + "# ضرایب بازی")

with open('newfile.py', 'w') as f:
    f.write(content)
