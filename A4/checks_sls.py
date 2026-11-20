"""
CLT FLOOR CHECK - Group 21, Advanced BIM, DTU

Assignment question: does SLS rather than ULS determine the panel thickness?
Current scope: existing bending-plus-shear deformation and diagnostic vibration;
combined final deformation checked against the report-basis L/360 limit;
representative P301/P401 comparison, CSV summaries and paginated PNG tables.
This script does not calculate ULS resistance or establish a required thickness.

Run from repository root: python A4/main_copy.py
Keep loads_2.py and a local config.py (MODEL_PATH) in the same A4 folder.
Dependencies: ifcopenshell, pandas, numpy, matplotlib.

Calculation units: mm, N, N/mm2. A 1 kN/m2 load on a 1 m strip is 1 N/mm.
Report references: PDF viewer pp. 276-278 (P301), 290-292 (P401).
Comparisons use deformation magnitudes. Report cases are representative, not a
verified mapping from a report panel ID to every IFC slab.

The diagnostic acceleration ratio is NOT a report vibration utilisation. It is
retained separately, so the deformation/vibration leader remains NOT_COMPARABLE.
No report-family vibration equation, gamma stiffness or ULS routine is substituted
silently. Existing load, stiffness and structural-model assumptions still apply.
"""

import math
from pathlib import Path

import numpy as np
import pandas as pd

from config import MODEL_PATH
from loads_2 import (
    assign_loads, calculate_sls_combinations, section_for_slab,
    checked_number, get_actions, SLS_COMBINATIONS, ACTION_NAMES,
    slab_identity, ACTION_LABELS, VIBRATION_CONFIG, read_ifc_slabs,
)

K_DEF = 0.8
PSI2 = {"Q": 0.5, "S": 0.0, "W": 0.0}
CAMBER_MM = 0.0
REPORT_FINAL_DEFLECTION_DIVISOR = 360.0
EXPORT_TABLE_IMAGES = True
TABLE_ROWS_PER_IMAGE = 20
RUN_DIAGNOSTIC_VIBRATION = True
REPORT_REFERENCES = {
    "P301": {"span_mm": 3200.0, "inst_mm": 4.41, "final_mm": 6.68,
             "final_util_pct": 75.14, "vibration_util_pct": 75.40},
    "P401": {"span_mm": 3200.0, "inst_mm": 2.32, "final_mm": 3.58,
             "final_util_pct": 40.32, "vibration_util_pct": 83.17},
}


# ===================================================================================
# EXPORT HELPERS
# ===================================================================================
def output_directory(output_folder=None):
    folder = (Path(output_folder) if output_folder is not None
              else Path(__file__).resolve().parent / "output")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def export_csv(dataframe, filename, output_folder=None):
    if dataframe.empty:
        raise ValueError(f"No data to export: {filename}")
    target = output_directory(output_folder) / filename
    dataframe.to_csv(target, index=False, encoding="utf-8-sig", na_rep="")
    print(f"Saved: {target}")
    return target


def export_characteristic_loads(loaded_slabs, output_folder=None):
    # Local name avoids confusion with the different batch export_loads API.
    fields = list(slab_identity(loaded_slabs[0])) + [
        "g_clt_k_kn_m2", "g_additional_k_kn_m2", "g_total_k_kn_m2",
        "q_imposed_k_kn_m2", "s_k_kn_m2", "w_down_k_kn_m2",
    ]
    frame = pd.DataFrame(loaded_slabs)[fields]
    if frame.isna().any().any():
        raise ValueError("Missing characteristic-load data")
    export_csv(frame, "slab_characteristic_loads.csv", output_folder)
    return frame


# ===================================================================================
# INSTANTANEOUS DEFORMATION AND CREEP - EXISTING EQUATIONS RETAINED
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
        "components": {a: response(v) for a, v in get_actions(slab).items()},
        "clt": response(slab["g_clt_k_kn_m2"]),
        "additional": response(slab["g_additional_k_kn_m2"])}


