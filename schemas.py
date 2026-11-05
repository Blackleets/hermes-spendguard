"""Tool schemas — what the LLM sees. Both tools are READ-ONLY by design:
there is no tool to change a budget, because the agent must not be able
to raise its own spending cap. Budgets change only via the human-typed
/spendguard slash command."""

SPENDGUARD_STATUS = {
    "name": "spendguard_status",
    "description": (
        "SpendGuard budget status: how much this Hermes installation has "
        "spent on model API calls today and this month (USD), the budgets "
        "in force, percent used, call counts and any unpriced calls. "
        "Read-only — budgets are set by the user with /spendguard."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

SPENDGUARD_REPORT = {
    "name": "spendguard_report",
    "description": (
        "SpendGuard spend report for a period ('day' or 'month'): total "
        "USD, call count, token totals and a per-model cost breakdown "
        "from the local ledger. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "period": {
                "type": "string",
                "enum": ["day", "month"],
                "description": "Reporting period. Default 'day'.",
                "default": "day",
            }
        },
        "required": [],
    },
}
