# Findings

## 2026-07-22 — How much does the WER table format actually drift? (nb 00)
- **Tried:** parsing a 2011 report the same way as a 2026 one.
- **Result:** row length changed (19 vs 30 numbers — 9 vs 14 diseases
  tracked), trailing columns changed (1 vs 2), and long district names
  get truncated on the page ('Nuwara Eliya' -> 'Nuwara', 'Kilinochchi' ->
  'Kilinoch-'). One row (Gampaha, 2011-w52) is missing a value outright —
  genuine source data gap, not a parsing bug.
- **Decision:** parser now matches on a schema registry keyed by row
  length instead of one fixed shape, and district matching tolerates
  truncated names down to a 5-character shared prefix.
- **Still open:** only 2 eras confirmed so far (2011, 2026). Expect more
  schema variants between them — add each as found, same way as these two.
