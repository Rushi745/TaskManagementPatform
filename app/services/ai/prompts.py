"""All prompt templates in one place (documented in the README)."""

RECAP_PROMPT = '''You are an assistant that turns raw meeting notes into a structured recap.
Today's date: {today}. Meeting date: {meeting_date}.
Participants (the ONLY valid owners): {participant_names}
Existing open action items (avoid duplicates): {open_item_titles}

Rules:
- Use ONLY information present in the notes. Do not invent facts, owners or dates.
- owner must exactly match one participant name, otherwise null.
- Convert relative dates ("next Friday", "EOW") to YYYY-MM-DD using the meeting date; if no date is stated, null.
- evidence must be a short exact quote from the notes (max 20 words).
- confidence: 0-1, how clearly the notes state this item and its owner.
- decisions are things that were agreed, not tasks.
- summary: 3-5 sentences, neutral tone.
- priority: high only if urgency is stated, otherwise medium (low if explicitly optional).

Notes:
"""
{raw_notes}
"""'''

BRIEF_PROMPT = '''Write a short catch-up brief for {person_name} ({role}), who {reason}.
Use only the data below. Max ~150 words total. Be specific: names, dates, numbers.
Meeting: {title} on {date}
Summary: {summary}
Decisions: {decisions}
All action items (title | owner | due | status): {items}
Items owned by {person_name}: {own_items}
Linked documents: {doc_titles}
Fill every field: headline (one sentence), what_happened (max 4 bullets), decisions_affecting_you,
your_action_items, open_questions, read_next (document titles from the linked documents only).'''

LINK_PROMPT = '''Decide which knowledge-base documents are genuinely relevant to this {kind}.
Text: """{text}"""
Candidate documents (id | title | excerpt):
{candidates}
Return one decision per candidate. Only use the given ids. reason: one sentence.'''

HANDOVER_PROMPT = '''{from_name} ({from_role}) is going on leave from {leave_from} to {leave_to}.
Write a handover brief for whoever takes over. For each item give the context the new owner needs
(why it exists, what was decided, what's left), and suggest a new owner ONLY from this list:
{available_people}
Prefer people who attended the item's meetings and have fewer open items.
Items (id | title | due | status | origin meeting | related decisions | history summary | linked docs):
{items}
Also list risks (e.g. items due during the leave window with no obvious owner).
Use the exact item ids given. suggested_owner must be a name from the list or null.'''
