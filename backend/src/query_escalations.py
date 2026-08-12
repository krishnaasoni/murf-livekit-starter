import json
import os
import sys

# Ensure src module directory is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

import db

action = sys.argv[1] if len(sys.argv) > 1 else "list"

if action == "list":
    db.init_db()
    escalations = db.get_escalations()
    print(json.dumps(escalations))
elif action == "resolve":
    db.init_db()
    ticket_id = int(sys.argv[2])
    res = db.resolve_escalation(ticket_id)
    print(json.dumps({"success": res}))
