# A4 – CLT Floor Check: does SLS govern the slab design? (Group 21, Structures)

An IfcOpenShell tool that reads all cross-laminated timber (CLT) floor slabs of Building 308 from the IFC model,
runs the ultimate limit state (ULS) and serviceability limit state (SLS) checks for every slab and shows which
limit state governs the design.

---

## About the tool

### Problem / claim

> *"In the structural design of the CLT floor slabs, the serviceability limit state (SLS: deflection and floor
> vibration) is more decisive than the ultimate limit state (ULS: bending and shear) and therefore determines the
> required slab thickness."*

The report states that the ULS utilisation of the timber is low, while deflection limits and the vibration
criterion govern. The report checks only two representative slabs by hand (Toolbox positions **P301**, Level 2 /
KLH5/140TL, and **P401**, Roof 2 / KLH5/130TL). Our tool checks the claim for **every** CLT slab in the model and
makes the check repeatable when spans, loads or build-ups change.

### Where we found the problem

- **Report:** 26-09-D-STR (Advanced Building Design 2026, Building 308 extension), structural report
  `26-09-D-STR-Anon.pdf`
- **Claim and hand calculations:** Appendix 3, pp. 271–273 and p. 304 (KLH/SPEC Toolbox outputs P301 and P401)
- **Loads:** printed p. 8 (CLT unit weight 5.5 kN/m³, imposed and permanent loads), pp. 10–13 (snow and wind)
- **IFC model:** `26-09-D-STR.ifc` (IFC4X3, Revit 2026 export) – *not* part of this repository

The use case and the BPMN diagrams are described in [A2](../A2/README.md) (`A2/IMG/`).

### Description of the tool

The tool follows the steps of our BPMN diagram from A2e:

| Step | What happens | File |
|---|---|---|
| 1 | Open the IFC model (path from `config.py`) | `main.py` → `open_model()` |
| 2 | Select all CLT slabs (`"KLH"` in `IfcSlab.Name`) and read type, storey, layer build-up, thickness, dimensions and area. Span = short side of the slab (the panels span 3.2 m between steel beams). Filler strips < 1 m are ignored. | `main.py` → `get_clt_slabs()` |
| 3 | Add the CLT material properties from the KLH ETA-06/0138 (2017) and compute the effective section properties (EI_eff with the γ-method, W_eff) | `materials.py` |
| 4 | Assign loads per slab (self-weight from the actual thickness, additional permanent, imposed, snow, wind) and build the load combinations (EN 1990, DK NA) | `loads_2.py` |
| 5 | **ULS:** bending, longitudinal shear and rolling shear (EN 1995-1-1, ETA) for every slab, plus a reproduction of the report's Toolbox results P301/P401 for validation | `checks_uls_f.py` |
| 6 | **SLS:** instantaneous and final deflection (incl. creep, k_def) against the adopted limits (L/400, L/250 for wind) and a floor-vibration diagnostic (natural frequency, footfall acceleration) | `main copy.py` → `run_sls_workflow()` |
| 7 | Write CSV result tables per slab (utilisation in % for every check) to `output/` | all modules |
| 8 | Compare ULS and SLS utilisation per slab → governing limit state → claim confirmed or not | `output/uls_summary.csv` vs. `output/slab_sls_summary.csv` |

**Main outputs (`output/`):**

| File | Content |
|---|---|
| `uls_summary.csv`, `uls_combinations.csv`, `uls_details.json` | ULS utilisation (bending, longitudinal shear, rolling shear) per slab and load combination |
| `toolbox_comparison.csv` | Our ULS results vs. the report's Toolbox values for P301 / P401 |
| `slab_characteristic_loads.csv`, `slab_sls_combinations.csv` | Loads and SLS combinations per slab |
| `slab_deflection_checks.csv`, `slab_deflection_governing.csv` | Deflection per check, limit and utilisation |
| `floor_vibration_scenarios.csv`, `floor_vibration_governing.csv` | Vibration diagnostic (f₁, acceleration) |
| `slab_sls_summary.csv` | One line per slab: governing deflection check, utilisation, vibration status |

**Scope and limitations** (also written into the CSV files):

- One-way, simply supported strips; symmetric five-layer KLH panels only.
- The span is taken from the IFC geometry (short side). The supports themselves are not read from the model.
- The vibration part is a **diagnostic** single-mode model, not a code verification (DS/EN 1995-1-1 / P354).
- Roof uplift, local wind zones, concentrated loads, notches and connections are not checked.

