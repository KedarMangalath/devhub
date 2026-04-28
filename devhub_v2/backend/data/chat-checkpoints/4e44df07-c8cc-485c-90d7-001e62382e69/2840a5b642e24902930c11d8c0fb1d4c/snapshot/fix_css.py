import os
import re

templates_dir = 'helpybotest/templates'

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # Replace background: white; or background-color: #fff; or background-color: white; inside style tags
    content = re.sub(r'background(-color)?:\s*(white|#fff|#ffffff|rgba\(255,\s*255,\s*255,\s*0\.95\));', r'background-color: var(--card-bg);', content, flags=re.IGNORECASE)
    
    # Replace background-color: #f8f9fa;
    content = re.sub(r'background(-color)?:\s*#f8f9fa;', r'background-color: var(--surface);', content, flags=re.IGNORECASE)

    # Replace color: #1d2741; or similar dark text colors
    content = re.sub(r'color:\s*#1d2741(be)?;', r'color: var(--text-main);', content, flags=re.IGNORECASE)
    content = re.sub(r'color:\s*#4560A9;', r'color: var(--primary);', content, flags=re.IGNORECASE)
    
    # Replace border colors
    content = re.sub(r'border:\s*1px\s+solid\s+#e0e6f7;', r'border: 1px solid var(--border);', content, flags=re.IGNORECASE)
    content = re.sub(r'border:\s*1px\s+solid\s+#dee2e6;', r'border: 1px solid var(--border);', content, flags=re.IGNORECASE)
    content = re.sub(r'border:\s*2px\s+solid\s*rgba\(67,\s*96,\s*169,\s*0\.3\);', r'border: 1px solid var(--border);', content, flags=re.IGNORECASE)
    content = re.sub(r'border:\s*2px\s+solid\s*#4360a927;', r'border: 1px solid var(--border);', content, flags=re.IGNORECASE)

    # Fix inputs
    content = re.sub(r'background:\s*#f8f9fd;', r'background-color: var(--input-bg);', content, flags=re.IGNORECASE)
    
    # Remove body styles in customize_chatbot.html
    if 'customize_chatbot.html' in filepath:
        content = re.sub(r'body\s*\{[^}]+\}', '', content)
        content = re.sub(r':root\s*\{[^}]+\}', '', content)

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filepath}")

for filename in os.listdir(templates_dir):
    if filename.endswith('.html'):
        process_file(os.path.join(templates_dir, filename))
