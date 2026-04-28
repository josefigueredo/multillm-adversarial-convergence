# compatibility shim — remove in MM15 Step 7
from src.implement.document_strategy import *  # noqa: F401, F403
from src.implement.document_strategy import _extract_json, _format_human_decisions, _format_patches, _parse_patches, _parse_raw_critiques, _parse_verified_critiques  # noqa: F401
