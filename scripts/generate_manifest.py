import json
import os
import re
from pathlib import Path
from datetime import datetime
import pytz

# The script is in 'scripts', so we go up one level to the project root.
PROJECT_ROOT = Path(__file__).parent.parent
MODULES_DIR = PROJECT_ROOT / "modules"
OUTPUT_FILE = PROJECT_ROOT / "source.json"

def extract_module_info(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    class_match = re.search(r'class\s+(\w+)\(BaseModule\):', content)
    if not class_match:
        return None
    
    name_match = re.search(r'self\.name\s*=\s*['"](.+?)['"]', content)
    if not name_match:
        return None

    author_match = re.search(r'self\.author\s*=\s*['"](.+?)['"]', content)
    if not author_match:
        return None

    description_match = re.search(r'self\.description\s*=\s*['"](.+?)['"]', content)
    if not description_match:
        return None
    
    version_match = re.search(r'self\.version\s*=\s*['"](.+?)['"]', content)
    version = version_match.group(1) if version_match else "1.0.0"
    
    return {
        "class_name": class_match.group(1),
        "name": name_match.group(1),
        "description": description_match.group(1),
        "author": author_match.group(1),
        "version": version
    }

def main():
    modules = []
    
    for py_file in MODULES_DIR.glob('**/*.py'):
        if not py_file.is_file() or py_file.name == '__init__.py':
            continue
        
        module_id = py_file.stem.replace('_module', '')
        
        info = extract_module_info(py_file)
        if not info:
            continue
        
        # Make file path relative to project root for the URL
        file_path_for_url = py_file.relative_to(PROJECT_ROOT)
        raw_url = f"{os.environ['BASE_URL']}/{os.environ['REPO_NAME']}/{os.environ['BRANCH']}/{file_path_for_url.as_posix()}"
        
        modules.append({
            "id": module_id,
            "name": info['name'],
            "author": info['author'],
            "description": info['description'],
            "version": info['version'],
            "url": raw_url
        })
    
    tz = pytz.timezone('Asia/Shanghai')
    manifest = {
        "name": os.environ.get("MODULE_NAME", "Aidepack Module Source"),
        "id": os.environ.get("MODULE_ID", "aidepack-module-source"),
        "date": datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S"),
        "data": modules
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    print(f"Generated {OUTPUT_FILE} with {len(modules)} modules")

if __name__ == "__main__":
    main()
