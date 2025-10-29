#!/usr/bin/env python3
"""
Refactor container.py into a modular structure.

This script splits the monolithic container.py file into logical modules.
"""
import re
from pathlib import Path
from typing import List, Tuple

# Define the module structure with line ranges
MODULE_STRUCTURE = {
    "exceptions.py": {
        "lines": (30, 33),
        "desc": "Container-related exceptions"
    },
    "labels.py": {
        "lines": (35, 178),
        "desc": "Docker label generation for traceability"
    },
    "source.py": {
        "lines": (179, 372),
        "desc": "MLServer source detection and wheel building"
    },
    "detection.py": {
        "lines": (374, 580),
        "desc": "File detection and dependency analysis"
    },
    "dockerfile.py": {
        "lines": (582, 880),
        "desc": "Dockerfile and .dockerignore generation"
    },
    "config.py": {
        "lines": (882, 1104),
        "desc": "Container configuration and metadata preparation"
    },
    "build.py": {
        "lines": (1105, 1383),
        "desc": "Docker build operations and file writing"
    },
    "registry.py": {
        "lines": (1385, 1554),
        "desc": "Container registry operations (push, list, remove)"
    },
}

def extract_imports(lines: List[str]) -> Tuple[List[str], List[str]]:
    """Extract import statements from lines."""
    imports = []
    from_imports = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('import ') and not stripped.startswith('import mlserver'):
            imports.append(line)
        elif stripped.startswith('from ') and not stripped.startswith('from .'):
            from_imports.append(line)

    return imports, from_imports

def get_file_header(module_name: str, description: str) -> str:
    """Generate file header."""
    return f'''"""
{description}
"""
'''

def extract_section(container_lines: List[str], start: int, end: int) -> List[str]:
    """Extract a section of lines (1-indexed)."""
    # Convert to 0-indexed
    return container_lines[start-1:end]

def main():
    # Read container.py
    container_path = Path("mlserver/container.py")
    if not container_path.exists():
        print(f"Error: {container_path} not found")
        return

    with open(container_path, 'r') as f:
        container_lines = f.readlines()

    # Extract common imports (lines 1-28)
    common_imports = container_lines[0:29]

    # Create container directory
    container_dir = Path("mlserver/container")
    container_dir.mkdir(exist_ok=True)

    print(f"Refactoring container.py into {len(MODULE_STRUCTURE)} modules...")

    # Process each module
    for module_name, info in MODULE_STRUCTURE.items():
        start_line, end_line = info["lines"]
        description = info["desc"]

        print(f"  Creating {module_name} (lines {start_line}-{end_line})...")

        # Extract section
        section_lines = extract_section(container_lines, start_line, end_line)

        # Build module content
        module_content = []
        module_content.append(get_file_header(module_name, description))

        # Add imports
        if module_name != "exceptions.py":
            # Add common imports
            module_content.extend(common_imports)
            module_content.append("\n")

            # Add internal imports
            module_content.append("from .exceptions import ContainerError\n")

            # Add cross-module imports based on dependencies
            if module_name == "labels.py":
                module_content.append("from .source import _get_mlserver_git_url\n")
            elif module_name == "dockerfile.py":
                module_content.append("from .detection import detect_required_files\n")
            elif module_name == "build.py":
                module_content.append("from .labels import generate_container_labels, _generate_label_directives\n")
                module_content.append("from .source import _get_mlserver_git_url, _handle_wheel_preparation\n")
                module_content.append("from .detection import detect_required_files\n")
                module_content.append("from .dockerfile import generate_dockerfile, generate_dockerignore\n")
                module_content.append("from .config import _load_container_config, _prepare_container_metadata, _generate_container_tags\n")
            elif module_name == "registry.py":
                pass  # Minimal dependencies
            elif module_name == "config.py":
                pass  # Uses imports from main

            module_content.append("\n")

        # Add the section code
        module_content.extend(section_lines)

        # Write module file
        module_path = container_dir / module_name
        with open(module_path, 'w') as f:
            f.writelines(module_content)

    print("\n✓ Refactoring complete!")
    print(f"  Created {len(MODULE_STRUCTURE)} modules in mlserver/container/")
    print("\nNext steps:")
    print("  1. Review generated files for import issues")
    print("  2. Update container/__init__.py exports")
    print("  3. Update tests to import from mlserver.container")
    print("  4. Remove or rename old container.py")

if __name__ == "__main__":
    main()
