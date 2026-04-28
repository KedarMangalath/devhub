import os
import re

templates_dir = 'helpybotest/templates'

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # Replace hover and active backgrounds
    content = re.sub(r'background-color:\s*#e9ecef;', r'background-color: var(--surface-solid);', content, flags=re.IGNORECASE)
    content = re.sub(r'background-color:\s*#e7f5ff;', r'background-color: var(--primary-hover); color: white;', content, flags=re.IGNORECASE)
    
    # Replace input backgrounds
    content = re.sub(r'background-color:\s*#f8f9fa;', r'background-color: var(--input-bg);', content, flags=re.IGNORECASE)
    content = re.sub(r'background-color:\s*#fff;', r'background-color: var(--card-bg);', content, flags=re.IGNORECASE)
    content = re.sub(r'background-color:\s*#ffffff;', r'background-color: var(--card-bg);', content, flags=re.IGNORECASE)
    
    # Replace text colors
    content = re.sub(r'color:\s*#333;', r'color: var(--text-main);', content, flags=re.IGNORECASE)
    content = re.sub(r'color:\s*#666;', r'color: var(--text-muted);', content, flags=re.IGNORECASE)
    content = re.sub(r'color:\s*#495057;', r'color: var(--text-main);', content, flags=re.IGNORECASE)
    content = re.sub(r'color:\s*#212529;', r'color: var(--text-main);', content, flags=re.IGNORECASE)

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filepath}")

for filename in os.listdir(templates_dir):
    if filename.endswith('.html'):
        process_file(os.path.join(templates_dir, filename))
