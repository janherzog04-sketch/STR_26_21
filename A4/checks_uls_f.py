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
from loads_2 import _number, get_loads


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
    if not loads['uls']:
        raise ValueError('No ULS combinations supplied.')
    for c in loads['uls']:
        signed_q = float(c['line_load_N_mm'])
        if not math.isfinite(signed_q):
            raise ValueError('Line load must be finite.')
        q = abs(signed_q)
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
        rows.append({'signed_q_N_mm':signed_q,'signed_M_Nmm':signed_q*L**2/8,
                     'signed_V_N':signed_q*L/2,'label': c['label'], 'expression': c['expression'], 'kmod': kmod,
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



# -----------------------------------------------------------------------------
# Batch checks and final tables. All results retain unresolved model assumptions.
# -----------------------------------------------------------------------------
from pathlib import Path
from copy import deepcopy
import csv
import json
from loads_2 import (candidate_scenarios,get_project_loads,validate_slab_list,
                   obtain_slabs,read_assignments,export_loads,add_input_arguments)


def _pending_items(slab, a, scenarios):
    pending=[]
    if a.get('load_zone_method')=='report_spatial_inference' and not a.get('load_zone_reviewed'):
        pending.append('report plan registration/boundaries and uniform maximum-zone load require review')
    if not a.get('role'):
        pending.append('actual floor/roof role not explicitly assigned')
    if any(s['role'] in ('floor','terrace') for s in scenarios) and not a.get('category'):
        pending.append('occupancy category/location or mixed zones unresolved')
    if any('region' in s for s in scenarios) and not a.get('wind_region'):
        pending.append('wind region/local pressure zoning unresolved')
    for key,text in [('span_confirmed','short side is not a verified structural span'),
                     ('orientation_confirmed','XX grain direction relative to span unverified'),
                     ('supports_confirmed','simply supported strip assumption unverified'),
                     ('rolling_shear_confirmed','rolling shear strength applicability unverified'),
                     ('equipment_reviewed','equipment/point/line loads and snow accumulation not reviewed')]:
        if not a.get(key):pending.append(text)
    if not a.get('zone_source'):
        pending.append('load-zone source/cross-reference missing')
    if any(s.get('category')=='E' for s in scenarios) and 'kmod_imposed' not in a:
        pending.append('storage duration assumed long-term, kmod=0.7')
    return pending


def _bearing_and_uplift(result, assignment, width):
    """Simple uniform contact demand only, for equal support lengths.

    Requires caller-supplied verified effective bearing length, fc90,k and
    kc90; none are guessed. Full local/notch/connection checks remain separate.
    Negative reaction is anchorage demand, not negative bearing compression.
    """
    keys=('bearing_length_mm','bearing_fc90_k_MPa','bearing_kc90')
    provided=[assignment.get(k) is not None for k in keys]
    if any(provided) and not all(provided):
        raise ValueError('Bearing needs length, fc90,k and kc90 together.')
    uplift=max(max(0.,-r['signed_V_N']) for r in result['results'])
    out={'uplift_per_support_N':uplift,'bearing_status':'NOT_EVALUATED',
         'anchorage_status':'NOT_EVALUATED','bearing_utilization':None}
    if all(provided):
        length,fc,kc=(_number(assignment[k],k,positive=True) for k in keys)
        ratios=[]
        for row in result['results']:
            stress=max(0.,row['signed_V_N'])/(width*length)
            resistance=row['kmod']*fc*kc/result['gamma_M']
            ratios.append((stress/resistance,row['label']))
        ratio,label=max(ratios)
        out.update(bearing_utilization=ratio,bearing_governing_combination=label,
                   bearing_status='CONDITIONAL_WITHIN' if ratio<=1 else 'EXCEEDS',
                   bearing_model='Uniform support contact; caller-provided effective contact length.')
    return out


def run_all_slabs(slabs, *, assignments=None, output_dir=None):
    """Use this directly after slabs=get_clt_slabs(model) in the user's main.

    Calculates the THREE implemented ULS panel checks for every load candidate
    and combination, retaining each candidate. Optional uniform bearing demand
    is evaluated only with supplied support/material data. No final building
    certificate or SLS/vibration verdict is generated.
    """
    validate_slab_list(slabs)
    assignments=read_assignments(None,slabs) if assignments is None else assignments
    if set(assignments)-{s['guid'] for s in slabs}:
        raise ValueError('Assignment contains unknown GUID.')
    summaries=[];scenario_rows=[];combination_rows=[];details=[];errors=[]
    for original in slabs:
        slab=deepcopy(original)
        a=assignments.get(slab['guid'],{})
        if a.get('span_mm') is not None:
            slab['span_mm']=_number(a['span_mm'],'span override',positive=True)
        base={'id':slab['id'],'guid':slab['guid'],'type':slab['type'],'storey':slab['storey'],
              'thickness_mm':slab['thickness_mm'],'span_mm':slab['span_mm'],
              'structural_zone':a.get('structural_zone')}
        try:
            scenarios=candidate_scenarios(slab,a)
            pending=_pending_items(slab,a,scenarios)
            rolling=a.get('rolling_shear_k_MPa',1.2)
            slab['properties']=get_material_properties(slab,orientation_confirmed=a.get('orientation_confirmed',False),
                                                       rolling_shear_k_MPa=rolling)
            cases=[]
            for scenario in scenarios:
                slab['loads']=get_project_loads(slab,scenario,a)
                result=check_uls(slab,reference_mode=True)
                extras=_bearing_and_uplift(result,a,slab['loads']['width_mm'])
                ratios=result['maximum_utilization']
                candidates=dict(ratios)
                if extras['bearing_utilization'] is not None:
                    candidates['bearing']=extras['bearing_utilization']
                controlling=max(candidates,key=candidates.get)
                overall=candidates[controlling]
                row={**base,'scenario':scenario['name'],
                     **{k+'_pct':100*v for k,v in ratios.items()},
                     'rolling_at_0_8_pct':100*ratios['rolling_shear']*rolling/.8,
                     'bearing_pct':None if extras['bearing_utilization'] is None else 100*extras['bearing_utilization'],
                     'uplift_per_support_N':extras['uplift_per_support_N'],
                     'governing_check':controlling,'max_pct':overall*100,
                     'combination':(extras['bearing_governing_combination'] if controlling=='bearing'
                                    else result['governing_combinations'][controlling]),
                     'Gk_kPa':slab['loads']['actions_kN_m2']['G'],
                     'Qk_kPa':slab['loads']['actions_kN_m2'].get('Q',0.),
                     'Sk_kPa':slab['loads']['actions_kN_m2'].get('S',0.),
                     'Wk_kPa':slab['loads']['actions_kN_m2'].get('W',0.),
                     'EI_eff_Nmm2':slab['properties']['section']['EI_eff_Nmm2'],
                     'rolling_shear_k_MPa':rolling,
                     'status':'EXCEEDS_IN_SCENARIO' if overall>1 else 'CONDITIONAL_WITHIN',
                     'bearing_status':extras['bearing_status'],
                     'anchorage_status':extras['anchorage_status'],
                     'pending':' | '.join(pending)}
                scenario_rows.append(row)
                for c in result['results']:
                    combination_rows.append({**base,'scenario':scenario['name'],'combination':c['label'],
                       'expression':c['expression'],'signed_q_N_mm':c['signed_q_N_mm'],
                       'kmod':c['kmod'],'M_kNm':c['M_Nmm']/1e6,'signed_M_kNm':c['signed_M_Nmm']/1e6,
                       'V_kN':c['V_N']/1000,'signed_reaction_kN':c['signed_V_N']/1000,
                       'sigma_m_MPa':c['sigma_m_MPa'],'tau_longitudinal_MPa':c['tau_longitudinal_MPa'],
                       'tau_rolling_MPa':c['tau_rolling_MPa'],
                       **{k+'_pct':100*v for k,v in c['utilization'].items()}})
                cases.append({'loads':deepcopy(slab['loads']),'checks':result,'support_checks':extras,'summary':row})
            selected=max((c['summary'] for c in cases),key=lambda r:r['max_pct'])
            summary=dict(selected)
            summary['scenario_count']=len(scenarios)
            summary['role_status']=('REPORT_INFERRED' if a.get('load_zone_method')=='report_spatial_inference' else 'EXPLICIT' if a.get('role') else 'CANDIDATE')
            summary['scenario']=selected['scenario']
            # Independent envelopes: different checks can govern in different cases.
            for key in ('bending_pct','longitudinal_shear_pct','rolling_shear_pct','rolling_at_0_8_pct','uplift_per_support_N'):
                summary[key]=max(c['summary'][key] for c in cases)
            if any(c['summary']['bearing_pct'] is not None for c in cases):
                summary['bearing_pct']=max(c['summary']['bearing_pct'] or 0 for c in cases)
            for check in ('bending','longitudinal_shear','rolling_shear'):
                governing_case=max(cases,key=lambda c:c['summary'][check+'_pct'])
                summary[check+'_scenario']=governing_case['summary']['scenario']
                summary[check+'_combination']=governing_case['checks']['governing_combinations'][check]
            summaries.append(summary)
            details.append({'slab':{k:v for k,v in slab.items() if k not in ('loads','properties')},
                            'properties':slab['properties'],'assignment':a,'pending':pending,'scenarios':cases,
                            'checks_not_completed':['SLS deflection/vibration (person 3)',
                            'connections/anchorage resistance','notches/openings/point-support punching',
                            'fire/ALS','nonuniform loading, drift and equipment-specific demands',
                            *(['support bearing'] if extras['bearing_utilization'] is None else [])]})
        except (ValueError,KeyError,TypeError,IndexError) as exc:
            errors.append({**base,'status':'ERROR','error':str(exc)})
            summaries.append({**base,'status':'ERROR','error':str(exc)})
    if output_dir is not None:
        folder=Path(output_dir);folder.mkdir(parents=True,exist_ok=True)
        for filename,rows in [('uls_summary.csv',summaries),('uls_scenarios.csv',scenario_rows),('uls_combinations.csv',combination_rows)]:
            keys=list(dict.fromkeys(k for row in rows for k in row))
            with (folder/filename).open('w',newline='',encoding='utf-8-sig') as f:
                writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader();writer.writerows(rows)
        (folder/'uls_details.json').write_text(json.dumps({'scope':'Conditional one-way ULS strip screening; no global PASS.',
            'summary':summaries,'details':details,'errors':errors},indent=2,allow_nan=False),encoding='utf-8')
        # Always preserve an independent assignment template; never overwrite
        # a file which the user may have reviewed/edited.
        template=folder/'assignments_template.json'
        if not template.exists():
            template.write_text(json.dumps({'instructions':'Copy to assignments.json and fill only verified values. Null leaves candidate scenarios.',
                'assignments':{s['guid']:{'role':None,'category':None,'wind_region':None,
                    'span_confirmed':False,'orientation_confirmed':False,'supports_confirmed':False,
                    'rolling_shear_confirmed':False,'equipment_reviewed':False,'zone_source':''} for s in slabs}},indent=2),encoding='utf-8')
    return {'summary':summaries,'scenarios':scenario_rows,'combinations':combination_rows,'errors':errors,'details':details}



def print_toolbox_comparison(batch, output_dir=None):
    """Append ULS-only comparison. References are separate from IFC results.

    A per-element comparison requires an explicitly assigned role/category and
    matching strip width, thickness, span (0.5 mm tolerance), characteristic
    actions, material edition and resistance factors. Never compare floor_E
    or maintenance envelope percentages with the P301/P401 reference as if
    the loads were equal. Missing assignments do not establish equivalence.
    """
    references={'P301':{'bending':29.18,'longitudinal_shear':9.57,'rolling_shear':21.00},
                'P401':{'bending':11.47,'longitudinal_shear':3.20,'rolling_shear':6.70}}
    print('\nTOOLBOX - ULS REFERENCE CASES (independent reference tests, not all IFC slabs)')
    print(f"{'Case':<6} {'Check':<22} {'Our %':>9} {'Toolbox %':>10} {'Delta pp':>10}")
    for name,reference in references.items():
        _,calculated=reference_slab(name)
        for check,value in reference.items():
            our=100*calculated['maximum_utilization'][check]
            print(f'{name:<6} {check:<22} {our:>9.2f} {value:>10.2f} {our-value:>10.2f}')
    print('Our inputs: CLT unit weight 5.5 kN/m3, ETA2017; L=3.20m, width=1m.')
    print('Toolbox 75/83% are SLS maxima and are not ULS comparison targets.')

    matches=[]
    for item in batch['details']:
        slab=item['slab'];a=item['assignment'];props=item['properties'];sec=props['section']
        if not a.get('role'):
            continue
        common=(abs(sec['span_mm']-3200)<=.5 and abs(sec['width_mm']-1000)<1e-6
                and props['material'].get('E0_mean_MPa')==12000
                and props['material'].get('E90_mean_MPa')==370
                and props['material'].get('G90_mean_MPa')==50
                and props['material'].get('fm_k_MPa')==24
                and props['material'].get('fv_k_MPa')==2.7
                and props['rolling_shear_k_MPa']==1.2)
        if not common:
            continue
        for case in item['scenarios']:
            load=case['loads'];result=case['checks'];actions=load['actions_kN_m2']
            if result['gamma_M']!=1.19 or result['ksys']!=1.0:
                continue
            name=None
            if (a.get('role')=='floor' and a.get('category')=='C3'
                    and abs(slab['thickness_mm']-140)<.1
                    and abs(actions.get('G',0)-1.97)<1e-6
                    and abs(actions.get('Q',0)-5)<1e-6
                    and not actions.get('W',0) and not actions.get('S',0)
                    and result['maximum_utilization']
                    and all(abs(c['kmod']-.8)<1e-6 for c in result['results'] if 'Qk' in c['expression'])):
                name='P301'
            elif (a.get('role')=='roof' and abs(slab['thickness_mm']-130)<.1
                    and abs(actions.get('G',0)-1.915)<1e-6
                    and abs(actions.get('S',0)-.8)<1e-6
                    and abs(actions.get('W',0)-.3)<1e-6 and not actions.get('Q',0)):
                name='P401'
            if name is None:
                continue
            row={'id':slab['id'],'guid':slab['guid'],'reference':name,
                 'scenario':load['scenario'],'span_mm':sec['span_mm'],
                 'comparison_status':'CONDITIONAL_COMPARABLE_STRIP'}
            for check,value in references[name].items():
                row[check+'_pct']=100*result['maximum_utilization'][check]
                row[check+'_toolbox_pct']=value
                row[check+'_delta_pp']=row[check+'_pct']-value
            matches.append(row)
    print('\nIFC STRIPS COMPARABLE TO TOOLBOX (project self-weight; span tolerance 0.5mm)')
    if matches:
        print(f"{'ID':>6} {'Ref':<5} {'Bend%':>8} {'TB%':>7} {'dpp':>7} {'Long%':>8} {'TB%':>7} {'dpp':>7} {'Roll%':>8} {'TB%':>7} {'dpp':>7}")
        for row in matches:
            values=''.join(f" {row[k+'_pct']:>8.2f} {row[k+'_toolbox_pct']:>7.2f} {row[k+'_delta_pp']:>7.2f}" for k in ('bending','longitudinal_shear','rolling_shear'))
            print(f"{row['id']:>6} {row['reference']:<5}"+values)
    else:
        print('No individually assigned slab satisfies the comparison criteria.')
    print(f'{len(matches)} comparable-strip comparisons. Unverified supports/grain assumptions still apply.')
    print('Storage E, roof maintenance, different spans and different wind inputs are not direct comparisons.')
    print('Current batch roof pressures 0.29/0.25kPa differ from Toolbox P401 0.30kPa; P401 above is a reference test only.')
    if output_dir is not None:
        keys=['id','guid','reference','scenario','span_mm','comparison_status']
        keys += [k+suffix for k in ('bending','longitudinal_shear','rolling_shear')
                 for suffix in ('_pct','_toolbox_pct','_delta_pp')]
        with (Path(output_dir)/'toolbox_comparison.csv').open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader();writer.writerows(matches)
    return matches


def main():
    import argparse
    parser=argparse.ArgumentParser(description='CLT ULS results for all IFC slabs; conditional screening and Toolbox validation.')
    add_input_arguments(parser)
    parser.add_argument('--toolbox',action='store_true',help='Run only the original two Toolbox cases.')
    args=parser.parse_args()
    if args.toolbox:
        run_toolbox_validation();return 0
    slabs,source=obtain_slabs(ifc_path=args.ifc,main_path=args.main,input_path=args.input)
    assignments=read_assignments(args.assignments,slabs)
    result=run_all_slabs(slabs,assignments=assignments,output_dir=args.out)
    export_loads(slabs,assignments,args.out)
    print(source)
    if args.assignments is None:
        print('Load assignment: built into loads.py (no external JSON input).')
    if not assignments:
        print('WARNING: no per-GUID assignment loaded. Zone ? and floor_E envelopes are generic candidates.')
        print('Load assignments are built into loads.py; remove an empty explicit --assignments override.')
    print('CONDITIONAL ULS STRIP RESULTS - loads and supports not automatically certified')
    print(f"{'ID':>6} {'Storey':<8} {'Zone':>4} {'L [m]':>6} {'Scenario':<20} {'Bend%':>8} {'Long%':>8} {'Roll%':>8} {'Uplift N':>9}")
    for r in result['summary']:
        if r['status']=='ERROR':
            print(f"{r['id']:>6} ERROR: {r['error']}");continue
        print(f"{r['id']:>6} {r['storey']:<8} {str(r.get('structural_zone') or '?'):>4} {r['span_mm']/1000:>6.3f} {r['scenario']:<20} "
              f"{r['bending_pct']:>8.2f} {r['longitudinal_shear_pct']:>8.2f} {r['rolling_shear_pct']:>8.2f} {r['uplift_per_support_N']:>9.1f}")
    print(f"\n{len(slabs)} slabs; {len(result['scenarios'])} scenarios; {len(result['combinations'])} ULS combinations; {len(result['errors'])} errors.")
    print('Table contains candidate envelopes; see CSV/JSON for every scenario and combination.')
    print(f"Outputs: {Path(args.out).resolve()}")
    print('Bearing without support dimensions, anchorage, SLS and vibration are NOT verified.')
    print_toolbox_comparison(result,args.out)
    return 1 if result['errors'] else 0


if __name__=='__main__':
    raise SystemExit(main())
