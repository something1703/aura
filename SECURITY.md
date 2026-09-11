# Security

## Principles

- never commit AWS credentials;
- use IAM roles and the standard credential chain;
- default to least privilege;
- keep AWS integration read-only during Phase 2;
- isolate destructive tests;
- redact secrets from reports and logs;
- treat architecture reports as potentially sensitive.

## Reporting issues

Do not publish credentials, tokens, or sensitive AWS identifiers in issues or screenshots.
