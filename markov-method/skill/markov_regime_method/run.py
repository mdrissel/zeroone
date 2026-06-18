"""Backward-compatibility shim. Canonical entry point: regime_performance_analytics.run."""
from regime_performance_analytics.run import main
import sys

if __name__ == "__main__":
    sys.exit(main())
