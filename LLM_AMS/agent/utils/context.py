def get_conversation_context(state, max_exchanges: int = 5):
    ctx = state.get("conversation_context", [])
    if ctx:
        return ctx[-max_exchanges:]
    return []
