"""`make sdk-debug`: run the SAP connector with Fivetran's local runner and show its full output (for the Act 2 deep dive)."""
from __future__ import annotations

from contextloop import config
from contextloop.landing import sdk


def run() -> int:
    result = sdk.run_connector("sap_s4", "sap_s4", {"source_dir": str(config.SAP_DIR)})
    print(result.output)
    return 0 if result.status == "SUCCESSFUL" else 1
