#!/usr/bin/env python3
"""Generate coverage badge for README."""

import json
import os
import subprocess
import sys

def get_coverage_percentage():
    """Run pytest with coverage and extract the percentage."""
    try:
        # Run pytest with coverage
        result = subprocess.run(
            ['pytest', '--cov=claude_orchestrator', '--cov-report=json', '-q'],
            capture_output=True,
            text=True
        )
        
        # Read coverage.json
        if os.path.exists('coverage.json'):
            with open('coverage.json', 'r') as f:
                data = json.load(f)
                return data['totals']['percent_covered']
        else:
            print("Coverage report not found. Running coverage...")
            return None
            
    except Exception as e:
        print(f"Error getting coverage: {e}")
        return None

def get_badge_color(percentage):
    """Get badge color based on coverage percentage."""
    if percentage >= 90:
        return 'brightgreen'
    elif percentage >= 80:
        return 'green'
    elif percentage >= 70:
        return 'yellowgreen'
    elif percentage >= 60:
        return 'yellow'
    elif percentage >= 50:
        return 'orange'
    else:
        return 'red'

def generate_badge_url(percentage):
    """Generate shields.io badge URL."""
    color = get_badge_color(percentage)
    label = 'coverage'
    message = f'{percentage:.1f}%25'  # %25 is URL encoded %
    return f"https://img.shields.io/badge/{label}-{message}-{color}"

def update_readme_badge(badge_url):
    """Update the coverage badge in README.md."""
    readme_path = 'README.md'
    
    if not os.path.exists(readme_path):
        print(f"{readme_path} not found")
        return False
    
    with open(readme_path, 'r') as f:
        content = f.read()
    
    # Look for existing coverage badge
    import re
    pattern = r'!\[Coverage\]\(https://img\.shields\.io/badge/coverage-[\d.]+%25-\w+\)'
    replacement = f'![Coverage]({badge_url})'
    
    if re.search(pattern, content):
        # Replace existing badge
        new_content = re.sub(pattern, replacement, content)
    else:
        # Add badge after the title
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('# '):
                lines.insert(i + 1, f'\n{replacement}')
                break
        new_content = '\n'.join(lines)
    
    with open(readme_path, 'w') as f:
        f.write(new_content)
    
    return True

def main():
    """Main function."""
    print("🔍 Calculating code coverage...")
    
    percentage = get_coverage_percentage()
    if percentage is None:
        print("❌ Failed to get coverage percentage")
        sys.exit(1)
    
    print(f"📊 Coverage: {percentage:.1f}%")
    
    badge_url = generate_badge_url(percentage)
    print(f"🎨 Badge URL: {badge_url}")
    
    if update_readme_badge(badge_url):
        print("✅ README.md updated with coverage badge")
    else:
        print("⚠️  Could not update README.md")
    
    # Clean up
    if os.path.exists('coverage.json'):
        os.remove('coverage.json')
    
    print(f"\n✨ Coverage badge generation complete!")

if __name__ == '__main__':
    main()