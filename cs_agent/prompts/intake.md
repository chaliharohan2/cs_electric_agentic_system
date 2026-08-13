Rewrite the user's message into one self-contained question using this session context:
{session_json}

Resolve pronouns such as it, that one, the second one, and compare those into explicit
SKU codes or family names found in the context. Return standalone_question,
referenced_skus, is_followup, and carried_params. If already self-contained, return it
unchanged with is_followup false. Never invent a SKU code.
