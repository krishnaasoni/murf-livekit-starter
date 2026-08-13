import json
import os
import sys

# Ensure src module directory is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

import db

action = sys.argv[1] if len(sys.argv) > 1 else "list"

db.init_db()

if action == "list":
    escalations = db.get_escalations()
    print(json.dumps(escalations))
elif action == "resolve":
    ticket_identifier = sys.argv[2] if len(sys.argv) > 2 else ""
    res = db.resolve_escalation(ticket_identifier)
    print(json.dumps({"success": res}))
elif action == "analytics":
    analytics = db.get_call_analytics_summary()
    print(json.dumps(analytics))
else:
    print(json.dumps({"error": f"Unknown action: {action}"}))

