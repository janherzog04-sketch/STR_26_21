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

# ===================================================================================
# 6. SLS SETTINGS: LOADS, COMBINATIONS AND SECTION PROPERTIES
# ===================================================================================
# All text and code before this heading are retained from the supplied first part.
# CURRENT SCOPE: deformation + adopted deflection criteria; diagnostic vibration only.
# The opening assignment description is retained verbatim but ULS/thickness iteration
# are NOT implemented by the appended code.

import numpy as np

CLT_UNIT_WEIGHT_KN_M3 = 5.5
ADDITIONAL_PERMANENT_LOAD_KN_M2 = 1.2
FLOOR_IMPOSED_LOAD_KN_M2 = 5.0
ROOF_SNOW_LOAD_KN_M2 = 0.8
ROOF_WIND_DOWN_KN_M2 = 0.29
STOREY_LOAD_CATEGORY = {"Level 1": "floor", "Level 2": "floor", "Roof 2": "roof"}
K_DEF = 0.8
PSI2 = {"Q": 0.5, "S": 0.0, "W": 0.0}
CAMBER_MM = 0.0
SECTION_PROPERTIES = {
    "KLH5/130TL": {"thickness_mm": 130., "EI_Nmm2": 1.880e12,
                   "Ks_N": 12.400e6, "EI_y_Nmm2": 0.316e12},
    "KLH5/140TL": {"thickness_mm": 140., "EI_Nmm2": 2.540e12,
                   "Ks_N": 12.700e6, "EI_y_Nmm2": 0.208e12},
}
IFC_TYPE_TO_SECTION = {
    "KLH5/130TL": "KLH5/130TL", "KLH5/130TL 2": "KLH5/130TL",
    "KLH5/140TL": "KLH5/140TL",
}
# Report Table 3.8 Category C. Factors: G, Q, snow, downward wind.
SLS_COMBINATIONS = {
    "LC11": ("characteristic", (1., 1., 0., 0.)),
    "LC12": ("characteristic", (1., 1., .3, .3)),
    "LC13": ("characteristic", (1., .6, 0., 1.)),
    "LC14": ("characteristic", (1., .6, 1., .3)),
    "LC21": ("frequent", (1., .6, 0., 0.)),
    "LC22": ("frequent", (1., .6, 0., 0.)),
    "LC23": ("frequent", (1., .5, 0., .2)),
    "LC24": ("frequent", (1., .5, .2, 0.)),
    "LC31": ("quasi_permanent", (1., .5, 0., 0.)),
    "LC32": ("quasi_permanent", (1., .5, 0., 0.)),
    "LC33": ("quasi_permanent", (1., .5, 0., 0.)),
    "LC34": ("quasi_permanent", (1., .5, 0., 0.)),
}
ACTION_NAMES = ("G", "Q", "S", "W")
ACTION_LABELS = {"G": "g", "Q": "q", "S": "snow", "W": "wind"}
DEFLECTION_DIVISORS = {
    "permanent_final": 400., "floor_imposed_instantaneous": 400.,
    "roof_snow_instantaneous": 400., "roof_wind_instantaneous": 250.,
}
VIBRATION_CONFIG = {
    "floor_width_m": 3.0,
    "mass_fractions": (0., .10, .20), "damping_ratios": (.02, .03),
    "walking_min_hz": 1.8, "walking_max_hz": 2.2, "walking_step_hz": .01,
    "additional_impulse_paces_hz": (1.5,), "walker_weight_N": 746.,
    "acceleration_reference_m_s2": .002*9.81,
    "impulse_samples_per_step": 4097,
}
VIBRATION_SCOPE = (
    "DIAGNOSTIC ONLY: unvalidated single-mode strip/impulse model and "
    "raw-acceleration comparison, not a DS/EN/P354 utilisation or verdict. "
    "Rigid simple supports, assumed 3 m responding width, no transverse "
    "localisation, support-beam modes, rotary inertia, machinery, multiple "
    "walkers or rhythmic activity. 1.5 Hz is impulse sensitivity only. "
    "The maximum is only over the evaluated diagnostic scenarios."
)

