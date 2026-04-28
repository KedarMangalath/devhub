import re

with open('css_content.txt', 'r') as f:
    css_content = f.read()

def update_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    new_content = re.sub(r'<style>.*?</style>', f'<style>\n{css_content}\n    </style>', content, flags=re.DOTALL)
    new_content = re.sub(r'<div class="bg-animation">.*?</div>', '<div class="bg-animation"></div>', new_content, flags=re.DOTALL)
    
    with open(filepath, 'w') as f:
        f.write(new_content)

update_file('helpybotest/templates/base.html')
update_file('helpybotest/templates/adminbase.html')
