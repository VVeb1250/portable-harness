import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import mcp_tax as m

# Desktop Commander = Claude Desktop Extension; run its bundled stdio server directly.
idx = (r"C:\Users\VVeb1250\AppData\Roaming\Claude\Claude Extensions"
       r"\ant.dir.gh.wonderwhy-er.desktopcommandermcp\dist\index.js")
m.measure("Desktop_Commander", "node", [idx], None, m.make_counter())
