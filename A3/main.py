"""
=====================================================================================
 CLT FLOOR CHECK – Is the slab design governed by SLS instead of ULS?
=====================================================================================
 Course:   Advanced BIM (DTU), Group 21 – Structures
 Claim:    "For the CLT floor slabs of Building 308, the serviceability limit state
            (deflection, vibration) governs the slab thickness, not the ultimate
            limit state (bending, shear)."
 Source:   Report 26-09-D-STR, Appendix 3 (pp. 271-273, 304)

 What this script does (same order as our BPMN diagram):
   1. Open the IFC model
   2. Extract all KLH (CLT) floor slabs: type, storey, layers, span
   3. Load material properties (from the KLH ETA – not in the IFC model)
   4. Define loads and load combinations (EN 1990 / EN 1991)
   5. ULS checks: bending and shear (EN 1995-1-1)
   6. SLS checks: deflection and vibration (EN 1995-1-1)
   7. Find the governing check; if a slab fails, find the next thicker build-up
   8. Write a summary table and give a verdict on the claim

 How to run:
   - Create A3/config.py with:  MODEL_PATH = r"C:\\path\\to\\26-09-D-STR.ifc"
   - Run this file in VS Code (triangle top right) or: python A3/main.py

 Units used in the calculations (consistent, no conversion needed):
   length = mm, force = N, stress = N/mm² (= MPa)
   line load on a 1 m wide strip: 1 kN/m² × 1 m = 1 kN/m = 1 N/mm

 IMPORTANT: All values marked "PLACEHOLDER" must be checked against the
 KLH ETA and the report before we use the results!
=====================================================================================
"""

# ===================================================================================
# 0. IMPORTS
# ===================================================================================
import math
from pathlib import Path

import ifcopenshell
import ifcopenshell.util.element as element
import ifcopenshell.util.unit as unit
import pandas as pd

from config import MODEL_PATH


# ===================================================================================
# 1. SETTINGS
# ===================================================================================
 
SLAB_NAME_FILTER = "KLH"       # a slab is a CLT slab if its name contains this text
MIN_SPAN_MM = 1000             # smaller pieces are filler strips -> ignored
 
 
# ===================================================================================
# 2. OPEN THE MODEL
# ===================================================================================
 
def open_model(path_text):
    """Open the IFC file and return the model. Stops with a clear message if the file is missing."""
    model_path = Path(path_text)
    if not model_path.is_file():
        raise FileNotFoundError(f"No file found at {model_path}!")
    return ifcopenshell.open(model_path)
 
 
# ===================================================================================
# 3. READ THE DATA OF ONE SLAB
# -----------------------------------------------------------------------------------
# Small helper functions, one for each piece of information.
# ===================================================================================
 
def get_type_name(slab):
    """Type name without the Revit prefix: 'Floor:KLH5/140TL' -> 'KLH5/140TL'."""
    slab_type = element.get_type(slab)
    return slab_type.Name.split(":")[-1] if slab_type else "unknown"
 
 
def get_storey_name(slab):
    """Name of the storey that contains the slab, e.g. 'Level 1'."""
    storey = element.get_container(slab)
    return storey.Name if storey else "unknown"
 
 
def get_layers(slab, mm_per_unit):
    """
    Layer build-up from top to bottom as a list of (thickness_mm, material_name).
    Path in IFC: IfcMaterialLayerSetUsage -> IfcMaterialLayerSet -> IfcMaterialLayer
    """
    layer_set = element.get_material(slab, should_skip_usage=True)
    if layer_set is None or not layer_set.is_a("IfcMaterialLayerSet"):
        return []
    return [(layer.LayerThickness * mm_per_unit, layer.Material.Name)
            for layer in layer_set.MaterialLayers]
 
 
def get_dimensions(slab, mm_per_unit):
    """
    Long side, short side (mm) and area (m²) from the quantity set 'Qto_SlabBaseQuantities'.
    Note: 'Length' is NOT always the longer side in this model, so we sort them ourselves.
    """
    qto = element.get_psets(slab).get("Qto_SlabBaseQuantities", {})
    side_a = qto.get("Length", 0) * mm_per_unit
    side_b = qto.get("Width", 0) * mm_per_unit
    return {
        "long_mm": max(side_a, side_b),
        "short_mm": min(side_a, side_b),
        "area_m2": qto.get("NetArea", 0),
    }
 
 
# ===================================================================================
# 4. MAIN FUNCTION OF THIS MODULE: ALL CLT SLABS
# ===================================================================================
 
def get_clt_slabs(model):
    """Collect all KLH floor slabs with their data. Returns a list of dictionaries."""
    mm_per_unit = unit.calculate_unit_scale(model) * 1000      # model unit -> mm (here 1.0)
 
    slabs = []
    for slab in model.by_type("IfcSlab"):
 
        # --- Filter: only KLH slabs ------------------------------------------------
        if SLAB_NAME_FILTER not in (slab.Name or ""):
            continue
 
        # --- Read the data ---------------------------------------------------------
        layers = get_layers(slab, mm_per_unit)
        dimensions = get_dimensions(slab, mm_per_unit)
 
        # --- Span = short side; skip filler strips ---------------------------------
        span_mm = dimensions["short_mm"]
        if span_mm < MIN_SPAN_MM:
            continue
 
        slabs.append({
            "id": slab.id(),
            "guid": slab.GlobalId,
            "name": slab.Name,
            "type": get_type_name(slab),
            "storey": get_storey_name(slab),
            "layers": layers,
            "thickness_mm": sum(t for t, _ in layers),
            "length_mm": dimensions["long_mm"],
            "span_mm": span_mm,
            "area_m2": dimensions["area_m2"],
        })
 
    return slabs
 
 
# ===================================================================================
# 5. TEST: RUN THIS FILE ON ITS OWN
# -----------------------------------------------------------------------------------
# This part only runs when you start ifc_extract.py directly,
# not when main.py imports the module.
# ===================================================================================
 
if __name__ == "__main__":
    from collections import Counter
 
    from config import MODEL_PATH
 
    model = open_model(MODEL_PATH)
    print(f"Model: {Path(MODEL_PATH).name} | schema {model.schema}\n")
 
    slabs = get_clt_slabs(model)
 
    # --- Table of all slabs --------------------------------------------------------
    header = (f"{'ID':>6} | {'Type':<12} | {'Storey':<8} | {'t [mm]':>6} | "
              f"{'Layers [mm]':<16} | {'Length [m]':>10} | {'Span [m]':>8}")
    print(header)
    print("-" * len(header))
    for s in slabs:
        layers_text = "/".join(f"{t:.0f}" for t, _ in s["layers"])
        print(f"{s['id']:>6} | {s['type']:<12} | {s['storey']:<8} | {s['thickness_mm']:>6.0f} | "
              f"{layers_text:<16} | {s['length_mm'] / 1000:>10.2f} | {s['span_mm'] / 1000:>8.2f}")
 
    # --- Short summary -------------------------------------------------------------
    print(f"\n{len(slabs)} CLT slabs (filler strips < {MIN_SPAN_MM} mm ignored)")
    for (storey, slab_type), count in sorted(Counter((s["storey"], s["type"]) for s in slabs).items()):
        print(f"  {storey:<8} {slab_type:<12} {count:>3} slabs")