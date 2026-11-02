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

model = ifcopenshell.open(model_path)
print("IfcOpenShell-Version:", ifcopenshell.version)
print("IFC-Schema:", model.schema)

# 2. Alle Decken (IfcSlab) holen
slabs = model.by_type("IfcSlab")
print(f"\n{len(slabs)} Decken (IfcSlab) gefunden. Die ersten 10:\n")

# 3. Für jede Decke: Name, Geschoss und Material ausgeben
for slab in slabs[:10]:
    storey = element.get_container(slab)
    material = element.get_material(slab, should_skip_usage=True)

    storey_name = storey.Name if storey else "-"
    material_name = "-"
    if material:
        material_name = getattr(material, "Name", None) or getattr(material, "LayerSetName", None) or "-"

    print(f"{slab.Name}  |  Geschoss: {storey_name}  |  Material: {material_name}")