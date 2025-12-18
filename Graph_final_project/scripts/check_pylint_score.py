"""Script to check pylint score and fail if below threshold."""

import sys
import subprocess
import re


def get_pylint_score():
    """Run pylint and extract the score."""
    try:
        result = subprocess.run(
            ["pylint", "app/", "scripts/", "tests/", "--rcfile=.pylintrc", "--output-format=text"],
            capture_output=True,
            text=True,
            check=False
        )
        
        # Extract score from output
        # Pylint outputs: "Your code has been rated at X.XX/10"
        output = result.stdout + result.stderr
        match = re.search(r'rated at ([\d.]+)/10', output)
        
        if match:
            return float(match.group(1))
        
        # If no score found, print output for debugging
        print("Pylint output:")
        print(output)
        return None
        
    except FileNotFoundError:
        print("ERROR: pylint not found. Install it with: pip install pylint")
        return None
    except Exception as e:
        print(f"ERROR running pylint: {e}")
        return None


def main():
    """Main function to check pylint score."""
    threshold = 9.5
    
    print("Running pylint...")
    score = get_pylint_score()
    
    if score is None:
        print("ERROR: Could not determine pylint score")
        sys.exit(1)
    
    print(f"Pylint score: {score}/10")
    
    if score < threshold:
        print(f"ERROR: Pylint score ({score}) is below threshold ({threshold})")
        sys.exit(1)
    else:
        print(f"✓ Pylint score ({score}) meets requirement (>= {threshold})")
        sys.exit(0)


if __name__ == "__main__":
    main()

