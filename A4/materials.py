"""KLH CLT materials and effective section properties - DTU Group 21.

Units: mm, N, MPa. Values refer to the actual strip width (default 1000 mm),
not a width-normalized quantity. EI is N*mm^2, W is mm^3.

Sources:
- Supplied KLH ETA-06/0138, 20 February 2017: Annex 3, p.14 (material
  properties); Annex 4, pp.19-20 (gamma method), p.28 (rolling shear).
- IFC output supplied by the team: two symmetric five-layer build-ups.
- Report P301/P401: numerical reference at L=3200 mm, primary direction XX.

Scope: simply supported, one-way strips, symmetric alternating five-layer
panels ONLY. XX is parallel to the outer lamellae; YY is perpendicular.
These labels do NOT establish the panel's orientation in the building.

The gamma approximation includes cross-layer rolling-shear flexibility in
EI_eff. Do not automatically add a separate shear deflection to this EI;
a different shear/flexure formulation must be checked for double counting.
No GA_eff or shear stress coefficients are supplied in this first module.
No creep, safety factors, loads, or ULS/SLS pass/fail checks are applied here.

The uploaded ETA edition is deliberately pinned to 2017. KLH also publishes
an edition dated 18 January 2021; do not mix values between editions.
"""

import math
from copy import deepcopy


ETA_SOURCE = "KLH ETA-06/0138, 20.02.2017"

# Properties for actions perpendicular to the panel: ETA p.14.
# E90_material is recorded, but transverse bending is neglected in this model.
MATERIAL = {
    "E0_mean_MPa": 12000.0,
    "E90_mean_MPa": 370.0,
    "G0_mean_MPa": 690.0,
    "G90_mean_MPa": 50.0,
    "fm_k_MPa": 24.0,
    "fv_k_MPa": 2.7,
    "rolling_shear_range_MPa": (0.8, 1.2),
    "source": ETA_SOURCE,
}

# Thicknesses come from the IFC extraction, not an invented ETA catalogue.
# Alternating 0/90/0/90/0 orientations are a working hypothesis to confirm.
BUILD_UPS = {
    "KLH5/140TL": (40.0, 20.0, 20.0, 20.0, 40.0),
    "KLH5/130TL": (30.0, 20.0, 30.0, 20.0, 30.0),
}
ALIASES = {"KLH5/130TL 2": "KLH5/130TL"}


def _positive(value, name):
    """Reject zero, negative, non-finite and non-numeric input."""
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite positive number.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite positive number.") from exc
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be a finite positive number.")
    return result


def get_build_up(type_name):
    """Resolve only known IFC names. Unknown products raise a clear error."""
    if not isinstance(type_name, str):
        raise ValueError("The slab type must be a string.")
    original = type_name
    name = type_name.strip()
    name = ALIASES.get(name, name)
    if name not in BUILD_UPS:
        raise ValueError(f"Unknown KLH type {original!r}. Add a verified build-up first.")
    return {
        "type_original": original,
        "type_canonical": name,
        "layer_thicknesses_mm": BUILD_UPS[name],
        "layer_angles_deg_assumed": (0, 90, 0, 90, 0),
        "thickness_mm": sum(BUILD_UPS[name]),
    }


def calculate_section_properties(type_name, span_mm, *, direction="XX", width_mm=1000.0):
    """Calculate instantaneous gamma stiffness for the two known layups.

    XX: outer/centre/outer longitudinal layers, with the centre at z=0.
        gamma_outer = 1/(1 + pi^2 E t_outer t_cross / (G_R L^2)).
    YY: the two internal transverse layers become the active layers.
        gamma = 1/(1 + pi^2 E t_active t_centre / (2 G_R L^2)).
    EI_eff = E * sum(I_i + gamma_i A_i z_i^2), active layers only.

    W_eff_report = EI_eff/(E*y_outer_active) matches the report's section
    modulus convention. It is NOT a general per-lamella stress solution.
    This module does not derive rolling-shear or longitudinal-shear stresses.
    """
    build = get_build_up(type_name)
    length = _positive(span_mm, "span_mm")
    width = _positive(width_mm, "width_mm")
    if direction not in ("XX", "YY"):
        raise ValueError("direction must be 'XX' or 'YY'.")

    t = build["layer_thicknesses_mm"]
    height = build["thickness_mm"]
    E = MATERIAL["E0_mean_MPa"]
    G_R = MATERIAL["G90_mean_MPa"]
    # Coordinates measured upwards from the mid-depth; first layer is top.
    centres = []
    top = height / 2.0
    for thickness in t:
        centres.append(top - thickness / 2.0)
        top -= thickness

    if direction == "XX":
        active = (0, 2, 4)
        gamma_outer = 1.0 / (1.0 + math.pi**2 * E * t[0] * t[1] / (G_R * length**2))
        gammas = (gamma_outer, 1.0, gamma_outer)
    else:
        active = (1, 3)
        gamma_pair = 1.0 / (1.0 + math.pi**2 * E * t[1] * t[2] / (2.0 * G_R * length**2))
        gammas = (gamma_pair, gamma_pair)

    I_net = 0.0
    I_eff = 0.0
    layer_results = []
    for index, gamma in zip(active, gammas):
        A = width * t[index]
        I_local = width * t[index]**3 / 12.0
        z = centres[index]
        I_net += I_local + A * z**2
        I_eff += I_local + gamma * A * z**2
        layer_results.append({"layer_number": index + 1, "z_mm": z, "gamma": gamma})
    EI_eff = E * I_eff
    y_outer = max(abs(centres[i]) + t[i] / 2.0 for i in active)
    return {
        "direction": direction,
        "span_mm": length,
        "width_mm": width,
        "E_transverse_used_in_bending_MPa": 0.0,
        "I_net_mm4": I_net,
        "EI_net_Nmm2": E * I_net,
        "I_eff_mm4": I_eff,
        "EI_eff_Nmm2": EI_eff,
        "W_eff_report_mm3": EI_eff / (E * y_outer),
        "active_layers": layer_results,
        "method": "gamma, symmetric five-layer, simply supported",
        "includes_cross_layer_shear_flexibility": True,
    }