def calculate_sls_deformations(loaded_slabs):
    kdef = checked_number(K_DEF, "k_def")
    camber = checked_number(CAMBER_MM, "camber")
    if any(checked_number(PSI2[a], f"psi2 {a}") > 1 for a in ("Q", "S", "W")):
        raise ValueError("psi2 must be within 0-1")
    rows = []
    for slab in loaded_slabs:
        inst = calculate_instantaneous_deflections(slab)
        c = inst["components"]
        creep = {a: kdef*c[a]["total"]*(1 if a == "G" else PSI2[a]) for a in ACTION_NAMES}
        for case, (family, factors) in SLS_COMBINATIONS.items():
            bending = sum(f*c[a]["bending"] for a, f in zip(ACTION_NAMES, factors))
            shear = sum(f*c[a]["shear"] for a, f in zip(ACTION_NAMES, factors))
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
                for part in ("bending", "shear"):
                    row[f"w_{label}_{part}_inst_mm"] = c[a][part]
                row[f"w_{label}_inst_mm"] = c[a]["total"]
                row[f"w_{label}_creep_mm"] = creep[a]
            rows.append(row)
    return pd.DataFrame(rows)


# ===================================================================================
# REPORT-BASIS COMBINED FINAL DEFLECTION CHECK - REPLACES ACTION-SPECIFIC CHECKS
# ===================================================================================
def calculate_deflection_checks(loaded_slabs, output_folder=None, *, deformations=None):
    if not loaded_slabs:
        raise ValueError("No slabs supplied")
    frame = (calculate_sls_deformations(loaded_slabs)
             if deformations is None else deformations).copy()
    divisor = checked_number(REPORT_FINAL_DEFLECTION_DIVISOR, "final divisor", True)
    rows = []
    for slab in loaded_slabs:
        L = checked_number(slab["span_mm"], "span", True)
        limit = L/divisor
        cases = frame.loc[(frame["guid"] == slab["guid"]) &
                          (frame["family"] == "characteristic")]
        if cases.empty or cases["case"].duplicated().any():
            raise ValueError(f"Missing/duplicate characteristic cases: slab {slab['id']}")
        for _, case in cases.iterrows():
            if not math.isclose(float(case["span_mm"]), L, rel_tol=0, abs_tol=.1):
                raise ValueError(f"Span mismatch: slab {slab['id']}")
            value = float(case["w_case_final_mm"])
            if not math.isfinite(value):
                raise ValueError(f"Invalid final deformation: slab {slab['id']}")
            calculated = abs(value)
            utilisation = calculated/limit
            rows.append({**slab_identity(slab),
                "check": "combined_final_report_L360", "case": case["case"],
                "calculated_deflection_mm": calculated,
                "limit_span_divisor": divisor, "limit_deflection_mm": limit,
                "utilisation_ratio": utilisation, "utilisation_percent": 100*utilisation,
                "check_status": "PASS_REPORT_LIMIT" if utilisation <= 1 else "FAIL_REPORT_LIMIT",
                "criterion_basis": "Report P301/P401 combined final deformation: L/360"})
    detailed = pd.DataFrame(rows)
    indices = detailed.groupby("guid", sort=False)["utilisation_ratio"].idxmax()
    summary = detailed.loc[indices].copy().reset_index(drop=True).rename(columns={
        "check": "governing_deflection_check", "check_status": "deflection_status"})
    export_csv(detailed, "slab_deflection_checks.csv", output_folder)
    export_csv(summary, "slab_deflection_governing.csv", output_folder)
    return detailed, summary


# ===================================================================================
# DIAGNOSTIC VIBRATION - EXISTING EQUATIONS RETAINED, NOT A REPORT UTILISATION
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
            candidates = list(base_paces)+[f1/h for h in range(1, 5) if lo <= f1/h <= hi]
            harmonic_paces = sorted(set(round(x, 10) for x in candidates))
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
        return scenarios, pd.DataFrame()
    scenarios["diagnostic_ratio_percent"] = 100*scenarios["a_std_m_s2"]/reference
    scenarios["comparison_status"] = np.where(scenarios["regime_valid"],
        "DIAGNOSTIC_ONLY", "OUTSIDE_ISOLATED_IMPULSE_REGIME")
    applicable = scenarios.loc[scenarios["regime_valid"]]
    indices = applicable.groupby("guid")["diagnostic_ratio_percent"].idxmax()
    governing = applicable.loc[indices].copy().reset_index(drop=True)
    export_csv(scenarios, "floor_vibration_scenarios.csv", output_folder)
    export_csv(governing, "floor_vibration_governing.csv", output_folder)
    return scenarios, governing


