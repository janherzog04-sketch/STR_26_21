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
import numpy as np

from config import MODEL_PATH

## import data from loads
from loads_2 import read_ifc_slabs
from loads_2 import (assign_loads, calculate_sls_combinations, export_loads, section_for_slab, checked_number,get_actions, SLS_COMBINATIONS, ACTION_NAMES, slab_identity, ACTION_LABELS, DEFLECTION_DIVISORS, VIBRATION_CONFIG, VIBRATION_SCOPE, export_csv)
#from main import slabs
# ===================================================================================
# . INSTANTANEOUS DEFORMATION AND CREEP
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

K_DEF = 0.8
PSI2 = {"Q": 0.5, "S": 0.0, "W": 0.0}
CAMBER_MM = 0.0

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
        "", "")
    scenarios["ratio_basis"] = ""
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
        print("\nVIBRATION DIAGNOSTIC")
        print(vibration[["id","storey","type","span_mm","width_m","modal_mass_kg",
                         "f1_hz","response","pace_hz","damping_ratio","mass_fraction",
                         "a_std_m_s2","acceleration_reference_m_s2","diagnostic_ratio_percent",
                         "comparison_status"]].to_string(index=False, float_format=lambda x:f"{x:.6f}"))
    print("\nOverall SLS:. Deflection limits evaluated; vibration is diagnostic only.")
    return {"loaded_slabs": loaded, "loads": loads, "combinations": combinations,
            "deformations": deformation, "deflection_checks": deflection_checks,
            "deflection_governing": deflection_summary, "vibration_scenarios": scenarios,
            "vibration_governing": vibration, "summary": summary}



# ===================================================================================
# 14. READ IFC AND RUN SLS CHECKS
# ===================================================================================
if __name__ == "__main__":
    model_path = Path(MODEL_PATH).expanduser()

    if not model_path.is_absolute():
        model_path = Path(__file__).resolve().parent / model_path

    if not model_path.is_file():
        raise FileNotFoundError(f"IFC model not found: {model_path}")

    # Create the list of slab dictionaries.
    slabs = read_ifc_slabs(model_path)

    print(f"Extracted {len(slabs)} KLH slabs.")

    # Run the functions defined above.
    results = run_sls_workflow(
        slabs,
        output_folder=Path(__file__).resolve().parent / "output",
    )

