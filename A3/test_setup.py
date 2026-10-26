from pathlib import Path

import ifcopenshell
import ifcopenshell.util.element as element

from config import MODEL_PATH

# 1. Modell öffnen
model_path = Path(MODEL_PATH)
if not model_path.is_file():
    raise FileNotFoundError(f"Keine Datei gefunden unter {model_path}!")

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