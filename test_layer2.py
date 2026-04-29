import traceback
from dotenv import load_dotenv
load_dotenv()

from agents.distiller import Distiller
from core.storage import save_constraint
from pathlib import Path

try:
    d = Distiller(Path.cwd())
    print("Model:", d._model)
    c = d.distill_raw_signal(
        code_context="for item in items:\n    db.session.commit()",
        error_context="DeadlockError: concurrent write conflict on table 'orders'",
        learned_rule="Never commit inside a loop - batch all writes then commit once outside",
    )
    save_constraint(Path.cwd(), c)
    print("Stored:", c.constraint_id)
    print("Context:", c.context)
    print("Never do:", c.never_do)
    print("Instead:", c.instead)
    print("Confidence:", c.confidence)
except Exception:
    traceback.print_exc()
