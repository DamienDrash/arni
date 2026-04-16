"""Legacy compatibility shim for the dedicated worker runtime.

Preferred entrypoint: ``python -m app.worker_runtime.main``.
This module remains only as an ops-safe alias while Epic 11 sunsets
legacy entrypoints behind explicit compatibility contracts.
"""

from app.worker_runtime.main import main


if __name__ == "__main__":
    main()
