# A2 – Use case, claim and tool idea (Group 21)

## A2a: About our group

- **Group number:** 21 (STR_26_21)
- **Focus area:** Structures
- **Role:** Analysts 
- **Python confidence:** "I am confident coding in Python" – group total score: **1 (Disagree)** 

---

## A2b: Identify claim

**Building / report:** Building 308 (Report 26-09-D-STR, DTU Building 308). 

**Exact source:** `26-09-D-STR-Anon.pdf`, Appendix 3 (pp. 271–273, 304).

**Claim to check:**

> In the structural design of the CLT floor slabs, the serviceability limit state (SLS: deflection and floor vibration) is more decisive than the ultimate limit state (ULS: bending and shear) and therefore determines the required slab thickness.

According to the report, the ULS utilisation of the timber is low, whereas deflection limits and the vibration criterion are said to govern.

**Why this claim?**
- It is *checkable*: the report gives numbers that we can reproduce and compare with our own results.
- It is *design-relevant*: if SLS governs, the slab thickness (and therefore timber volume, weight added to the existing structure and embodied carbon) is driven by stiffness, not strength. This is important for the extension of Building 308.
- It is *automatable*: the inputs (slab geometry, layers, material, floor) are mostly available in an IFC model, and the checks are formula-based (Eurocode 5 and the manufacturer's ETA).
- It fits our group's background: it is a clearly bounded calculation, which is realistic given our limited Python experience.

---

## A2c: Use case

**How would we check the claim?**
An ifcOpenShell script reads all CLT floor slabs from the IFC model, collects span, layer build-up, material and floor, and runs ULS and SLS checks for each slab with the same loads. For each slab it compares the ULS and SLS utilisation ratios and states which one governs.

**When does the claim need to be checked?**
In the design phase, when the slab thickness is chosen and while the layout/spans of the extension can still be changed. It must be repeated whenever spans, loads or the build-up change.

**What information does the claim rely on?**
- IFC model: geometry, material layers, thickness, storey, supporting elements (manufacturer type, e.g. KLH)
- Loads: self-weight (from the model), imposed and permanent loads (EN 1991-1-1 / report)
- Mechanical properties of CLT (E-modulus, shear modulus, strengths, density): manufacturer's ETA
- Standards: Eurocode 5 (EN 1995-1-1), load combinations (EN 1990)

**Phase:** Design.

**BIM purpose:** *Analyse* (Validate -> checking a design against code requirements). The tool analyses existing slabs and reports whether they comply. The "required thickness" output is a result of the analysis.

**Closest existing BIM use case:** Fall 2025 - Group 23 - "Concrete beam width checking according to Eurocode 2". Similar processes, just for another structural element. 

---

## A2d: Scope the use case

Can be seen in the repository -> A2 -> IMG 

---

## A2e: Tool idea

**Description:**
The tool is a Python script using ifcOpenShell. It:

1. Opens the IFC model and selects all `IfcSlab` elements that are CLT floors (filter by material name, e.g. "KLH", and FLOOR).
2. Extracts for each slab: thickness and layers, area and dimensions, the storey, and the supporting beams/walls to derive the **structural span**.
3. Reads mechanical properties from an external ETA data file, since they are not in the IFC model.
4. Defines the loads from Eurocode 1 / the report and builds the load combinations according to Eurocode 0.
5. Runs the **ULS checks** (bending, shear) and the **SLS checks** (deflection, floor vibration) for the *same* slab and thickness, using Eurocode 5 and the ETA for CLT.
6. Calculates the utilisation ratio for each check, determines the governing limit state, and, if a check fails, searches the next available thickness/layer build-up from the ETA.
7. Writes a summary table (CSV/Excel or console) per slab and storey: span, thickness, ULS ratio, SLS ratio, governing check, required thickness.
8. Compares the results to the claim: if the SLS ratio is higher than the ULS ratio for the slabs, the claim is confirmed.

**Business and societal value:**
- *Client / owner:* an overview of the required slab thickness per storey and span, and a traceable, repeatable check instead of one-off hand calculations.
- *Design team:* faster design iteration when spans or loads change; thicknesses can be adapted per storey, which avoids over-dimensioning.
- *Resources:* less timber, less added weight on the existing building, and lower embodied carbon; this also saves time and cost.
- *Quality:* technical verification of the slabs, and a transparent check of a claim in the report.

---

## A2f: Information requirements

| Information | Where in IFC | In the model? | ifcOpenShell approach | What we need to learn |
|---|---|---|---|---|
| Slab elements | `IfcSlab`, `PredefinedType = FLOOR` | Yes (**TODO** verify) | `model.by_type("IfcSlab")` | Filtering by type and material |
| Material / manufacturer (KLH) | `IfcMaterial.Name`, `IfcMaterialLayerSet` | Partly (name only) | `ifcopenshell.util.element.get_material()` | Reading material sets |
| Thickness | `IfcMaterialLayerSet.TotalThickness` / `IfcMaterialLayer.LayerThickness`; also `Qto_SlabBaseQuantities.Width` (depth) | Yes (**TODO** verify) | `ifcopenshell.util.element.get_psets()` | Layer set vs. quantity set |
| Panel layers | `IfcMaterialLayerSetUsage` → `IfcMaterialLayerSet` → `IfcMaterialLayer` | Yes, but grain direction of each layer is probably not modelled | `get_material()` and iterate `MaterialLayers` | How to store layer orientation (own property) |
| Slab dimensions | `Qto_SlabBaseQuantities` (Length, Width, GrossArea) | Check | `get_psets(slab, qtos_only=True)` | Difference between slab length and span |
| **Span** | Not directly. Derived from geometry and supporting elements (`IfcBeam`, `IfcWall`) | No (needs own logic) | Geometry via `ifcopenshell.geom`, bounding box / support distances | Geometry processing; the hardest part |
| Storey | `IfcRelContainedInSpatialStructure` → `IfcBuildingStorey` | Yes | `ifcopenshell.util.element.get_container()` | Spatial structure |
| Mass / self-weight | `Qto_SlabBaseQuantities.NetVolume` × density | Volume yes, density no | Volume from quantity set, density from ETA | Unit handling |
| E-modulus, shear modulus, strengths, density | `Pset_MaterialMechanical` | Likely not (**TODO** verify) | External ETA table (JSON/CSV) | Reading external data; linking by product name |
| Loads (permanent, imposed) | `IfcStructuralLoad*` is rarely modelled | Likely not; "Show Loads" in the viewer may be empty (**TODO** verify) | Input from EN 1991-1-1 or the report as parameters | Load combinations (EN 1990) |
| Support conditions | Not in the architectural model | No | Assumption: simply supported, one-way span (document it) | Structural modelling assumptions |

**Open questions for the Learning Bank (Excel in Teams):**
- How do we derive the structural span of an `IfcSlab` from its supporting elements?
- How do we model/store the layer grain direction of CLT in IFC?
- How are manufacturer data (ETA) attached to materials: custom property set or external file?
- Which CLT calculation method do we implement (gamma method, shear analogy, or the ETA's design tables)?

**Next steps:** learn Python basics, install ifcOpenShell, open the model and print all `IfcSlab` elements with their materials and property sets, to see what is actually in the model.

---

## A2g: Software licence

We choose the **MIT licence** for our tool (a `LICENSE` file is added to the repository root).

Reasoning:
- ifcOpenShell is licensed under LGPL-3.0, which allows its use as a library from MIT-licensed code.
- Blender and Bonsai are GPL. If our code imports `bpy` or is distributed as a Blender add-on, it must be released under a GPL-compatible licence (GPL-3.0). **TODO:** decide this once we know whether we use Blender only for viewing the model (then MIT is fine) or inside the script (then use GPL-3.0).

We currently work only with Python, ifcOpenShell and Blender; no licensed (commercial) software is needed.
