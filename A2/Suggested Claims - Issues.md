Suggestion - Claims/Issues:

1. Existing RC Floor Slab Bending & Deflection Deficit

Exact Source: 26-01-D-STR-Anon.pdf, Pages 14–15 (Section 7.2.1, Tables 9 & 10)4.Building & Element: DTU Building 308, Level 1 floor slabs (P201, P202, P203, P204).

The Issue: Slabs P203 and P204 (250 mm flat RC slabs) fail ULS bending checks under new upper floor loads with a 240% utilization ratio ($M_{Ed} = 91.7\text{ kNm}$ vs. $M_{Rd} = 38.2\text{ kNm}$) and fail SLS deflection limits with a calculated 331 mm deflection vs. 16 mm allowable4.

Potential OpenBIM Tool: An ifcOpenShell script that parses IfcSlab entities (thickness, span, rebar data), extracts applied floor loads, and verifies ULS bending and SLS deflection compliance4.


2. Basement RC T-Beam Shear Stirrup Capacity Deficit

Exact Source: 26-09-D-STR-Anon.pdf, Page 13 (Section 4.1, Table 4.1)5.Building & Element: DTU Building 308, Basement monolithic RC T-beam B102 (span = 8.3 m)5.

The Issue: Beam B102 carries increased vertical loads from the new upper frame. While its bending utilization is acceptable at 60%, its internal stirrup shear reinforcement is insufficient, reaching 120% shear utilization ($V_{Ed} = 173\text{ kN}$)5.

Potential OpenBIM Tool: A tool that extracts RC beam cross-sections (IfcBeam), shear forces, and stirrup bar spacing (IfcReinforcingBar) to verify Eurocode 2 shear stirrup capacity5.


3. Continuous RC Beams Negative Moment & Code Minimum Reinforcement

Exact Source: 26-06-D-STR-Anon.pdf, Page 10 (Section 5.1.2)3.Building & Element: DTU Building 308, multi-span continuous concrete beams B110, B111, B11236.

The Issue: Negative hogging moments develop over intermediate supports. The existing top reinforcement at these support locations falls below modern Eurocode minimum reinforcement requirements3. Engineers relied on plastic moment redistribution to justify safety against brittle collapse without applying top CFRP strips3.

Potential OpenBIM Tool: An IFC model checker that evaluates continuous beam elements, compares top rebar area over intermediate supports against Eurocode 2 minimum reinforcement rules, and flags non-compliant sections3.


4. Basement Concrete Slab Serviceability (SLS) Deflection Deficit

Exact Source: 26-08-D-STR-Anon.pdf, Page 17 (Section 5.3, Table 4)78.Building & Element: DTU Building 308, Basement floor RC slabs P101–P111 (thicknesses 120 mm–140 mm)8.

The Issue: All assessed basement slabs satisfy ULS bending checks without modification, but 9 out of 10 basement slabs fail SLS deflection limits8. Carbon-Fiber Reinforced Polymer (CFRP) surface strips must be bonded to the tensile face solely to control deflections78.

Potential OpenBIM Tool: A script that evaluates slab deflections across an IFC model and calculates the required composite stiffness contribution from surface-bonded CFRP materials78.


5. Vibration Criteria and Deflection Constraints in Lightweight CLT Upper Floors

Exact Source: 26-09-D-STR-Anon.pdf, Appendix 3 (Pages 271–273, 304)9 & 26-08-D-STR-Anon.pdf, Page 17 (Section 5.4)8.Building & Element: DTU Building 308, new Level 2 & 3 extensions constructed with Cross-Laminated Timber (CLT) floor decks (e.g., KLH 140 mm) on Glulam beams1011.

The Issue: Lightweight timber floor extensions are governed primarily by SLS deflection limits ($L/300\text{–}L/400$) and floor vibration criteria (fundamental frequency $f_1 \ge 4.5\text{ Hz}$ per EN 1995-1-1) rather than ULS bending strength (where timber utilization is low, around 21%)10more_horiz.

Potential OpenBIM Tool: An OpenBIM script that extracts timber/CLT panel spans, material stiffness properties, and mass distributions directly from IFC to execute Eurocode 5 (EN 1995) floor vibration and SLS deflection checks1012.
