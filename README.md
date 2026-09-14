
This contains a complete Nexus Research AI Discovery MVP with OpenAlex normalization and evals


Every Nexus Research AI module must have:

1. Unit Tests
2. Benchmark Data
3. Evaluation Script

No module moves to production
without all three.

**This is the flow:**
Research Query
        ↓
OpenAlex
        ↓
Raw JSON
        ↓
Normalization
        ↓
Source
        ↓
DiscoveryResult
        ↓
Eval
