"""Diagnostic reproduction of Appendix 3 Toolbox ULS checks, P301/P401.

Scope: symmetric five-layer KLH strips, XX direction, simply supported UDL.
Requires explicit reference_mode=True: this first version does not verify IFC
supports, lamella orientation, notches, concentrated supports or action coverage.
Returned 'reference_checks_passed' refers ONLY to the three reproduced checks.

Report conventions: sigma=M/W_eff_report; tau=V*EQ/(b*EI_eff).
EQ_L is the transformed first moment above mid-depth; EQ_R above the
upper boundary of the centre longitudinal layer. All layers contribute to EQ
with E0 or E90; EI_eff is calculated with the materials module gamma method.
This intentionally reproduces the report convention, not a general layerwise
stress solver. No gamma reductions are inserted into EQ.

E90 is 370 MPa from uploaded ETA 2017 by default. The report's intermediate
EQ entries are consistent with 450 MPa: use shear_E90_MPa=450 explicitly ONLY
for the documented report-convention comparison. Do not mix editions silently.
Report gamma_M=1.19 and ksys=1.0; report rolling shear strength=1.20 MPa.
The latter must be explicitly selected; applicable ETA conditions remain to check.
"""
import math
from materials import get_material_properties
from loads import _number, get_loads


def check_uls(slab, *, reference_mode=False, gamma_M=1.19, ksys=1.0,
              shear_E90_MPa=None):
    if not reference_mode:
        raise ValueError('This diagnostic implementation requires reference_mode=True. Verify actual supports/orientation separately.')
    props = slab['properties']
    loads = slab['loads']
    section = props['section']
    if section['direction'] != 'XX':
        raise ValueError('Report shear reproduction is implemented only in XX.')
    L = _number(slab['span_mm'], 'span_mm', positive=True)
    if not math.isclose(L, section['span_mm'], rel_tol=1e-9):
        raise ValueError('Recompute materials for the current span.')
    width = section['width_mm']
    if not math.isclose(width, loads['width_mm'], rel_tol=1e-9):
        raise ValueError('Load and section widths differ.')
    thicknesses = props['layer_thicknesses_mm']
    if not math.isclose(float(slab['thickness_mm']), sum(thicknesses), abs_tol=.1):
        raise ValueError('Recompute material properties for the current panel.')
    # Detect stale panel/layer input by recalculating its section independently.
    fresh = get_material_properties(slab, width_mm=width)['section']
    if not math.isclose(fresh['EI_eff_Nmm2'], section['EI_eff_Nmm2'], rel_tol=1e-9):
        raise ValueError('Stale or altered material stiffness; recompute properties.')
    gm = _number(gamma_M, 'gamma_M', positive=True)
    system = _number(ksys, 'ksys', positive=True)
    material = props['material']
    rolling = props['rolling_shear_k_MPa']
    if rolling is None:
        raise ValueError('Select rolling_shear_k_MPa explicitly in get_material_properties().')
    E90 = material['E90_mean_MPa'] if shear_E90_MPa is None else _number(shear_E90_MPa, 'shear_E90_MPa')
    E0 = material['E0_mean_MPa']
    h = sum(thicknesses)

    def first_moment_above(cut):
        top = h / 2
        total = 0.
        for i, t in enumerate(thicknesses):
            bottom = top - t
            low = max(bottom, cut)
            if top > low:
                E = E0 if i % 2 == 0 else E90
                total += E * width * (top**2 - low**2) / 2
            top = bottom
        return total

    EQL = first_moment_above(0.)
    EQR = first_moment_above(thicknesses[2] / 2)
    EI = section['EI_eff_Nmm2']
    W = section['W_eff_report_mm3']
    rows = []
    for c in loads['uls']:
        q = _number(c['line_load_N_mm'], 'line_load_N_mm')
        kmod = _number(c['kmod'], 'kmod', positive=True)
        M = q * L**2 / 8
        V = q * L / 2
        fm = kmod * material['fm_k_MPa'] * system / gm
        fv = kmod * material['fv_k_MPa'] / gm
        fr = kmod * rolling / gm
        sigma = M / W
        tauL = V * EQL / (width * EI)
        tauR = V * EQR / (width * EI)
        ratios = {'bending': sigma / fm, 'longitudinal_shear': tauL / fv, 'rolling_shear': tauR / fr}
        rows.append({'label': c['label'], 'expression': c['expression'], 'kmod': kmod,
                     'M_Nmm': M, 'V_N': V, 'sigma_m_MPa': sigma,
                     'tau_longitudinal_MPa': tauL, 'tau_rolling_MPa': tauR,
                     'fm_d_MPa': fm, 'fv_d_MPa': fv, 'fr_d_MPa': fr,
                     'utilization': ratios})
    governing = {key: max(rows, key=lambda r: r['utilization'][key]) for key in rows[0]['utilization']}
    maxima = {key: row['utilization'][key] for key, row in governing.items()}
    return {'scenario': loads['scenario'], 'results': rows, 'maximum_utilization': maxima,
            'governing_combinations': {key: row['label'] for key, row in governing.items()},
            'reference_checks_passed': all(v <= 1 for v in maxima.values()),
            'EQ_L_Nmm': EQL, 'EQ_R_Nmm': EQR, 'shear_E90_MPa': E90,
            'gamma_M': gm, 'ksys': system,
            'status': 'REFERENCE ONLY: three report checks, subject to unverified modelling assumptions.'}


