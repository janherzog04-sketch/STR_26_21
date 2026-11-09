"""P301/P401 report loading scenarios; Group 21, Advanced BIM, DTU.

Project data: 26-09-D-STR-Anon.pdf, printed p.8: CLT unit weight 5.5 kN/m3.
Scenario combinations: Appendix 3, SPEC Toolbox P301 pp.1,5-7/14 and
P401 pp.1,5-8/17. These are report reproductions, NOT a general EN1990 engine.
P301: G + imposed 5.0. P401: G + snow 0.8 + downward wind 0.3 kN/m2.
The caller assigns a scenario explicitly: no assignment from storey or thickness.

Self weight is calculated at EVERY thickness by default. Override with
self_weight_kN_m2 only for an explicit reference comparison.
Area loads kN/m2; width mm; line load N/mm = area load * width/1000.
SLS equivalent final loads already include creep: use instantaneous stiffness
and do not apply kdef again. No vibration calculations are included.
Roof combinations only reproduce the report's downward load cases: uplift,
local wind zones, maintenance loads and other roof actions are outside scope.
"""
import math

SOURCE = "26-09-D-STR, p.8 and Appendix 3 P301/P401"


def _number(value, name, *, positive=False):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number.")
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name} must be a finite number.") from exc
    if not math.isfinite(result) or result < 0 or (positive and result == 0):
        raise ValueError(f"{name} must be finite and {'positive' if positive else 'non-negative'}.")
    return result


def calculate_self_weight(thickness_mm, unit_weight_kN_m3=5.5):
    """Return kN/m2. unit_weight is kN/m3, not density in kg/m3."""
    return (_number(thickness_mm, 'thickness_mm', positive=True) / 1000
            * _number(unit_weight_kN_m3, 'unit_weight_kN_m3', positive=True))