# ===================================================================================
# REPORT COMPARISON AND ONE ROW PER SLAB
# ===================================================================================
def build_sls_summary(loaded_slabs, deformation, deflection_summary, vibration):
    checks = deflection_summary.set_index("guid")
    if checks.index.has_duplicates:
        raise ValueError("Duplicate governing deflection results")
    v = vibration.set_index("guid") if not vibration.empty else pd.DataFrame()
    rows = []
    for slab in loaded_slabs:
        guid = slab["guid"]
        governing = checks.loc[guid]
        cases = deformation.loc[(deformation["guid"] == guid) &
                                (deformation["family"] == "characteristic")]
        inst = pd.to_numeric(cases["w_case_inst_mm"], errors="raise").abs()
        if inst.empty or not np.isfinite(inst).all():
            raise ValueError(f"Invalid instantaneous response for {guid}")
        inst_index = inst.idxmax()
        maximum_final = float(governing["calculated_deflection_mm"])
        maximum_inst = float(inst.loc[inst_index])
        span = float(slab["span_mm"])
        thickness = float(slab["thickness_mm"])
        reference_key = None
        if slab["load_category"] == "floor" and math.isclose(thickness, 140., abs_tol=.1):
            reference_key = "P301"
        elif slab["load_category"] == "roof" and math.isclose(thickness, 130., abs_tol=.1):
            reference_key = "P401"
        ref = REPORT_REFERENCES.get(reference_key)
        same_span = bool(math.isclose(span, ref["span_mm"], rel_tol=0., abs_tol=.1)) if ref else False
        vv = v.loc[guid] if not v.empty and guid in v.index else None
        row = {**slab_identity(slab), "slab_id": slab["id"], "section": slab["type"],
            "maximum_instantaneous_deformation_mm": maximum_inst,
            "governing_instantaneous_load_case": cases.loc[inst_index, "case"],
            "maximum_final_deformation_mm": maximum_final,
            "governing_final_load_case": governing["case"],
            "allowable_final_deformation_mm": governing["limit_deflection_mm"],
            "governing_deflection_check": governing["governing_deflection_check"],
            "deflection_utilisation_percent": governing["utilisation_percent"],
            "deformation_utilisation_percent": governing["utilisation_percent"],
            "deflection_acceptance_status": governing["deflection_status"],
            "natural_frequency_hz": float(vv["f1_hz"]) if vv is not None else None,
            "vibration_diagnostic_ratio_percent": float(vv["diagnostic_ratio_percent"]) if vv is not None else None,
            "vibration_utilisation_percent": None,
            "vibration_status": "DIAGNOSTIC_ONLY" if vv is not None else "NOT_ASSESSED",
            "leading_calculated_check": "NOT_COMPARABLE",
            "report_reference": reference_key+"_REPRESENTATIVE" if ref else None,
            "report_span_mm": ref["span_mm"] if ref else None,
            "same_span_as_report": same_span if ref else None,
            "report_instantaneous_deformation_mm": ref["inst_mm"] if ref else None,
            "report_final_deformation_mm": ref["final_mm"] if ref else None,
            "report_deflection_utilisation_percent": ref["final_util_pct"] if ref else None,
            "report_vibration_utilisation_percent": ref["vibration_util_pct"] if ref else None,
            "final_deformation_difference_mm": maximum_final-ref["final_mm"] if same_span else None,
            "final_deformation_difference_percent": 100*(maximum_final/ref["final_mm"]-1) if same_span else None,
            "instantaneous_deformation_difference_percent": 100*(maximum_inst/ref["inst_mm"]-1) if same_span else None,
            "deflection_utilisation_difference_pp": float(governing["utilisation_percent"])-ref["final_util_pct"] if same_span else None}
        rows.append(row)
    return pd.DataFrame(rows)


def export_sls_comparison_csv(summary, output_folder=None):
    export_csv(summary, "slab_sls_summary.csv", output_folder)
    export_csv(summary, "slab_sls_comparison.csv", output_folder)
    fields = ["slab_id", "guid", "storey", "section", "span_mm", "report_reference",
        "same_span_as_report", "maximum_final_deformation_mm", "report_final_deformation_mm",
        "final_deformation_difference_mm", "final_deformation_difference_percent",
        "deflection_utilisation_percent", "report_deflection_utilisation_percent",
        "deflection_utilisation_difference_pp", "vibration_diagnostic_ratio_percent",
        "vibration_utilisation_percent", "report_vibration_utilisation_percent",
        "leading_calculated_check"]
    comparison = summary[fields].copy()
    export_csv(comparison, "slab_report_comparison.csv", output_folder)
    return {"summary": summary, "comparison": comparison}


