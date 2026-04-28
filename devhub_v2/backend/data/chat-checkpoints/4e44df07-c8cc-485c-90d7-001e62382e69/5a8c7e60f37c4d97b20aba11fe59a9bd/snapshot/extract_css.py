import re

with open('helpybotest/templates/chat_widget_template.js', 'r', encoding='utf-8') as f:
    content = f.read()

match = re.search(r'style\.textContent = `(.*?)`;', content, re.DOTALL)
if match:
    css = match.group(1)
    # Find all selectors
    selectors = re.findall(r'([^{]+)\{', css)
    for s in selectors:
        s = s.strip()
        if not s.startswith('#chat-widget') and not s.startswith('@') and not s.startswith('.wave') and not s.startswith('#chat-header') and not s.startswith('.header-text-container') and not s.startswith('#chat-logo') and not s.startswith('#carousel'):
            print(s)
