# A2 – Use case, claim and tool idea (Group 21)

> Draft notes: items marked **TODO** need a decision or a check by the group before submission. Delete this note and all TODOs at the end.

---

## A2a: About our group

- **Group number:** 21 (STR_26_21)
- **Focus area:** Structures
- **Role:** Analysts (**TODO:** state explicitly whether the Structures focus area keeps the manager role in this group)
- **Python confidence:** "I am confident coding in Python" – group total score: **1 (Disagree)** (**TODO:** confirm this is the sum/agreed score for the whole group, not one member's answer)

---

## A2b: Identify claim

**Building / report:** Building #2609 (Report 26-09-D-STR, DTU Building 308). Supporting evidence from Building #2608 (Report 26-08-D-STR).

**Exact source:** `26-09-D-STR-Anon.pdf`, Appendix 3 (pp. 271–273, 304) and `26-08-D-STR-Anon.pdf`, p. 17 (Section 5.4).

**Claim to check:**

> In the structural design of the CLT floor slabs of the new timber extension, the serviceability limit state (SLS: deflection and floor vibration) is more decisive than the ultimate limit state (ULS: bending and shear). In other words, the SLS utilisation ratio is higher than the ULS utilisation ratio, and SLS determines the required slab thickness.

According to the report, the ULS utilisation of the timber is low (about 21 %), whereas deflection limits (L/300–L/400) and the vibration criterion (fundamental frequency f₁ ≥ 4.5 Hz, EN 1995-1-1) are said to govern.

**Why this claim?**
- It is *checkable*: the report gives numbers (21 % ULS, deflection limits, f₁ limit) that we can reproduce and compare with our own results.
- It is *design-relevant*: if SLS governs, the slab thickness (and therefore timber volume, weight added to the existing structure and embodied carbon) is driven by stiffness, not strength. This is important for the extension, because the existing RC structure has little load reserve (see A1, issues 1, 2, 4 and 5).
- It is *automatable*: the inputs (slab geometry, layers, material, floor) are mostly available in an IFC model, and the checks are formula-based (Eurocode 5 and the manufacturer's ETA).
- It fits our group's background: it is a clearly bounded calculation, which is realistic given our limited Python experience.

---

## A2c: Use case

**How would we check the claim?**
An ifcOpenShell script reads all CLT floor slabs from the IFC model, collects span, layer build-up, material and floor, and runs ULS and SLS checks for each slab with the same loads. For each slab it compares the ULS and SLS utilisation ratios and states which one governs.

**When does the claim need to be checked?**
In the design phase, when the slab thickness is chosen and while the layout/spans of the extension can still be changed (concept and detailed design). It must be repeated whenever spans, loads or the build-up change.

**What information does the claim rely on?**
- IFC model: geometry, material layers, thickness, storey, supporting elements (manufacturer type, e.g. KLH)
- Loads: self-weight (from the model), imposed and permanent loads (EN 1991-1-1 / report)
- Mechanical properties of CLT (E-modulus, shear modulus, strengths, density): manufacturer's ETA
- Standards: Eurocode 5 (EN 1995-1-1), load combinations (EN 1990)

**Phase:** Design.

**BIM purpose:** *Analyse* (checking a design against code requirements). **TODO:** decide between *Analyse* and *Generate* (our draft said Generate). Suggested justification: the tool does not create new model content; it analyses existing slabs and reports whether they comply. The "required thickness" output is a result of the analysis, not generated geometry.

**Closest existing BIM use case:** structural analysis / design code checking in the design phase. **TODO:** name the exact use case from the course examples; if none fits, state that we define a new use case "Limit-state check of CLT floor slabs".

**Whole use case (BPMN):**

![Whole use case](IMG/diagram_use_case.svg)

Source: [`IMG/diagram_use_case.bpmn`](IMG/diagram_use_case.bpmn)

The diagram should show (**TODO**, to be redrawn):
- Lanes: *Structural engineer*, *Timber manufacturer (ETA)*, *Building owner / client*, *Tool*
- Information exchange: IFC model from architect/engineer, ETA values from manufacturer, results report to the client
- The specific IFC classes used: `IfcSlab`, `IfcMaterialLayerSet(Usage)`, `IfcBuildingStorey`, `IfcRelContainedInSpatialStructure`, `IfcBeam` (supports, for the span)

---

## A2d: Scope the use case

The part of the use case for which we develop a new script is highlighted in the diagram below. Everything else (modelling, manufacturer data, final decision) is outside the scope of the tool.

![Scope of the tool](IMG/diagram_use_case_scope.svg)

(**TODO:** the file `diagram - tool.svg` currently shows the tool process with a "CLT SLAB CHECK" frame. Rename it without spaces, e.g. `diagram_use_case_scope.svg`, and make sure the whole-use-case diagram is a separate file. Convert the frame text to a path or normal `<text>` so that it renders on GitHub.)

---

## A2e: Tool idea

**Description:**
The tool is a Python script using ifcOpenShell. It:

1. Opens the IFC model and selects all `IfcSlab` elements that are CLT floors (filter by material name, e.g. "KLH", and `PredefinedType` FLOOR).
2. Extracts for each slab: thickness and layers (`IfcMaterialLayerSet`), area and dimensions (`Qto_SlabBaseQuantities`), the storey, and the supporting beams/walls to derive the **structural span**.
3. Reads mechanical properties from an external ETA data file (JSON/CSV), since they are not in the IFC model.
4. Defines the loads from Eurocode 1 / the report and builds the load combinations according to Eurocode 0.
5. Runs the **ULS checks** (bending, shear) and the **SLS checks** (deflection, floor vibration f₁) for the *same* slab and thickness, using Eurocode 5 and the ETA method for CLT.
6. Calculates the utilisation ratio for each check, determines the governing limit state, and, if a check fails, searches the next available thickness/layer build-up from the ETA.
7. Writes a summary table (CSV/Excel or console) per slab and storey: span, thickness, ULS ratio, SLS ratio, governing check, required thickness.
8. Compares the results to the claim: if the SLS ratio is higher than the ULS ratio for the slabs, the claim is confirmed.

**Business and societal value:**
- *Client / owner:* an overview of the required slab thickness per storey and span, and a traceable, repeatable check instead of one-off hand calculations.
- *Design team:* faster design iteration when spans or loads change; thicknesses can be adapted per storey, which avoids over-dimensioning.
- *Resources:* less timber, less added weight on the existing building, and lower embodied carbon; this also saves time and cost.
- *Quality:* technical verification of the slabs, and a transparent check of a claim in the report.

**Tool BPMN:**

![Tool process](IMG/diagram_tool.svg)

Source: [`IMG/diagram_tool.bpmn`](IMG/diagram_tool.bpmn)

**TODO, corrections for the diagram:**
- Use an AND gateway to split after "Import IFC model" and to join before the checks.
- Run ULS and SLS in parallel for the same thickness, then compare the two ratios (gateway: "SLS ratio > ULS ratio?"). Do not stop at the first failing check.
- Add a task "Adjust thickness / layer build-up" in the "ratio ≥ 100 %" loop.
- Data store "Overview list": use *output* associations (the tool writes to it).
- Add the vibration check (f₁ ≥ 4.5 Hz) or remove it from the claim.
- Name the lanes separately instead of in the pool title.

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
