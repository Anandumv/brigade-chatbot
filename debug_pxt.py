import sys
import os

# Emulate run_all_tests environment
backend_dir = os.path.abspath("backend")
sys.path.insert(0, backend_dir)

print(f"PYTHONPATH: {backend_dir}")
print(f"sys.path: {sys.path}")

try:
    import pixeltable
    print(f"Imported pixeltable from: {pixeltable.__file__}")
    print(f"pixeltable is a package: {hasattr(pixeltable, '__path__')}")
    
    from pixeltable.iterators import DocumentSplitter
    print("Successfully imported DocumentSplitter")
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()

# Check for shadowing files in sys.path
for path in sys.path:
    if os.path.isdir(path):
        for item in os.listdir(path):
            if item.startswith("pixeltable") and item != "pixeltable":
                print(f"Potential shadowing item found in {path}: {item}")
