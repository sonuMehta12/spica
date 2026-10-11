#!/bin/sh
# Cortex is a weekend project (CLAUDE.md § Working style, 2026-10-08).
# On a weekday, every session in this repo opens with a reminder: one line the
# person sees, and the same fact handed to Claude so it opens with the flag.
# Saturday and Sunday print nothing. CORTEX_DAY (1 = Monday … 7 = Sunday)
# fakes the day for testing.

day=${CORTEX_DAY:-$(date +%u)}
[ "$day" -ge 6 ] && exit 0

today=$(date +%A)
cat <<JSON
{
  "systemMessage": "It's ${today} — a weekday. Cortex is a weekend project; this time belongs to office work.",
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Today is ${today}, a weekday. By the user's own rule (CLAUDE.md, Working style) Cortex is worked on only at weekends. Open your first reply with one plain line saying so, and that this time belongs to office work. Then do what they asked, keep it short, and do not suggest follow-up Cortex work."
  }
}
JSON
