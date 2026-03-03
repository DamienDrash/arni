"""
ARIIA Billing V2 Module

Enterprise-grade billing, subscription management, and feature gating.
Replaces the legacy billing implementation with:
- Event-sourced billing audit trail
- Decoupled feature/limit definitions via FeatureSets
- Granular usage metering
- Idempotent webhook processing
- Redis-backed caching for feature gates
"""