# ===================================================================================
# 7. VALIDATION AND EXPORT HELPERS
# ===================================================================================
def checked_number(value, label, positive=False):
    value = float(value)
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(f"Invalid {label}: {value}")
    return value


def export_csv(dataframe, filename, output_folder=None):
    if dataframe.empty:
        raise ValueError(f"No data to export: {filename}")
    folder = Path(output_folder) if output_folder is not None else Path(__file__).resolve().parent / "output"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename
    dataframe.to_csv(target, index=False, encoding="utf-8-sig", na_rep="")
    print(f"Saved: {target}")
    return target


def slab_identity(slab):
    return {k: slab[k] for k in (
        "id", "guid", "type", "storey", "thickness_mm", "span_mm", "load_category"
    )}


def section_for_slab(slab):
    if slab["type"] not in IFC_TYPE_TO_SECTION:
        raise ValueError(f"Slab {slab['id']}: unmapped type {slab['type']!r}")
    name = IFC_TYPE_TO_SECTION[slab["type"]]
    props = SECTION_PROPERTIES[name]
    thickness = checked_number(slab["thickness_mm"], "thickness", True)
    if not math.isclose(thickness, props["thickness_mm"], rel_tol=0., abs_tol=.1):
        raise ValueError(f"Slab {slab['id']}: thickness does not match {name}")
    return name, props

# ===================================================================================
# 8. CHARACTERISTIC LOAD ASSIGNMENTS
# ===================================================================================
def assign_loads(raw_slabs):
    loaded = []
    for slab in raw_slabs:
        if slab["storey"] not in STOREY_LOAD_CATEGORY:
            raise ValueError(f"Unassigned storey {slab['storey']!r}")
        category = STOREY_LOAD_CATEGORY[slab["storey"]]
        if category not in ("floor", "roof"):
            raise ValueError(f"Invalid load category {category!r}")
        section_for_slab(slab)
        t = checked_number(slab["thickness_mm"], "thickness", True)
        self_weight = checked_number(CLT_UNIT_WEIGHT_KN_M3, "unit weight", True)*t/1000
        additional = checked_number(ADDITIONAL_PERMANENT_LOAD_KN_M2, "additional permanent")
        loaded.append({**slab, "load_category": category,
            "g_clt_k_kn_m2": self_weight, "g_additional_k_kn_m2": additional,
            "g_total_k_kn_m2": self_weight+additional,
            "q_imposed_k_kn_m2": checked_number(FLOOR_IMPOSED_LOAD_KN_M2, "imposed") if category == "floor" else 0.,
            "s_k_kn_m2": checked_number(ROOF_SNOW_LOAD_KN_M2, "snow") if category == "roof" else 0.,
            "w_down_k_kn_m2": checked_number(ROOF_WIND_DOWN_KN_M2, "wind") if category == "roof" else 0.})
    return loaded


def get_actions(slab):
    fields = ("g_total_k_kn_m2", "q_imposed_k_kn_m2", "s_k_kn_m2", "w_down_k_kn_m2")
    return {a: checked_number(slab[k], f"action {a}") for a,k in zip(ACTION_NAMES, fields)}


def export_loads(loaded_slabs, output_folder=None):
    fields = list(slab_identity(loaded_slabs[0])) + [
        "g_clt_k_kn_m2", "g_additional_k_kn_m2", "g_total_k_kn_m2",
        "q_imposed_k_kn_m2", "s_k_kn_m2", "w_down_k_kn_m2"]
    df = pd.DataFrame(loaded_slabs)[fields]
    if df.isna().any().any():
        raise ValueError("Missing characteristic-load data")
    export_csv(df, "slab_characteristic_loads.csv", output_folder)
    return df

# ===================================================================================
# 9. SLS LOAD COMBINATIONS
# ===================================================================================
def calculate_sls_combinations(loaded_slabs, output_folder=None):
    rows = []
    for slab in loaded_slabs:
        actions = get_actions(slab)
        for case, (family, factors) in SLS_COMBINATIONS.items():
            parts = {a: actions[a]*f for a,f in zip(ACTION_NAMES, factors)}
            rows.append({**slab_identity(slab), "case": case, "family": family,
                **{f"factor_{a}": f for a,f in zip(ACTION_NAMES, factors)},
                **{f"{a}_contribution_kn_m2": x for a,x in parts.items()},
                "total_sls_kn_m2": sum(parts.values()), "basis": "Report Table 3.8 Category C"})
    df = pd.DataFrame(rows)
    export_csv(df, "slab_sls_combinations.csv", output_folder)
    return df

