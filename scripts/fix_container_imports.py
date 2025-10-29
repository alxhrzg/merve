#!/usr/bin/env python3
"""Fix imports in refactored container modules."""
import re
from pathlib import Path

def fix_module_imports(module_path: Path):
    """Fix imports in a module file."""
    with open(module_path, 'r') as f:
        content = f.read()

    # Remove duplicate docstring headers
    content = re.sub(
        r'"""[^"]*"""\s*"""[^"]*"""',
        lambda m: m.group(0).split('"""')[2] + '"""',
        content,
        count=1
    )

    # Fix relative imports to absolute imports
    content = content.replace('from .config import AppConfig', 'from mlserver.config import AppConfig')
    content = content.replace('from .version import', 'from mlserver.version import')
    content = content.replace('from .version_control import', 'from mlserver.version_control import')
    content = content.replace('from .settings import', 'from mlserver.settings import')
    content = content.replace('from .multi_classifier import', 'from mlserver.multi_classifier import')

    # Keep internal container module imports as relative
    # (these are correct)

    with open(module_path, 'w') as f:
        f.write(content)

    print(f"  Fixed {module_path.name}")

def main():
    container_dir = Path("mlserver/container")

    print("Fixing imports in container modules...")
    for module_file in container_dir.glob("*.py"):
        if module_file.name != "__init__.py":
            fix_module_imports(module_file)

    print("\n✓ Import fixes complete!")

if __name__ == "__main__":
    main()