### Instructions to run the tool

**Requirements:** Python 3.10+, packages in `requirements.txt` (`ifcopenshell`, `pandas`, `openpyxl`; `numpy`
comes with pandas).

1. **Clone** the repository and open the `A4/` folder in VS Code.
2. **Install** the packages:
   ```bash
   pip install -r requirements.txt
   ```
3. **Set the model path:** copy `config_example.py` to `config.py` and enter the path to the IFC model on your
   own computer. `config.py` and `*.ifc` are in `.gitignore` and are never uploaded.
   ```python
   MODEL_PATH = r"C:\Users\YourName\DTU\26-09-D-STR.ifc"
   ```
4. **Check the extraction** – prints a table of all CLT slabs (type, storey, layers, span):
   ```bash
   python main.py
   ```
5. **Run the ULS checks** for all slabs (reads the slabs via `main.py`):
   ```bash
   python checks_uls_f.py --main main.py
   ```
   Options: `--ifc <path>` reads the IFC file directly, `--out <folder>` changes the output folder,
   `--toolbox` runs only the validation against the report cases P301 / P401.
6. **Run the SLS checks** (deflection + vibration diagnostic):
   ```bash
   python "main copy.py"
   ```
7. **Read the results** in `output/`: compare the ULS utilisation (`uls_summary.csv`) with the SLS utilisation
   (`slab_sls_summary.csv`) per slab. If the SLS utilisation is higher for the slabs, the claim is confirmed.

---

## Advanced Building Design

### In which stage (A, B, C or D) is the tool useful?

- **Stage B – design and analyse different options:** main use. When the structural system is chosen, the tool
  shows for each slab type and span whether strength or stiffness governs. This tells the team which CLT
  build-up is needed and whether a thinner panel or a different beam spacing is possible.
- **Stage C – integrate the building systems:** re-run whenever the model changes (new spans, openings, changed
  loads or slab types) to check that all slabs still work after coordination with the other disciplines.
- **Stage D – detail and communicate the final design:** verify the claims and the hand calculations in the final
  structural report for *all* slabs, not only the two representative positions. This is how we used it for
  Building 308.

Stage A (client needs and strategies) has no detailed model yet, so the tool is not useful there.

### Which subjects might use it?

| Subject | Use |
|---|---|
| **Structures** | Main user: verification of the CLT slabs, choice of slab build-up and span |
| **Architecture** | Floor build-up height and span/beam layout depend on the governing check |
| **Materials / LCA** | A thinner panel means less timber volume and lower embodied CO₂ |
| **PM / ICT** | Fast, repeatable check of a report claim; status of all slabs in one table |

### What information is required in the model?

| Information | Where in IFC | Required |
|---|---|---|
| CLT slabs | `IfcSlab` with `"KLH"` in `Name` | yes |
| Slab type (e.g. `KLH5/140TL`) | `IfcSlabType.Name` (`Floor:KLH5/140TL`) | yes – selects the build-up from the ETA |
| Storey | `IfcBuildingStorey` via `IfcRelContainedInSpatialStructure` | yes – decides floor or roof loads |
| Layer build-up and thickness | `IfcMaterialLayerSetUsage` → `IfcMaterialLayerSet` → `IfcMaterialLayer.LayerThickness` | yes – five layers |
| Layer direction | `IfcMaterialLayer.Material.Name` (`Wood - hor` / `Wood - ver`) | recommended |
| Length, width (→ span) | `Qto_SlabBaseQuantities.Length` / `.Width` | yes |
| Area | `Qto_SlabBaseQuantities.NetArea` | yes |
| Unique ID | `GlobalId` | yes – unique for every slab |
| Length unit | `IfcUnitAssignment` (here mm) | yes – the tool converts to mm |

**Not in the model – supplied by the tool:**

- CLT material properties (E₀, E₉₀, G, strengths, k_def): KLH ETA-06/0138, 20.02.2017 → `materials.py`
- Loads (imposed 5.0 kN/m², additional permanent 1.2 kN/m², snow 0.8 kN/m², wind) and partial factors: report
  p. 8–13, EN 1990/1991 with DK NA → `loads_2.py`
- Supports: there are no `IfcStructural*` objects in the model; simple supports at the short span are assumed.
