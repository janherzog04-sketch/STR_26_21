"""check_setup.py - run once after cloning:  python check_setup.py"""
import sys
from pathlib import Path


def fail(message):
    sys.exit(f"[FAIL] {message}")


print(f"[ OK ] Python {sys.version.split()[0]}")

try:
    import ifcopenshell
except ImportError:
    fail("IfcOpenShell missing -> pip install -r requirements.txt")
print(f"[ OK ] IfcOpenShell {ifcopenshell.version}")

try:
    from config import MODEL_PATH
except ImportError:
    fail("config.py missing -> copy config_example.py to config.py and add your model path")
print("[ OK ] config.py found")

if not Path(MODEL_PATH).is_file():
    fail(f"No model at {MODEL_PATH} -> check the path in config.py")

model = ifcopenshell.open(MODEL_PATH)
print(f"[ OK ] Model opened: {model.schema}, {len(model.by_type('IfcProduct'))} products")
print("\nAll good - you can run main.py")