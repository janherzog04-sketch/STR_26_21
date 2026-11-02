import ifcopenshell
from config import MODEL_PATH      # your personal path (config.py is not on GitHub)

IFC_CLASS = "IfcWall"              # which elements to count, e.g. "IfcSlab", "IfcBeam"

model = ifcopenshell.open(MODEL_PATH)
elements = model.by_type(IFC_CLASS)
print(f"{IFC_CLASS} in model: {len(elements)}")
