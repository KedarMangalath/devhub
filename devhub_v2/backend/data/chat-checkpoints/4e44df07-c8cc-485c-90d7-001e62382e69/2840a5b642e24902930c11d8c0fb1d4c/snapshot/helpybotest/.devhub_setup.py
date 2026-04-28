import os, re, subprocess, sys
imports = set()
for root, dirs, files in os.walk('.'):
    if '.venv' in dirs: dirs.remove('.venv')
    for f in files:
        if f.endswith('.py'):
            try:
                c = open(os.path.join(root, f), 'r', encoding='utf-8').read()
                for m in re.findall(r'^\s*(?:from|import)\s+([a-zA-Z0-9_]+)', c, re.MULTILINE):
                    imports.add(m)
            except: pass
ignore = set(sys.stdlib_module_names) if hasattr(sys, 'stdlib_module_names') else set()
to_install = []
mappings = {'dotenv': 'python-dotenv', 'cv2': 'opencv-python', 'PIL': 'Pillow', 'bs4': 'beautifulsoup4', 'yaml': 'pyyaml', 'dateutil': 'python-dateutil', 'github': 'PyGithub'}
for p in imports:
    if p not in ignore and not os.path.exists(p) and not os.path.exists(p+'.py'):
        to_install.append(mappings.get(p, p))
if to_install:
    print('Installing auto-detected dependencies:', ', '.join(to_install))
    subprocess.run([sys.executable, '-m', 'pip', 'install'] + to_install)
else:
    print('No external dependencies detected.')