def get_material_properties(slab, *, direction="XX", width_mm=1000.0,
                            orientation_confirmed=False, rolling_shear_k_MPa=None):
    """Accept one dictionary returned by get_clt_slabs().

    Required keys: type, span_mm. If layers/thickness_mm are supplied, check
    them against the known configuration (0.1 mm tolerance).
    The caller must confirm supports and the physical span independently.
    rolling_shear_k_MPa stays None unless explicitly selected after checking
    ETA Table 4. Supplying 0.8 or 1.2 records that selection, not verification.
    Returns a NEW dictionary without modifying the IFC input.
    """
    build = get_build_up(slab["type"])
    expected = build["layer_thicknesses_mm"]
    if "layers" in slab:
        actual = tuple(_positive(layer[0], "IFC layer thickness") for layer in slab["layers"])
        if len(actual) != len(expected) or any(abs(a - b) > 0.1 for a, b in zip(actual, expected)):
            raise ValueError(f"IFC layers {actual} do not match {build['type_canonical']}: {expected}.")
    if "thickness_mm" in slab:
        thickness = _positive(slab["thickness_mm"], "IFC thickness_mm")
        if abs(thickness - build["thickness_mm"]) > 0.1:
            raise ValueError("IFC total thickness does not match the selected KLH build-up.")
    if not isinstance(orientation_confirmed, bool):
        raise ValueError("orientation_confirmed must be True or False.")
    if rolling_shear_k_MPa is not None:
        rolling_shear_k_MPa = _positive(rolling_shear_k_MPa, "rolling_shear_k_MPa")
        if rolling_shear_k_MPa not in (0.8, 1.2):
            raise ValueError("Select 0.8 or 1.2 MPa only after checking ETA Table 4.")

    assumptions = [
        "Simply supported one-way strip; verify the actual supports.",
        "span_mm supplied by caller; IFC short side alone does not verify the span.",
        "Gamma EI includes cross-layer shear flexibility; avoid double counting in SLS.",
    ]
    if not orientation_confirmed:
        assumptions.append("Alternating lamellae and grain direction relative to span are UNCONFIRMED.")
    if rolling_shear_k_MPa is None:
        assumptions.append("Rolling shear strength is UNSELECTED; check ETA Table 4.")
    return {
        "id": slab.get("id"),
        "guid": slab.get("guid"),
        "storey": slab.get("storey"),
        **build,
        "material": deepcopy(MATERIAL),
        "rolling_shear_k_MPa": rolling_shear_k_MPa,
        "orientation_confirmed": orientation_confirmed,
        "section": calculate_section_properties(
            slab["type"], slab["span_mm"], direction=direction, width_mm=width_mm),
        "assumptions": assumptions,
    }


if __name__ == "__main__":
    print("KLH MATERIALS - reference strips: width=1000 mm, span=3200 mm")
    print(f"Source: {ETA_SOURCE}\n")
    print(f"{'Type':<15} {'Dir':<4} {'EI_eff [N mm2]':>17} {'W_report [mm3]':>17}")
    for name in BUILD_UPS:
        for axis in ("XX", "YY"):
            result = calculate_section_properties(name, 3200.0, direction=axis)
            print(f"{name:<15} {axis:<4} {result['EI_eff_Nmm2']:>17.4e} "
                  f"{result['W_eff_report_mm3']:>17.4e}")
    print("\nReference check against rounded P301/P401 values (tolerance 0.5%):")
    references = {"KLH5/140TL": (2.16e12, 2.57e6), "KLH5/130TL": (1.66e12, 2.13e6)}
    for name, (EI_reference, W_reference) in references.items():
        calculated = calculate_section_properties(name, 3200.0)
        for key, reference in (("EI_eff_Nmm2", EI_reference), ("W_eff_report_mm3", W_reference)):
            error = abs(calculated[key] / reference - 1.0)
            if error > 0.005:
                raise AssertionError(f"{name}, {key}: reference mismatch {error:.2%}.")
        print(f"  {name}: OK (EI_eff and report section modulus)")
    print("\nOrientation/support assumptions remain to be checked. No ULS/SLS verdict yet.")
