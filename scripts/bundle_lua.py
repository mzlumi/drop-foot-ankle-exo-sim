#!/usr/bin/env python3
"""Write scenarios/lua/<script>_bundle.lua, the one-file scripts that SCONE runs (see dropfoot.scenarios.lua_bundle).

    python scripts/bundle_lua.py
"""

from dropfoot import ROOT
from dropfoot.scenarios import write_lua_bundles

if __name__ == "__main__":
    for path in write_lua_bundles():
        print(path.relative_to(ROOT))