# ===================================================================================
# PAGINATED PNG TABLES
# ===================================================================================
def export_sls_table_images(summary_df, output_folder=None, rows_per_image=20):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("Install table dependency: python -m pip install matplotlib") from exc
    if not isinstance(rows_per_image, int) or rows_per_image < 1:
        raise ValueError("rows_per_image must be a positive integer")
    if summary_df.empty:
        return []
    columns = {
        "slab_id": "Slab\nID", "storey": "Storey", "section": "Section",
        "maximum_final_deformation_mm": "Max. final\ndeformation [mm]",
        "deformation_utilisation_percent": "Final deformation\nutilisation [%]",
        "report_final_deformation_mm": "Report final\ndeformation [mm]",
        "final_deformation_difference_percent": "Final difference\n(equal span) [%]",
    }
    table_df = summary_df[list(columns)].sort_values(["storey", "slab_id"]).copy()
    table_df["slab_id"] = table_df["slab_id"].map(lambda x: str(int(x)))
    for col, decimals in (("maximum_final_deformation_mm", 3),
                          ("deformation_utilisation_percent", 2),
                          ("report_final_deformation_mm", 3),
                          ("final_deformation_difference_percent", 2)):
        table_df[col] = table_df[col].map(
            lambda value, n=decimals: "—" if pd.isna(value) else f"{float(value):.{n}f}")
    table_df = table_df.rename(columns=columns)
    folder = output_directory(output_folder)
    paths = []
    for page, start in enumerate(range(0, len(table_df), rows_per_image), 1):
        part = table_df.iloc[start:start+rows_per_image]
        fig, ax = plt.subplots(figsize=(16, 2.6+.40*len(part)))
        ax.axis("off")
        ax.set_title(f"CLT slab final-deformation comparison\nSlabs {start+1}–{start+len(part)} of {len(table_df)}",
                     fontsize=14, fontweight="bold", pad=22)
        table = ax.table(cellText=part.values, colLabels=part.columns,
            cellLoc="center", colLoc="center", loc="center",
            colWidths=[.07, .09, .16, .18, .18, .16, .16])
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 1.8)
        for (r, c), cell in table.get_celld().items():
            cell.set_edgecolor("#D0D7DE")
            cell.set_linewidth(.6)
            if r == 0:
                cell.set_facecolor("#17365D")
                cell.set_text_props(color="white", weight="bold")
                cell.set_height(cell.get_height()*1.5)
            else:
                cell.set_facecolor("#EEF3F8" if r % 2 == 0 else "white")
        fig.text(.5, .02, "Final deformation limit: L/360. Report values are representative; differences shown only at equal span.",
                 ha="center", fontsize=9)
        fig.subplots_adjust(left=.03, right=.97, top=.84, bottom=.10)
        target = folder/f"slab_sls_table_{page:02d}.png"
        try:
            fig.savefig(target, dpi=250, bbox_inches="tight", facecolor="white")
        finally:
            plt.close(fig)
        paths.append(target)
        print(f"Saved: {target}")
    return paths


