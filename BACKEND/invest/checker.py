import re

def find_orphaned_routes(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        clean_line = line.strip()
        # Look for the route decorator
        if clean_line.startswith('@routes_bp.route'):
            # Check the subsequent lines for a 'def'
            found_def = False
            # Check the next 5 lines (to account for multi-line decorators)
            for j in range(i + 1, min(i + 6, len(lines))):
                next_line = lines[j].strip()
                if next_line.startswith('def '):
                    found_def = True
                    break
                if next_line.startswith('@routes_bp.route'):
                    # Found another decorator before a def!
                    break
            
            if not found_def:
                print(f"🚨 Potential Orphan Decorator found at line {i + 1}:")
                print(f"   Code: {clean_line}")
                print("-" * 30)

if __name__ == "__main__":
    find_orphaned_routes('routes.py')
