import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from state import load, validate

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state", "habits.json")
    errs = validate(load(path))
    if errs:
        print("\n".join(errs)); sys.exit(1)
    print("OK")

if __name__ == "__main__":
    main()