# ===================================================================================
# 10. INSTANTANEOUS DEFORMATION AND CREEP
# ===================================================================================
def calculate_instantaneous_deflections(slab):
    name, props = section_for_slab(slab)
    L = checked_number(slab["span_mm"], "span", True)
    EI = checked_number(props["EI_Nmm2"], "EI", True)
    Ks = checked_number(props["Ks_N"], "Ks", True)
    def response(surface_load):
        q = checked_number(surface_load, "surface load")
        bending = 5*q*L**4/(384*EI)
        shear = q*L**2/(8*Ks)
        return {"bending": bending, "shear": shear, "total": bending+shear}
    return {"section": name, "EI_Nmm2": EI, "Ks_N": Ks,
        "components": {a: response(v) for a,v in get_actions(slab).items()},
        "clt": response(slab["g_clt_k_kn_m2"]),
        "additional": response(slab["g_additional_k_kn_m2"])}


def calculate_sls_deformations(loaded_slabs):
    kdef = checked_number(K_DEF, "k_def")
    camber = checked_number(CAMBER_MM, "camber")
    if any(checked_number(PSI2[a], f"psi2 {a}") > 1 for a in ("Q","S","W")):
        raise ValueError("psi2 must be within 0-1")
    rows = []
    for slab in loaded_slabs:
        inst = calculate_instantaneous_deflections(slab)
        c = inst["components"]
        creep = {a: kdef*c[a]["total"]*(1 if a == "G" else PSI2[a]) for a in ACTION_NAMES}
        for case, (family, factors) in SLS_COMBINATIONS.items():
            bending = sum(f*c[a]["bending"] for a,f in zip(ACTION_NAMES, factors))
            shear = sum(f*c[a]["shear"] for a,f in zip(ACTION_NAMES, factors))
            wc = sum(creep.values()) if family == "characteristic" else None
            final = bending+shear+wc if wc is not None else None
            row = {**slab_identity(slab), "section": inst["section"],
                "EI_Nmm2": inst["EI_Nmm2"], "Ks_N": inst["Ks_N"],
                "case": case, "family": family, "k_def": kdef,
                "w_clt_inst_mm": inst["clt"]["total"],
                "w_additional_inst_mm": inst["additional"]["total"],
                "w_g_final_mm": c["G"]["total"]+creep["G"],
                "w_case_bending_inst_mm": bending, "w_case_shear_inst_mm": shear,
                "w_case_inst_mm": bending+shear, "w_case_creep_mm": wc,
                "w_case_final_mm": final, "camber_mm": camber,
                "w_case_net_final_mm": final-camber if final is not None else None,
                "deformation_model": "BENDING_PLUS_SHEAR"}
            for a, label in ACTION_LABELS.items():
                for part in ("bending","shear"):
                    row[f"w_{label}_{part}_inst_mm"] = c[a][part]
                row[f"w_{label}_inst_mm"] = c[a]["total"]
                row[f"w_{label}_creep_mm"] = creep[a]
            rows.append(row)
    return pd.DataFrame(rows)