def get_loads(slab, *, load_case, unit_weight_kN_m3=5.5, self_weight_kN_m2=None,
              additional_dead_kN_m2=1.2, imposed_kN_m2=None,
              snow_kN_m2=None, wind_kN_m2=None, width_mm=None):
    """Read thickness_mm and optional properties.section.width_mm from a slab.

    G includes CLT self weight plus additional_dead, which must EXCLUDE CLT.
    Supplying self_weight_kN_m2 takes precedence over unit weight and records
    the override. Defaults refer only to the selected report scenario.
    """
    if load_case not in ('P301', 'P401'):
        raise ValueError("Choose load_case='P301' or 'P401' explicitly.")
    thickness = _number(slab['thickness_mm'], 'thickness_mm', positive=True)
    section_width = slab.get('properties', {}).get('section', {}).get('width_mm')
    width = _number(width_mm if width_mm is not None else
                    (section_width if section_width is not None else 1000), 'width_mm', positive=True)
    if section_width is not None and not math.isclose(width, float(section_width), abs_tol=1e-6):
        raise ValueError('Loads and material section must use the same strip width.')
    if self_weight_kN_m2 is None:
        sw = calculate_self_weight(thickness, unit_weight_kN_m3)
        sw_source = 'Calculated: CLT thickness * project unit weight'
    else:
        sw = _number(self_weight_kN_m2, 'self_weight_kN_m2', positive=True)
        sw_source = 'Explicit reference self-weight override'
    topping = _number(additional_dead_kN_m2, 'additional_dead_kN_m2')
    actions = {'G': sw + topping, 'Q': 0.0, 'S': 0.0, 'W': 0.0}
    if load_case == 'P301':
        if snow_kN_m2 is not None or wind_kN_m2 is not None:
            raise ValueError('Snow/wind belong to P401; no mixed scenario is implemented.')
        actions['Q'] = _number(5.0 if imposed_kN_m2 is None else imposed_kN_m2, 'imposed_kN_m2')
        uls_patterns = [({'G': 1.2}, .6), ({'G': 1.0}, .6),
                        ({'G': 1., 'Q': 1.5}, .8), ({'G': 1., 'Q': .9}, .8)]
        inst_patterns = [{'G': 1., 'Q': 1.}, {'G': 1.}, {'G': 1., 'Q': .6}]
        creep_patterns = [{'G': .8, 'Q': .4}, {'G': .8}, {'G': .8, 'Q': .4}]
        psi = {'Q': {'psi0': .6, 'psi1': .6, 'psi2': .5}}
    else:
        if imposed_kN_m2 is not None:
            raise ValueError('P401 does not implement roof imposed/maintenance loads.')
        actions['S'] = _number(.8 if snow_kN_m2 is None else snow_kN_m2, 'snow_kN_m2')
        actions['W'] = _number(.3 if wind_kN_m2 is None else wind_kN_m2, 'wind_kN_m2')
        uls_patterns = [({'G': 1.2}, .6), ({'G': 1.}, .6),
                        ({'G': 1., 'W': 1.5}, 1.1), ({'G': 1., 'S': 1.5}, .9),
                        ({'G': 1., 'W': .45}, 1.1), ({'G': 1., 'S': .45}, .9),
                        ({'G': 1., 'S': 1.5, 'W': .45}, 1.1),
                        ({'G': 1., 'W': .45, 'S': .45}, 1.1)]
        inst_patterns = [{'G': 1.}, {'G': 1., 'W': 1.}, {'G': 1., 'S': 1.},
                         {'G': 1., 'W': .3}, {'G': 1., 'S': .3},
                         {'G': 1., 'S': 1., 'W': .3}, {'G': 1., 'W': .3, 'S': .3}]
        creep_patterns = [{'G': .8} for _ in inst_patterns]
        psi = {'S': {'psi0_other': .3, 'psi0_with_leading_wind': 0., 'psi2': 0.},
               'W': {'psi0_other': .3, 'psi2': 0.}}

    def combination(label, factors, **extra):
        area = sum(actions[k] * value for k, value in factors.items())
        return {'label': label, 'expression': ' + '.join(f'{v:.2f}{k}k' for k, v in factors.items()),
                'factors': dict(factors), 'area_load_kN_m2': area,
                'line_load_N_mm': area * width / 1000, **extra}

    uls = [combination(f'LC{i}', factors, kmod=kmod)
           for i, (factors, kmod) in enumerate(uls_patterns, 1)]
    sls = []
    for i, (inst, creep) in enumerate(zip(inst_patterns, creep_patterns), 1):
        final = {key: inst.get(key, 0) + creep.get(key, 0) for key in actions
                 if key in inst or key in creep}
        for kind, factors in [('inst', inst), ('creep', creep), ('final', final)]:
            sls.append(combination(f'LC{i}', factors, deformation=kind))
    return {'id': slab.get('id'), 'guid': slab.get('guid'), 'scenario': load_case,
            'source': SOURCE, 'width_mm': width, 'actions_kN_m2': actions,
            'characteristic': {'self_weight_kN_m2': sw, 'self_weight_source': sw_source,
                               'additional_dead_kN_m2': topping, 'Gk_kN_m2': actions['G'],
                               'Qk_kN_m2': actions['Q'], 'Sk_kN_m2': actions['S'], 'Wk_kN_m2': actions['W']},
            'parameters': {'kdef': .8, 'service_class': 1, 'consequence_class': 'CC2', 'psi': psi},
            'uls': uls, 'sls': sls,
            'assumptions': ['Scenario assigned explicitly, not verified from IFC use.',
                            'Report downward uniform load cases only.',
                            'Check every ULS combination with its own kmod.',
                            'SLS final equivalent loads already include creep.']}


if __name__ == '__main__':
    for case, thickness in [('P301', 140), ('P401', 130)]:
        loads = get_loads({'thickness_mm': thickness}, load_case=case)
        print(f"\n{case}: self weight={loads['characteristic']['self_weight_kN_m2']:.3f} kN/m2")
        for c in loads['uls']:
            print(f"{c['label']}: {c['expression']:<30} q={c['line_load_N_mm']:.4f} N/mm, kmod={c['kmod']:.2f}")
