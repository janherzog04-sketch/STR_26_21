"""CLT batch loads and P301/P401 reference API; Group 21, Advanced BIM, DTU.

Batch API below adds candidate categories, signed wind and per-GUID assignment.
Legacy get_loads() preserves the original Toolbox comparison cases.

Project data: 26-09-D-STR-Anon.pdf, printed p.8: CLT unit weight 5.5 kN/m3.
Scenario combinations: Appendix 3, SPEC Toolbox P301 pp.1,5-7/14 and
P401 pp.1,5-8/17. These are report reproductions, NOT a general EN1990 engine.
P301: G + imposed 5.0. P401: G + snow 0.8 + downward wind 0.3 kN/m2.
The caller assigns a scenario explicitly: no assignment from storey or thickness.

Self weight is calculated at EVERY thickness by default. Override with
self_weight_kN_m2 only for an explicit reference comparison.
Area loads kN/m2; width mm; line load N/mm = area load * width/1000.
Only ULS load combinations are generated.
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
        psi = {'Q': {'psi0': .6}}
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
        psi = {'S': {'psi0_other': .3, 'psi0_with_leading_wind': 0.},
               'W': {'psi0_other': .3}}

    def combination(label, factors, **extra):
        area = sum(actions[k] * value for k, value in factors.items())
        return {'label': label, 'expression': ' + '.join(f'{v:.2f}{k}k' for k, v in factors.items()),
                'factors': dict(factors), 'area_load_kN_m2': area,
                'line_load_N_mm': area * width / 1000, **extra}

    uls = [combination(f'LC{i}', factors, kmod=kmod)
           for i, (factors, kmod) in enumerate(uls_patterns, 1)]
    return {'id': slab.get('id'), 'guid': slab.get('guid'), 'scenario': load_case,
            'source': SOURCE, 'width_mm': width, 'actions_kN_m2': actions,
            'characteristic': {'self_weight_kN_m2': sw, 'self_weight_source': sw_source,
                               'additional_dead_kN_m2': topping, 'Gk_kN_m2': actions['G'],
                               'Qk_kN_m2': actions['Q'], 'Sk_kN_m2': actions['S'], 'Wk_kN_m2': actions['W']},
            'parameters': {'service_class': 1, 'consequence_class': 'CC2', 'psi': psi},
            'uls': uls,
            'assumptions': ['Scenario assigned explicitly, not verified from IFC use.',
                            'Report downward uniform load cases only.',
                            'Check every ULS combination with its own kmod.']}



# -----------------------------------------------------------------------------
# Batch analysis of IFC slabs. Existing get_loads() remains the Toolbox API.
# -----------------------------------------------------------------------------
from pathlib import Path
import json
import hashlib
import itertools
import csv

CATEGORY_LOADS = {'C1': 2.5, 'C2': 4.0, 'C3': 5.0, 'C4': 5.0, 'E': 7.5}
WIND_REGIONS = {'I': {'pressure': .29, 'suction': -1.51},
                'II': {'pressure': .25, 'suction': -1.29}}
# Report p.8: loads; p.10: net roof pressures. DK NA 2021 Table A1.1:
# C psi0/1/2=.6/.6/.5; E=.8/.8/.7; leading wind excludes snow.
# Do not reproduce inconsistent E factors in report Table 3.8.
BATCH_SOURCE = 'Report printed pp.8,10-13; DK EN1990 NA2021 Table A1.1; Appendix3'


def read_ifc_slabs(path):
    """Same KLH filter/short-side rule as the supplied main, with GUIDs.

    Imports IfcOpenShell only here. Geometry dimensions are NOT verified spans.
    Area uses the IFC AREAUNIT scale separately from length units.
    """
    import ifcopenshell
    from ifcopenshell.util import element, unit
    model = ifcopenshell.open(str(path))
    mm_scale = unit.calculate_unit_scale(model) * 1000
    area_scale = unit.calculate_unit_scale(model, 'AREAUNIT')
    result = []
    for item in model.by_type('IfcSlab'):
        if 'KLH' not in (item.Name or ''):
            continue
        q = element.get_psets(item).get('Qto_SlabBaseQuantities', {})
        sides = [_number(q.get(k, 0), k) * mm_scale for k in ('Length', 'Width')]
        if min(sides) < 1000:
            continue
        material = element.get_material(item, should_skip_usage=True)
        if material is None or not material.is_a('IfcMaterialLayerSet'):
            raise ValueError(f'No material layers for IFC slab #{item.id()}')
        layers = [(float(l.LayerThickness)*mm_scale,
                   l.Material.Name if l.Material else 'unknown') for l in material.MaterialLayers]
        slab_type = element.get_type(item)
        storey = element.get_container(item)
        result.append({'id': item.id(), 'guid': item.GlobalId, 'name': item.Name,
                       'type': slab_type.Name.split(':')[-1] if slab_type and slab_type.Name else 'unknown',
                       'storey': storey.Name if storey else 'unknown', 'layers': layers,
                       'thickness_mm': sum(t for t, _ in layers),
                       'span_mm': min(sides), 'length_mm': max(sides),
                       'area_m2': float(q.get('NetArea', 0))*area_scale,
                       'span_source': 'IFC short dimension; supports not verified'})
    validate_slab_list(result)
    return result


def validate_slab_list(slabs):
    if not slabs:
        raise ValueError('No KLH slabs found.')
    guids = set()
    for slab in slabs:
        guid = slab.get('guid')
        if not guid or guid in guids:
            raise ValueError('Every slab needs a unique, nonempty GUID.')
        guids.add(guid)
        for key in ('span_mm', 'thickness_mm'):
            _number(slab[key], key, positive=True)


def obtain_slabs(*, ifc_path=None, main_path=None, input_path=None):
    """Use --ifc, --main (open_model/get_clt_slabs), config or optional slab JSON."""
    if sum(x is not None for x in (ifc_path, main_path, input_path)) > 1:
        raise ValueError('Choose only one input: --ifc, --main, --input.')
    if main_path:
        import importlib.util
        import sys
        path = Path(main_path).resolve()
        spec = importlib.util.spec_from_file_location('_clt_user_extractor', path)
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(path.parent))
        try:
            spec.loader.exec_module(module)
            slabs = module.get_clt_slabs(module.open_model(module.MODEL_PATH))
        finally:
            sys.path.pop(0)
        validate_slab_list(slabs)
        return slabs, f'Extractor: {path}'
    if ifc_path:
        return read_ifc_slabs(ifc_path), f'Live IFC: {Path(ifc_path).resolve()}'
    if input_path:
        data = json.loads(Path(input_path).read_text(encoding='utf-8'))
        slabs = data['slabs'] if isinstance(data, dict) else data
        validate_slab_list(slabs)
        return slabs, f'JSON input: {Path(input_path).resolve()}'
    config = Path(__file__).resolve().with_name('config.py')
    if config.is_file():
        import runpy
        model_path = Path(runpy.run_path(str(config))['MODEL_PATH'])
        if not model_path.is_absolute():
            model_path = config.parent/model_path
        return read_ifc_slabs(model_path), f'Live IFC via config.py: {model_path}'
    raise ValueError('No IFC source selected. Place config.py with MODEL_PATH beside the scripts, or pass --main main_2.py / --ifc MODEL.ifc.')


# Report-derived assignments embedded here: no external JSON is required.
# GUID is the stable key; IFC numeric IDs in comments are for locating rows.
# Tuple: (structural_zone, role, floor_category, wind_region, source).
# Graphic inference remains subject to review; zone never scales loads.
REPORT_ASSIGNMENTS = {
    '3Q94u7fkv5APMhQVYLZWlh': (1, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22158
    '3Q94u7fkv5APMhQVYLZWic': (1, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22224
    '3Q94u7fkv5APMhQVYLZWdj': (1, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22260
    '3Q94u7fkv5APMhQVYLZWdG': (1, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22296
    '3Q94u7fkv5APMhQVYLZWao': (1, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22332
    '3Q94u7fkv5APMhQVYLZWaM': (1, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22368
    '3Q94u7fkv5APMhQVYLZWbu': (1, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22404
    '3Q94u7fkv5APMhQVYLZWbZ': (1, 'floor', 'E', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22440
    '3Q94u7fkv5APMhQVYLZWb0': (1, 'floor', 'E', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22476
    '3Q94u7fkv5APMhQVYLZWQa': (1, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22512
    '3Q94u7fkv5APMhQVYLZWQF': (1, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22548
    '3Q94u7fkv5APMhQVYLZWRn': (1, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22584
    '3Q94u7fkv5APMhQVYLZWRJ': (1, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22620
    '3Q94u7fkv5APMhQVYLZWOr': (1, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22656
    '3Q94u7fkv5APMhQVYLZWOG': (1, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22692
    '3Q94u7fkv5APMhQVYLZWPw': (1, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22728
    '3Q94u7fkv5APMhQVYLZWPS': (1, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22764
    '3Q94u7fkv5APMhQVYLZWP6': (1, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22800
    '0Jpez8be91A8Qcbjngrg$p': (1, 'floor', 'C3', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22836
    '0Jpez8be91A8Qcbjngrg$I': (1, 'floor', 'C3', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22872
    '0Jpez8be91A8Qcbjngrgyp': (1, 'floor', 'C3', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22908
    '0Jpez8be91A8QcbjngrgyL': (1, 'floor', 'C3', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22944
    '24xRcBfoTAuOCJavVSBhBN': (1, 'floor', 'C3', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 22980
    '24xRcBfoTAuOCJavVSBhCt': (1, 'floor', 'C3', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23016
    '24xRcBfoTAuOCJavVSBhCU': (1, 'floor', 'C3', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23052
    '24xRcBfoTAuOCJavVSBhD$': (1, 'floor', 'E', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23088
    '24xRcBfoTAuOCJavVSBhDV': (1, 'floor', 'E', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23124
    '24xRcBfoTAuOCJavVSBhEv': (1, 'floor', 'C3', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23160
    '24xRcBfoTAuOCJavVSBhEU': (1, 'floor', 'C3', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23196
    '24xRcBfoTAuOCJavVSBhFy': (1, 'floor', 'C3', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23232
    '24xRcBfoTAuOCJavVSBhFN': (1, 'floor', 'C3', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23268
    '24xRcBfoTAuOCJavVSBhFE': (1, 'floor', 'C3', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23304
    '199TjqPDTBawDd4skGv7$M': (1, 'floor', 'C3', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23340
    '199TjqPDTBawDd4skGv7$l': (1, 'floor', 'C3', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23376
    '1xtytahNvBmets3goGVgic': (1, 'floor', 'C3', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23412
    '3Eq6k5tGH5wgtF_cR3ZT8b': (1, 'floor', 'C3', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23448
    '3Eq6k5tGH5wgtF_cR3ZTB7': (1, 'floor', 'E', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23484
    '1MzTiDj9z7xhLagQSa7Gzo': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23520
    '1MzTiDj9z7xhLagQSa7Gzw': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23566
    '1MzTiDj9z7xhLagQSa7Gw2': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23602
    '1MzTiDj9z7xhLagQSa7GwA': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23638
    '1MzTiDj9z7xhLagQSa7GwI': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23674
    '1MzTiDj9z7xhLagQSa7GwQ': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23710
    '1MzTiDj9z7xhLagQSa7GwY': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23746
    '1MzTiDj9z7xhLagQSa7Gwg': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23782
    '1MzTiDj9z7xhLagQSa7Gwo': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23818
    '1MzTiDj9z7xhLagQSa7Gww': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23854
    '1MzTiDj9z7xhLagQSa7Gx2': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23890
    '1MzTiDj9z7xhLagQSa7GxA': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23926
    '1MzTiDj9z7xhLagQSa7GxI': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23962
    '1MzTiDj9z7xhLagQSa7GxQ': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 23998
    '1MzTiDj9z7xhLagQSa7GxY': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 24034
    '1MzTiDj9z7xhLagQSa7Gxg': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 24070
    '1MzTiDj9z7xhLagQSa7Gxo': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 24106
    '1MzTiDj9z7xhLagQSa7Gxw': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 24142
    '1MzTiDj9z7xhLagQSa7Gu2': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 24178
    '2mHIAaUjv13BSZee8xfzJO': (2, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 24309
    '2mHIAaUjv13BSZee8xfzH$': (2, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 24345
    '2mHIAaUjv13BSZee8xfzHS': (2, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 24381
    '2mHIAaUjv13BSZee8xfzUw': (2, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 24417
    '2mHIAaUjv13BSZee8xfzUO': (2, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 24453
    '2mHIAaUjv13BSZee8xfzU6': (2, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 24489
    '2mHIAaUjv13BSZee8xfzVd': (2, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 24525
    '2mHIAaUjv13BSZee8xfzS_': (2, 'roof', None, 'II', 'Structural sheet K09_C08_ZLevel2 PDF418 explicitly labels lateral wing P401; report Fig.3.3b; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 24561
    '2mHIAaUjv13BSZee8xfzSs': (2, 'roof', None, 'II', 'Structural sheet K09_C08_ZLevel2 PDF418 explicitly labels lateral wing P401; report Fig.3.3b; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 24597
    '2mHIAaUjv13BSZee8xfzSk': (2, 'roof', None, 'II', 'Structural sheet K09_C08_ZLevel2 PDF418 explicitly labels lateral wing P401; report Fig.3.3b; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 24633
    '2mHIAaUjv13BSZee8xfzSc': (2, 'roof', None, 'II', 'Structural sheet K09_C08_ZLevel2 PDF418 explicitly labels lateral wing P401; report Fig.3.3b; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 24669
    '2mHIAaUjv13BSZee8xfzSU': (2, 'roof', None, 'II', 'Structural sheet K09_C08_ZLevel2 PDF418 explicitly labels lateral wing P401; report Fig.3.3b; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 24705
    '2mHIAaUjv13BSZee8xfzSM': (2, 'roof', None, 'II', 'Structural sheet K09_C08_ZLevel2 PDF418 explicitly labels lateral wing P401; report Fig.3.3b; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 24741
    '2mHIAaUjv13BSZee8xfzSE': (2, 'roof', None, 'II', 'Structural sheet K09_C08_ZLevel2 PDF418 explicitly labels lateral wing P401; report Fig.3.3b; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 24777
    '3RkjpzjozBoeiBL19n3SLY': (1, 'floor', 'C3', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 31880
    '3pf39X1Db1_fwOhiKfB528': (1, 'floor', 'C3', None, 'Fig.3.4, printed p.12; structural sheet K09_C08_ZLevel2, PDF418; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 31916
    '2j9K9M5KH1UPNFbIDRbx_8': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 31983
    '12NaNPyjv23QVQiqBH2kGe': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 33092
    '12NaNPyjv23QVQiqBH2kSz': (1, 'roof', None, 'I', 'Roof sheet K09_C08_ZRoof PDF419, P401; report Fig.3.3a; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 33128
    '1fA00WNOX0zvIcAa2xGeAz': (1, 'floor', 'E', None, 'Fig.3.5a, printed p.13; structural sheet K09_C08_ZLevel1, PDF417; maximum category intersecting panel bbox, applied uniformly for screening; structural zone inferred from position and report Fig.3.1/Appendix11; no load reduction by zone'),  # IFC ID 33356
}

# Optional reviewed per-GUID changes (span, category, bearing data, etc.).
# Example: ASSIGNMENT_OVERRIDES = {"GUID": {"span_mm": 3200}}
ASSIGNMENT_OVERRIDES = {}


def embedded_assignments(slabs):
    """Return independent assignments for these GUIDs; never guess an unknown GUID."""
    from copy import deepcopy
    result = {}
    for slab in slabs:
        guid = slab['guid']
        if guid not in REPORT_ASSIGNMENTS:
            raise ValueError(f'No built-in load assignment for IFC slab {slab.get("id")}, GUID {guid}. Update REPORT_ASSIGNMENTS in loads.py.')
        zone, role, category, region, source = REPORT_ASSIGNMENTS[guid]
        entry = {'structural_zone': zone, 'role': role, 'zone_source': source,
                 'load_zone_method': 'report_spatial_inference', 'load_zone_reviewed': False,
                 'span_confirmed': False, 'orientation_confirmed': False,
                 'supports_confirmed': False, 'rolling_shear_confirmed': False,
                 'equipment_reviewed': False}
        if category is not None: entry['category'] = category
        if region is not None: entry['wind_region'] = region
        if role == 'roof': entry['include_maintenance'] = True
        entry.update(deepcopy(ASSIGNMENT_OVERRIDES.get(guid, {})))
        result[guid] = entry
    return result


def read_assignments(path, slabs):
    """Use assignments embedded in loads.py; optional explicit file override."""
    if path is None:
        assignments = embedded_assignments(slabs)
    else:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        assignments = data.get('assignments', data)
    known = {s['guid'] for s in slabs}
    if set(assignments) - known:
        raise ValueError('Assignments contain GUIDs absent from this model.')
    allowed = {'role', 'category', 'wind_region', 'span_mm', 'span_confirmed',
               'orientation_confirmed', 'supports_confirmed', 'additional_dead_kN_m2',
               'rolling_shear_k_MPa', 'rolling_shear_confirmed', 'kmod_imposed',
               'bearing_length_mm', 'bearing_fc90_k_MPa', 'bearing_kc90',
               'equipment_reviewed', 'zone_source', 'include_maintenance',
               'load_zone_reviewed', 'load_zone_method', 'structural_zone'}
    for guid, a in assignments.items():
        if not isinstance(a, dict) or set(a)-allowed:
            raise ValueError(f'Unknown assignment fields for {guid}.')
        for key in ('span_confirmed', 'orientation_confirmed', 'supports_confirmed',
                    'rolling_shear_confirmed', 'equipment_reviewed', 'include_maintenance', 'load_zone_reviewed'):
            if key in a and not isinstance(a[key], bool):
                raise ValueError(f'{key} must be a JSON boolean.')
        if a.get('structural_zone') is not None and (isinstance(a['structural_zone'],bool) or a['structural_zone'] not in (1,2,3)):
            raise ValueError('structural_zone must be 1, 2 or 3; it does not reduce loads.')
        if a.get('category') is not None and a['category'] not in CATEGORY_LOADS:
            raise ValueError('Category must be C1/C2/C3/C4/E.')
        if a.get('role') is not None and a['role'] not in ('floor', 'roof', 'terrace'):
            raise ValueError('Role must be floor, roof or terrace.')
        if a.get('wind_region') is not None and a['wind_region'] not in WIND_REGIONS:
            raise ValueError('wind_region must be I or II.')
    return assignments


def candidate_scenarios(slab, assignment=None):
    """Candidate roles/categories are a screening policy, NOT actual use.

    Roof 2: roof candidate. Level1/2 140 mm: floor candidates.
    Level2 130 mm: BOTH floor and roof candidates (unresolved lower wing).
    Unknown storeys/types: both. An explicit assignment narrows candidates.
    """
    a = assignment or {}
    if a.get('role'):
        roles = [a['role']]
    elif slab.get('storey') == 'Roof 2':
        roles = ['roof']
    elif slab.get('storey') == 'Level 2' and '130' in slab.get('type', ''):
        roles = ['floor', 'roof', 'terrace']
    elif slab.get('storey') in ('Level 1', 'Level 2') and '140' in slab.get('type', ''):
        roles = ['floor']
    else:
        roles = ['floor', 'roof']
    scenarios = []
    for role in roles:
        if role == 'floor':
            for cat in ([a['category']] if a.get('category') else CATEGORY_LOADS):
                scenarios.append({'role': role, 'category': cat, 'name': 'floor_'+cat})
        else:
            for region in ([a['wind_region']] if a.get('wind_region') else WIND_REGIONS):
                for sign in ('pressure', 'suction'):
                    scenarios.append({'role': role, 'region': region, 'wind_case': sign,
                                      **({'category':a.get('category') or 'C3'} if role=='terrace' else {}),
                                      'name': f'{role}_{region}_{sign}'})
            # Appendix2 lists qroof=1.5. Separate maintenance candidate, NOT
            # superposed on snow/wind. Category H combination factors are zero.
            if role=='roof' and a.get('include_maintenance', True):
                scenarios.append({'role': 'roof', 'category': 'H', 'name': 'roof_maintenance'})
    return scenarios


def get_project_loads(slab, scenario, assignment=None):
    """Signed downward-positive UDL cases, simply supported strip screening.

    ULS STR: G-only 1.2G and 1G; variable leading 1.5, companions
    1.5*psi0, including variable absence and favourable G=.9.
    Each resulting net load is analysed, including reversal by suction.
    This is STR panel bending/shear, NOT an EQU/UPL anchorage certification.
    E duration assumed long-term kmod=.7; C medium-term=.8; H short=.9.
    These durations remain modelling assumptions until a reviewer confirms.
    """
    a = assignment or {}
    width = _number(slab.get('properties', {}).get('section', {}).get('width_mm', 1000), 'width', positive=True)
    sw = calculate_self_weight(slab['thickness_mm'])
    topping = _number(a.get('additional_dead_kN_m2', 1.2), 'additional_dead')
    actions = {'G': sw+topping}
    role = scenario['role']
    if role == 'floor' or scenario.get('category') == 'H':
        cat = scenario['category']
        actions['Q'] = 1.5 if cat == 'H' else CATEGORY_LOADS[cat]
        psi = {'Q': (0. if cat == 'H' else .8 if cat == 'E' else .6)}
        kmod = {'Q': _number(a.get('kmod_imposed', .7 if cat == 'E' else .9 if cat == 'H' else .8), 'kmod_imposed', positive=True)}
        if kmod['Q'] > 1.1:
            raise ValueError('kmod_imposed >1.1 is outside this SC1 screening implementation.')
    else:
        actions.update(S=.8, W=WIND_REGIONS[scenario['region']][scenario['wind_case']])
        psi = {'S': .3, 'W': .3}
        kmod = {'S': .9, 'W': 1.1}
        if role=='terrace':
            cat=scenario['category']
            actions['Q']=CATEGORY_LOADS[cat]
            psi['Q']=.8 if cat=='E' else .6
            kmod['Q']=_number(a.get('kmod_imposed',.7 if cat=='E' else .8),'kmod_imposed',positive=True)
    variables = [k for k in actions if k != 'G']

    def combo(label, factors, **extra):
        q = sum(actions[k]*v for k,v in factors.items())
        return {'label': label, 'expression': ' + '.join(f'{v:g}{k}k' for k,v in factors.items()),
                'factors': factors, 'area_load_kN_m2': q, 'line_load_N_mm': q*width/1000, **extra}

    uls = [combo('G12', {'G': 1.2}, kmod=.6), combo('G10', {'G': 1.}, kmod=.6)]
    for leader in variables:
        companions = [k for k in variables if k != leader]
        for present in itertools.product((False, True), repeat=len(companions)):
            factors = {leader: 1.5}
            for k, yes in zip(companions, present):
                factor = 0. if leader == 'W' and k == 'S' else 1.5*(.6 if leader=='Q' and scenario.get('category')=='E' and k in ('S','W') else psi[k])
                if yes and factor:
                    factors[k] = factor
            for gf in (1., .9):
                f = {'G': gf, **factors}
                key = tuple(f.items())
                if any(tuple(c['factors'].items()) == key for c in uls):
                    continue
                uls.append(combo(f'U{len(uls)+1}', f, kmod=max(kmod[k] for k in factors)))
    # ULS companion-only patterns, used in Toolbox too; leading cases above
    # still evaluated even if another case has a larger total load.
    for k in variables:
        if psi[k]:
            uls.append(combo(f'U{len(uls)+1}', {'G':1., k:1.5*psi[k]}, kmod=kmod[k]))
    return {'scenario':scenario['name'], 'scenario_definition':dict(scenario), 'source':BATCH_SOURCE,
            'structural_zone':a.get('structural_zone'), 'zone_load_reduction_factor':1.0,
            'width_mm':width, 'actions_kN_m2':actions,
            'characteristic':{'self_weight_kN_m2':sw,'additional_dead_kN_m2':topping,
                              'Gk_kN_m2':actions['G'],'Qk_kN_m2':actions.get('Q',0),
                              'Sk_kN_m2':actions.get('S',0),'Wk_kN_m2':actions.get('W',0)},
            'parameters':{'psi':psi,'kmod_by_action':kmod}, 'uls':uls,
            'assumptions':['Uniform UDL; worst roof wind values are global screening envelopes, not local zone assignment.',
                           'No equipment point loads, snow drift, transfer loads or connection resistance inferred.',
                           'Storage kmod=.7 assumes long-term loading; other occupancy durations also require review.',
                           'SC1, CC2; 1.2 kPa topping includes partition allowance already.']}


def export_loads(slabs, assignments, folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    rows=[];details=[]
    for slab in slabs:
        a=assignments.get(slab['guid'],{})
        for scenario in candidate_scenarios(slab,a):
            loads=get_project_loads(slab,scenario,a)
            details.append({'id':slab['id'],'guid':slab['guid'],'loads':loads})
            for state in ('uls',):
                for c in loads[state]:
                    rows.append({'id':slab['id'],'guid':slab['guid'],'storey':slab['storey'],
                                 'structural_zone':a.get('structural_zone'),'scenario':loads['scenario'],'state':state,'combination':c['label'],
                                 'expression':c['expression'],'family':c.get('family','STR'),
                                 'area_load_kPa':c['area_load_kN_m2'],'line_load_N_mm':c['line_load_N_mm'],
                                 'kmod':c.get('kmod',''),'assignment_status':('REPORT_INFERRED' if a.get('load_zone_method')=='report_spatial_inference' else 'EXPLICIT' if a.get('role') else 'CANDIDATE')})
    with (folder/'loads_all.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (folder/'loads_all.json').write_text(json.dumps(details,indent=2,allow_nan=False),encoding='utf-8')
    return rows


def add_input_arguments(parser):
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--ifc',help='Read current IFC directly; requires ifcopenshell.')
    group.add_argument('--main',help='Use the supplied extractor module, e.g. main_2.py.')
    group.add_argument('--input',help='Read JSON slab list or supplied IFC snapshot.')
    parser.add_argument('--assignments',help='Per-GUID load/support review JSON.')
    parser.add_argument('--out',default=str(Path(__file__).resolve().parent/'output'),help='Output directory.')


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description='CLT loads for every slab: report scenarios and combinations.')
    add_input_arguments(parser);args=parser.parse_args()
    slabs,source=obtain_slabs(ifc_path=args.ifc,main_path=args.main,input_path=args.input)
    assignments=read_assignments(args.assignments,slabs)
    rows=export_loads(slabs,assignments,args.out)
    print(source)
    print(f'{len(slabs)} slabs; {len(rows)} load-combination rows saved to {args.out}')
    print('Unassigned loads are candidate scenarios, not confirmed actual loads.')


#==================================================================================
# 9. SLS LOADS AND LOAD COMBINATIONS
# ===================================================================================

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