# ===================================================================================
# 11. ADOPTED DEFLECTION ACCEPTANCE CHECKS
# ===================================================================================
def calculate_deflection_checks(loaded_slabs, output_folder=None):
    if not math.isclose(float(CAMBER_MM), 0., rel_tol=0., abs_tol=1e-9):
        raise ValueError("Only no-camber acceptance limits implemented")
    kdef = checked_number(K_DEF, "k_def")
    rows = []
    for slab in loaded_slabs:
        c = calculate_instantaneous_deflections(slab)["components"]
        L = checked_number(slab["span_mm"], "span", True)
        checks = [("permanent_final", "G: self-weight + additional permanent",
                   c["G"]["total"]*(1+kdef), DEFLECTION_DIVISORS["permanent_final"])]
        if slab["load_category"] == "floor":
            checks.append(("floor_imposed_instantaneous", "Characteristic imposed Qk",
                           c["Q"]["total"], DEFLECTION_DIVISORS["floor_imposed_instantaneous"]))
        elif slab["load_category"] == "roof":
            checks.extend([
                ("roof_snow_instantaneous", "Characteristic snow Sk", c["S"]["total"],
                 DEFLECTION_DIVISORS["roof_snow_instantaneous"]),
                ("roof_wind_instantaneous", "Characteristic downward wind Wk", c["W"]["total"],
                 DEFLECTION_DIVISORS["roof_wind_instantaneous"])])
        else:
            raise ValueError("Unknown load category")
        for name, action, calculated, divisor in checks:
            limit = L/checked_number(divisor, "limit divisor", True)
            util = calculated/limit
            rows.append({**slab_identity(slab), "check": name, "action": action,
                "calculated_deflection_mm": calculated, "limit_span_divisor": divisor,
                "limit_deflection_mm": limit, "utilisation_ratio": util,
                "utilisation_percent": 100*util,
                "check_status": "PASS_ADOPTED_LIMIT" if util <= 1 else "FAIL_ADOPTED_LIMIT",
                "criterion_basis": "Adopted DK NA:2019 Table 7.2 example criterion", "k_def": kdef})
    detailed = pd.DataFrame(rows)
    if detailed.empty:
        raise ValueError("No deflection checks")
    indices = detailed.groupby("guid")["utilisation_ratio"].idxmax()
    summary = detailed.loc[indices].copy().reset_index(drop=True).rename(columns={
        "check": "governing_deflection_check", "check_status": "deflection_status"})
    export_csv(detailed, "slab_deflection_checks.csv", output_folder)
    export_csv(summary, "slab_deflection_governing.csv", output_folder)
    return detailed, summary

# ===================================================================================
# 12. DIAGNOSTIC VIBRATION MODEL — NOT A DS/EN ACCEPTANCE CHECK
# ===================================================================================
def harmonic_coefficients(pace):
    if not 1.8 <= pace <= 2.2:
        raise ValueError("Harmonic pace must lie within 1.8-2.2 Hz")
    return (.436*(pace-.95), .006*(2*pace+12.3),
            .007*(3*pace+5.2), .007*(4*pace+2.0))


def strip_mode(L, width, D, S, mass_area):
    f_bending = math.pi/(2*L**2)*math.sqrt(D/mass_area)
    f1 = f_bending/math.sqrt(1+math.pi**2*D/(S*L**2))
    return f1, mass_area*width*L/2, f_bending


def harmonic_response(f1, modal_mass, damping, pace, weight):
    amplitudes = []
    for h, alpha in enumerate(harmonic_coefficients(pace), 1):
        r = h*pace/f1
        factor = r*r/math.sqrt((1-r*r)**2+(2*damping*r)**2)
        amplitudes.append(weight*alpha/modal_mass*factor)
    return math.sqrt(sum(a*a for a in amplitudes)/2), sum(abs(a) for a in amplitudes)


def impulse_response(f1, modal_mass, damping, pace, weight, samples):
    # Retained experimental model from the previous version, not validated for acceptance.
    impulse = 60*pace**1.43/f1**1.3*weight/700
    v0 = impulse/modal_mass
    omega = 2*math.pi*f1
    decay = damping*omega
    wd = omega*math.sqrt(1-damping*damping)
    t = np.linspace(0., 1/pace, samples)
    exponential = np.exp(-decay*t)
    velocity = v0*exponential*(np.cos(wd*t)-decay/wd*np.sin(wd*t))
    acceleration = v0*exponential*((decay**2-wd**2)/wd*np.sin(wd*t)-2*decay*np.cos(wd*t))
    def mean(y):
        return float(np.sum((y[:-1]+y[1:])*np.diff(t)/2)*pace)
    std = math.sqrt(max(0., mean(acceleration**2)-mean(acceleration)**2))
    return std, float(np.max(np.abs(acceleration))), math.sqrt(mean(velocity**2)), impulse


