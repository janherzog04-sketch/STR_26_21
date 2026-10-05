A2a: About our group 
We are confident in coding in Python:
1 - Disagree

Focus Are: Structures (Analysts)


A2b: Identify claim
Report 26-09-D-STR
Building 308

Fact to check:

"In terms of the structural analysis of CLT - slabs, we want to check the fact that 
SLS proofs are more decisive than ULS proofs."

"Lightweight timber floor extensions are governed primarily by SLS deflection limits 
and floor vibration criteria rather than ULS bending strength."

Exact Source: 26-09-D-STR-Anon.pdf, 
Appendix 3 (Pages 271–273, 304)9 & 26-08-D-STR-Anon.pdf, Page 17 (Section 5.4)


A2c: Use case
This fact/claim would be checked by our tool:
"An OpenBIM script that extracts timber/CLT panel spans, material stiffness properties, 
and mass distributions directly from IFC to execute ULS and SLS checks."

This would be checked during the designing phase.

- IFC Modell (Geometry, Material, properties (manufacturer's type)) 
- Standards (Eurocode)

BIM purpose: Generate 
-> includes sizing of facility elements in the design phase 

A2d: Scope the use case (-> can be seen in the folder "IMG" in Github) 

A2e: Tool idea
Describtion of the tool: 
"At first the script / tool imports the IFC Model of the building. 
Then it extracts the information about the element IfcSlab. 
It takes the system information as well as the properties of the referred slab. 
With this given information as well as external information from the standards, the ULS and SLS checks are executed. 
In the end the overall utility ratios and thicknesses are summarized in a table / storage. 
Finally the initial fact can be checked."

Business / societal values: 
The client can benefit from the overview of needed thicknesses. 
The adaption of different thicknesses (e.g. for specific stories) can lead to a optimization ot the shape.
Optimization of the shape can lead to a save of time, cost and ressources. 
Technical verification of the slab in terms of structural analysis. 


A2f: Information requirements
Span (Object Information -> Occurance Quantities -> "Length")
Thickness (Geometry and materials -> Object materials -> "Total Thickness")
Panel layers (Geometry and materials -> Object materials -> "Material Layers") 
Material (Geometry and materials -> "Materials"; more specified through Name of the element -> "KLH" (manufacturer))
Loads (Structural Analysis -> "Show Loads")
Floor -> (Object Information -> Object -> "Spatial Container")
Mechanical properties (E-modulus, compressive strength,...) -> not in the IFC Model -> information needed from the specific ETA
