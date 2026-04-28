import os
import re

filepath = 'helpybotest/templates/customize_chatbot.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('var(--text-primary)', 'var(--text-main)')
content = content.replace('var(--text-secondary)', 'var(--text-muted)')
content = content.replace('var(--text-tertiary)', 'var(--text-muted)')
content = content.replace('var(--background)', 'var(--background)')
content = content.replace('var(--background-alt)', 'var(--background)')
content = content.replace('var(--card-bg)', 'var(--card-bg)')
content = content.replace('var(--border)', 'var(--border)')
content = content.replace('var(--border-light)', 'var(--border)')
content = content.replace('var(--primary-light)', 'rgba(99, 102, 241, 0.1)')
content = content.replace('var(--primary-lighter)', 'rgba(99, 102, 241, 0.05)')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
