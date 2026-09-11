# Logical Architecture

```text
                   +-----------------------+
                   |       User / CLI      |
                   +-----------+-----------+
                               |
                               v
                   +-----------------------+
                   | Requirement Model      |
                   +-----------+-----------+
                               |
                               v
                   +-----------------------+
                   | Architecture Catalog   |
                   +-----------+-----------+
                               |
                    +----------+----------+
                    |                     |
                    v                     v
             Failure Analysis       Cost Analysis
                    |                     |
                    +----------+----------+
                               |
                               v
                   +-----------------------+
                   | Rule + Score Engine   |
                   +-----------+-----------+
                               |
                               v
                   +-----------------------+
                   | Decision + ADR Engine |
                   +-----------------------+
```

Phase 2 extends the graph with AWS observed-state and Terraform desired-state inputs.
