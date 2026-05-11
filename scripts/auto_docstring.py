"""
auto_docstring.py

This module contains core functionality for the Nexus application.
"""

import os
from pathlib import Path

def process_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    ext = file_path.suffix.lower()
    filename = file_path.name
    
    if ext == '.py':
        # Check if already has a module docstring
        if not content.lstrip().startswith('"""') and not content.lstrip().startswith("'''"):
            docstring = f'"""\n{filename}\n\nThis module contains core functionality for the Nexus application.\n"""\n\n'
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(docstring + content)
            return True
            
    elif ext in ['.jsx', '.js']:
        # Check if already has a doc block
        if not content.lstrip().startswith('/**') and not content.lstrip().startswith('//'):
            docstring = f'/**\n * @file {filename}\n * @description Core React component/service for the Nexus application.\n */\n\n'
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(docstring + content)
            return True
            
    return False

def main():
    root = Path('.')
    modified = 0
    for file_path in root.rglob('*'):
        if file_path.is_file() and file_path.suffix in ['.py', '.jsx', '.js']:
            if 'node_modules' in file_path.parts or 'venv' in file_path.parts or '.git' in file_path.parts:
                continue
            if process_file(file_path):
                print(f"Added docstring to {file_path}")
                modified += 1
    
    print(f"Added docstrings to {modified} files.")

if __name__ == "__main__":
    main()
