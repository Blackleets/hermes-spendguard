"""Hermes SpendGuard plugin — registration.

Wires the read-only spend tools, the accounting + enforcement hooks and
the human-only /spendguard command into Hermes, using only the public
plugin surface (register(ctx)).
"""

import logging
import sys
from pathlib import Path

try:  # normal path: Hermes loads this directory as a package
    from . import commands, hooks, schemas, tools
except ImportError:  # standalone import (e.g. tests)
    sys.path.insert(0, str(Path(__file__).parent))
    import commands  # type: ignore
    import hooks  # type: ignore
    import schemas  # type: ignore
    import tools  # type: ignore

logger = logging.getLogger(__name__)


def register(ctx):
    ctx.register_tool(name="spendguard_status", toolset="hermes-spendguard",
                      schema=schemas.SPENDGUARD_STATUS, handler=tools.spendguard_status)
    ctx.register_tool(name="spendguard_report", toolset="hermes-spendguard",
                      schema=schemas.SPENDGUARD_REPORT, handler=tools.spendguard_report)

    ctx.register_hook("post_api_request", hooks.post_api_request)
    ctx.register_hook("post_auxiliary_call", hooks.post_auxiliary_call)
    ctx.register_hook("pre_llm_call", hooks.pre_llm_call)
    ctx.register_hook("pre_tool_call", hooks.pre_tool_call)

    ctx.register_command("spendguard", commands.spendguard_command,
                         description="SpendGuard: budget status, reports and (human-only) budget settings")

    skills_dir = Path(__file__).parent / "skills"
    if skills_dir.exists():
        for child in sorted(skills_dir.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.exists():
                ctx.register_skill(child.name, skill_md)

    logger.info("hermes-spendguard registered: spendguard_status, spendguard_report, "
                "4 hooks, /spendguard")
