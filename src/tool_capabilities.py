# compatibility shim — remove in MM15 Step 7
from src.policy.tool_capabilities import *  # noqa: F401, F403
from src.policy.tool_capabilities import (  # noqa: F401
    SHIPPED_TOOLS,
    _TOOL_CAPABILITIES,
)