# ===================================================================================
# WORKFLOW AND SUMMARY
# ===================================================================================
def run_sls_workflow(raw_slabs, output_folder=None):
    if not raw_slabs:
        raise ValueError("No KLH slabs extracted")
    guids = [slab["guid"] for slab in raw_slabs]
    if any(not guid for guid in guids) or len(set(guids)) != len(guids):
        raise ValueError("Every slab needs a unique, nonempty GUID")
    loaded = assign_loads(raw_slabs)
    loads = export_characteristic_loads(loaded, output_folder)
    combinations = calculate_sls_combinations(loaded, output_folder)
    deformation = calculate_sls_deformations(loaded)
    deflection_checks, deflection_summary = calculate_deflection_checks(
        loaded, output_folder, deformations=deformation)
    if RUN_DIAGNOSTIC_VIBRATION:
        scenarios, vibration = calculate_floor_vibration(loaded, output_folder)
    else:
        scenarios, vibration = pd.DataFrame(), pd.DataFrame()
    summary = build_sls_summary(loaded, deformation, deflection_summary, vibration)
    mapped = summary.set_index("guid")
    for field in ("deflection_acceptance_status", "deflection_utilisation_percent",
                  "governing_deflection_check", "maximum_final_deformation_mm",
                  "governing_final_load_case", "allowable_final_deformation_mm",
                  "vibration_status", "vibration_diagnostic_ratio_percent"):
        deformation[field] = deformation["guid"].map(mapped[field])
    export_csv(deformation, "slab_sls_deformations.csv", output_folder)
    comparison = export_sls_comparison_csv(summary, output_folder)
    images = (export_sls_table_images(summary, output_folder, TABLE_ROWS_PER_IMAGE)
              if EXPORT_TABLE_IMAGES else [])
    print("\nREPORT-BASIS FINAL-DEFORMATION SUMMARY")
    fields = ["slab_id", "storey", "section", "governing_final_load_case",
              "maximum_final_deformation_mm", "allowable_final_deformation_mm",
              "deflection_utilisation_percent", "deflection_acceptance_status",
              "report_final_deformation_mm", "final_deformation_difference_percent"]
    print(summary[fields].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print("\nVibration remains diagnostic: no comparable vibration utilisation or SLS leader is declared.")
    return {"loaded_slabs": loaded, "loads": loads, "combinations": combinations,
            "deformations": deformation, "deflection_checks": deflection_checks,
            "deflection_governing": deflection_summary,
            "vibration_scenarios": scenarios, "vibration_governing": vibration,
            "summary": summary, "comparison": comparison["comparison"], "table_images": images}


# ===================================================================================
# EXTRACT THE IFC AND START THE WORKFLOW
# ===================================================================================
if __name__ == "__main__":
    model_path = Path(MODEL_PATH).expanduser()
    if not model_path.is_absolute():
        model_path = Path(__file__).resolve().parent/model_path
    if not model_path.is_file():
        raise FileNotFoundError(f"IFC model not found: {model_path}")
    slabs = read_ifc_slabs(model_path)
    print(f"Extracted {len(slabs)} KLH slabs.")
    results = run_sls_workflow(slabs)

def compare_results_with_report(summary_df, output_folder=None):
    """Compare the per-slab summary with representative report cases.

    Uses final deformation and the same L/360 limit as the report.
    Differences are only calculated for matching spans. A matching span
    alone does not confirm identical loading, supports or panel identity.
    Requires REPORT_REFERENCES and export_csv from main_copy.py.
    """
    required = {"slab_id", "storey", "section", "span_mm", "report_reference",
                "maximum_final_deformation_mm", "deflection_utilisation_percent"}
    if not required.issubset(summary_df.columns):
        raise ValueError(f"Missing summary columns: {sorted(required-set(summary_df.columns))}")
    if summary_df.empty:
        raise ValueError("No results to compare")
    rows = []
    for _, slab in summary_df.iterrows():
        name = slab["report_reference"]
        name = str(name).split("_")[0] if pd.notna(name) else None
        ref = REPORT_REFERENCES.get(name)
        span = float(slab["span_mm"])
        calculated_mm = abs(float(slab["maximum_final_deformation_mm"]))
        calculated_pct = float(slab["deflection_utilisation_percent"])
        if not all(math.isfinite(v) for v in (span, calculated_mm, calculated_pct)) or span <= 0:
            raise ValueError(f"Invalid comparison input: slab {slab['slab_id']}")
        if not math.isclose(calculated_pct, 100*calculated_mm/(span/360), rel_tol=1e-6, abs_tol=1e-6):
            raise ValueError("Use the report-basis final-deflection summary, not the old action-specific utilisation")
        same_span = bool(math.isclose(span, ref["span_mm"], rel_tol=0, abs_tol=.1)) if ref else False
        rows.append({
            "slab_id": slab["slab_id"], "storey": slab["storey"], "section": slab["section"],
            "span_mm": span, "report_case": name,
            "report_span_mm": ref["span_mm"] if ref else None,
            "comparison_basis": ("MATCHED_SPAN_REPRESENTATIVE" if same_span else
                                 "DIFFERENT_SPAN" if ref else "NO_REFERENCE"),
            "calculated_final_mm": calculated_mm,
            "report_final_mm": ref["final_mm"] if ref else None,
            "difference_mm": calculated_mm-ref["final_mm"] if same_span else None,
            "difference_percent": 100*(calculated_mm/ref["final_mm"]-1) if same_span else None,
            "calculated_final_utilisation_percent": calculated_pct,
            "report_final_utilisation_percent": ref["final_util_pct"] if ref else None,
            "utilisation_difference_pp": calculated_pct-ref["final_util_pct"] if same_span else None,
        })
    comparison = pd.DataFrame(rows)
    export_csv(comparison, "slab_calculated_vs_report.csv", output_folder)
    print("\nCALCULATED FINAL DEFORMATION VS REPORT")
    print(comparison.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    return comparison