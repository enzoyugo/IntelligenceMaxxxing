# TMX_IM_BOUNDARY_RUNTIME_PROOF_V2

- Separate repos/processes/storage maintained  
- TMX outbox mutation lock prevents lost observations  
- Enrollment journal is TMX-local SQLite (not IM storage)  
- IM Policy freeze intact  
- No cross-repo imports added  