def calculate_floor_vibration(loaded_slabs, output_folder=None, config=None):
    cfg = dict(VIBRATION_CONFIG if config is None else config)
    width = checked_number(cfg["floor_width_m"], "width", True)
    weight = checked_number(cfg["walker_weight_N"], "walker weight", True)
    reference = checked_number(cfg["acceleration_reference_m_s2"], "acceleration reference", True)
    lo, hi = cfg["walking_min_hz"], cfg["walking_max_hz"]
    if not 1.8 <= lo <= hi <= 2.2:
        raise ValueError("Harmonic range must lie within 1.8-2.2 Hz")
    step = checked_number(cfg["walking_step_hz"], "pace step", True)
    samples = int(cfg["impulse_samples_per_step"])
    if samples < 1001:
        raise ValueError("Use at least 1001 impulse samples")
    fractions = tuple(checked_number(x, "mass fraction") for x in cfg["mass_fractions"])
    dampings = tuple(checked_number(x, "damping", True) for x in cfg["damping_ratios"])
    if not fractions or not dampings or any(x > 1 for x in fractions) or any(x >= 1 for x in dampings):
        raise ValueError("Invalid mass/damping scenarios")
    extra = tuple(checked_number(x, "extra impulse pace", True) for x in cfg["additional_impulse_paces_hz"])
    base_paces = np.linspace(lo, hi, max(2, math.ceil((hi-lo)/step)+1))
    rows = []
    for slab in loaded_slabs:
        if slab["load_category"] != "floor":
            continue
        name, props = section_for_slab(slab)
        L = checked_number(slab["span_mm"], "span", True)/1000
        D = checked_number(props["EI_Nmm2"], "EI", True)/1e6
        S = checked_number(props["Ks_N"], "Ks", True)
        actions = get_actions(slab)
        for fraction in fractions:
            mass_area = checked_number((actions["G"]+fraction*actions["Q"])*1000/9.81, "mass", True)
            f1, modal_mass, f_bending = strip_mode(L, width, D, S, mass_area)
            candidates = list(base_paces)+[f1/h for h in range(1,5) if lo <= f1/h <= hi]
            harmonic_paces = sorted(set(round(x,10) for x in candidates))
            impulse_paces = sorted(set(harmonic_paces+list(extra)))
            for damping in dampings:
                common = {**slab_identity(slab), "section": name, "width_m": width,
                    "mass_fraction": fraction, "mass_kg_m2": mass_area,
                    "modal_mass_kg": modal_mass, "damping_ratio": damping,
                    "f1_hz": f1, "f1_bending_only_hz": f_bending,
                    "acceleration_reference_m_s2": reference}
                for pace in harmonic_paces:
                    rms, peak = harmonic_response(f1, modal_mass, damping, pace, weight)
                    rows.append({**common, "response": "harmonic_steady_state", "pace_hz": pace,
                        "a_std_m_s2": rms, "a_peak_or_upper_bound_m_s2": peak,
                        "velocity_rms_m_s": None, "design_impulse_Ns": None, "regime_valid": True})
                for pace in impulse_paces:
                    std, peak, vrms, impulse = impulse_response(f1, modal_mass, damping, pace, weight, samples)
                    rows.append({**common, "response": "isolated_footfall_impulse", "pace_hz": pace,
                        "a_std_m_s2": std, "a_peak_or_upper_bound_m_s2": peak,
                        "velocity_rms_m_s": vrms, "design_impulse_Ns": impulse,
                        "regime_valid": f1 > 4*pace})
    scenarios = pd.DataFrame(rows)
    if scenarios.empty:
        print("No floor slabs selected for diagnostic walking vibration")
        return scenarios, pd.DataFrame()
    scenarios["diagnostic_ratio_percent"] = 100*scenarios["a_std_m_s2"]/reference
    scenarios["comparison_status"] = np.where(scenarios["regime_valid"],
        "UNVALIDATED_DIAGNOSTIC_ONLY", "OUTSIDE_ISOLATED_IMPULSE_REGIME")
    scenarios["ratio_basis"] = "RAW_ACCELERATION_TO_ADOPTED_REFERENCE_NOT_CODE_UTILISATION"
    scenarios["scope_note"] = VIBRATION_SCOPE
    applicable = scenarios.loc[scenarios["regime_valid"]]
    indices = applicable.groupby("guid")["diagnostic_ratio_percent"].idxmax()
    governing = applicable.loc[indices].copy().reset_index(drop=True)
    export_csv(scenarios, "floor_vibration_scenarios.csv", output_folder)
    export_csv(governing, "floor_vibration_governing.csv", output_folder)
    return scenarios, governing

