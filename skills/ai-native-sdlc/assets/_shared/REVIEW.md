# Code Review Guidelines (REVIEW.md)

## Multi-Pass Review Protocol
Every pull request undergoes three automated review passes before human sign-off:

### Pass 1: Bug & Logic Review
- Off-by-one errors, null/undefined safety, unhandled exceptions.
- Broken edge cases and subtle regressions.

### Pass 2: Security & Boundary Review
- Input validation and injection vulnerabilities.
- Secret leaks or PII in logs.
- Privilege boundaries and authentication checks.

### Pass 3: Spec & Policy Compliance
- Verify implementation against `02-design/output/spec.md` and `03-build/output/plan.md`.
- Ensure no out-of-scope files were touched.

## Finding Severity
- **Important**: Functional regressions, security flaws, broken contracts, or unhandled exceptions. (Blocks merge).
- **Nit**: Style, naming, or minor readability suggestions. (Max 5 reported).