# Standalone results and Toolbox comparison; no fourth script is required.
def reference_slab(case, *, reproduce_toolbox=False):
    """Build one explicitly assigned report case, independently of the IFC.

    Default: unit weight 5.5 kN/m3 and E90=370 MPa (uploaded ETA 2017).
    Secondary diagnostic: supplied Toolbox weights 0.785/0.729 kPa and
    E90=450 MPa for comparison with the report's intermediate EQ entries.
    The secondary inputs do not change the primary project results.
    """
    if case not in ('P301', 'P401'):
        raise ValueError("Reference case must be P301 or P401.")
    name, t = ('KLH5/140TL', 140) if case == 'P301' else ('KLH5/130TL 2', 130)
    slab = {'type': name, 'thickness_mm': t, 'span_mm': 3200.0}
    # 1.2 is the REPORT's selected value; ETA applicability still to be verified.
    slab['properties'] = get_material_properties(slab, rolling_shear_k_MPa=1.2)
    override = {'self_weight_kN_m2': .785 if case == 'P301' else .729} if reproduce_toolbox else {}
    slab['loads'] = get_loads(slab, load_case=case, **override)
    result = check_uls(slab, reference_mode=True, shear_E90_MPa=450 if reproduce_toolbox else None)
    return slab, result


def run_toolbox_validation():
    """Print final reference ULS results and compare them with Toolbox.

    Delta pp = project utilization minus published Toolbox utilization,
    in percentage points. Reproduction % is a separate diagnostic with
    the report comparison inputs, not the adopted project calculation.
    This is not a global building verdict or a SLS/vibration check.
    """
    references = {'P301': {'bending': 29.18, 'longitudinal_shear': 9.57, 'rolling_shear': 21.00},
                  'P401': {'bending': 11.47, 'longitudinal_shear': 3.20, 'rolling_shear': 6.70}}
    for case in references:
        slab, project = reference_slab(case)
        _, toolbox = reference_slab(case, reproduce_toolbox=True)
        print(f"\n{case}, L=3.20 m, strip=1 m; self weight={slab['loads']['characteristic']['self_weight_kN_m2']:.3f} kPa")
        print(f"{'Check':<22} {'Project %':>11} {'Toolbox %':>11} {'Delta pp':>10} {'Reproduction %':>16}")
        for key, ref in references[case].items():
            val = project['maximum_utilization'][key]*100
            reproduced = toolbox['maximum_utilization'][key]*100
            print(f'{key:<22} {val:>11.3f} {ref:>11.2f} {val-ref:>10.3f} {reproduced:>16.3f}')
            if abs(reproduced-ref) > .10:
                raise AssertionError(f'{case}/{key}: difference >0.10 percentage points.')
        print('Governing ULS combinations:', project['governing_combinations'])
    print('\nOK: report-convention reproduction within 0.10 percentage points.')
    print('Reference assumptions only. IFC assignment, SLS and vibration remain outside this test.')


if __name__ == '__main__':
    run_toolbox_validation()