# ===================================================================================
# 13. WORKFLOW AND SUMMARY
# ===================================================================================
def run_sls_workflow(raw_slabs, output_folder=None):
    if not raw_slabs:
        raise ValueError("No KLH slabs extracted")
    guids = [s["guid"] for s in raw_slabs]
    if len(set(guids)) != len(guids):
        raise ValueError("Duplicate slab GUIDs")
    loaded = assign_loads(raw_slabs)
    loads = export_loads(loaded, output_folder)
    combinations = calculate_sls_combinations(loaded, output_folder)
    deformation = calculate_sls_deformations(loaded)
    deflection_checks, deflection_summary = calculate_deflection_checks(loaded, output_folder)
    scenarios, vibration = calculate_floor_vibration(loaded, output_folder)
    d = deflection_summary.set_index("guid")
    deformation["deflection_acceptance_status"] = deformation["guid"].map(d["deflection_status"])
    deformation["deflection_utilisation_percent"] = deformation["guid"].map(d["utilisation_percent"])
    deformation["governing_deflection_check"] = deformation["guid"].map(d["governing_deflection_check"])
    if not vibration.empty:
        v = vibration.set_index("guid")
        deformation["vibration_status"] = deformation["guid"].map(v["comparison_status"]).fillna("NOT_ASSESSED_ROOF")
        deformation["vibration_diagnostic_ratio_percent"] = deformation["guid"].map(v["diagnostic_ratio_percent"])
    else:
        deformation["vibration_status"] = "NOT_ASSESSED_ROOF"
        deformation["vibration_diagnostic_ratio_percent"] = np.nan
    deformation["sls_status"] = "INCOMPLETE"
    deformation["note"] = (
        "Adopted action-specific deflection limits checked; vibration diagnostic "
        "is unvalidated and is not a DS/EN verdict. ULS and thickness iteration not implemented."
    )
    export_csv(deformation, "slab_sls_deformations.csv", output_folder)
    fields = ["id", "guid", "storey", "type", "span_mm", "thickness_mm",
              "governing_deflection_check", "deflection_utilisation_percent",
              "deflection_acceptance_status", "vibration_diagnostic_ratio_percent",
              "vibration_status", "sls_status"]
    summary = deformation.loc[deformation["case"] == "LC11", fields].copy().reset_index(drop=True)
    export_csv(summary, "slab_sls_summary.csv", output_folder)
    print("\nSLAB SUMMARY")
    print(summary.drop(columns="guid").to_string(index=False, float_format=lambda x:f"{x:.3f}"))
    if not vibration.empty:
        print("\nVIBRATION DIAGNOSTIC — NOT A DS/EN UTILISATION OR VERDICT")
        print(vibration[["id","storey","type","span_mm","width_m","modal_mass_kg",
                         "f1_hz","response","pace_hz","damping_ratio","mass_fraction",
                         "a_std_m_s2","acceleration_reference_m_s2","diagnostic_ratio_percent",
                         "comparison_status"]].to_string(index=False, float_format=lambda x:f"{x:.6f}"))
    print("\nOverall SLS: INCOMPLETE. Deflection limits evaluated; vibration is diagnostic only.")
    return {"loaded_slabs": loaded, "loads": loads, "combinations": combinations,
            "deformations": deformation, "deflection_checks": deflection_checks,
            "deflection_governing": deflection_summary, "vibration_scenarios": scenarios,
            "vibration_governing": vibration, "summary": summary}

# ===================================================================================
# 14. CONTINUE FROM THE UNCHANGED SECTION 5
# ===================================================================================
if __name__ == "__main__":
    # Section 5 already opened the model and populated `slabs`.
    results = run_sls_workflow(slabs)
