# Meeting-note guidelines

Write concise English notes grounded only in the transcript and any context supplied by the user. Do not add recommendations, follow-ups, or details that nobody said. Read [the example notes](examples/2026-09-20-retrieval-domain-shift/meeting-notes.md) and match their structure and tone; the transcript beside them shows the source.

Start with a `#` title that names the meeting topic, followed by a short header list:

- Project: the project or topic, from project context when available.
- Participants: the speakers, with roles when known from the transcript or project context. Do not list people who did not speak; describe them where they are mentioned.

Omit a header line you cannot fill. If something limits trust in the notes, such as speaker labels that were inferred or looked unreliable, or a garbled transcript, add a one-line blockquote source note under the header. Omit the note otherwise.

Then use these sections, in this order, when they contain meaningful information:

- Summary: two or three sentences on why the meeting happened (the questions or goals brought to it) and what was concluded.
- Decisions: what the participants agreed or settled, with the rationale when it was discussed. One person's advice or assessment is not a decision unless the others accepted it as the plan; put it in Important discussion, attributed to the speaker.
- Action items: grouped by owner, with nested bullets.
- Open questions: points raised and left unresolved.
- Important discussion: one short `###` subsection per topic. Capture the concern behind a question, context relayed from people who were not present, and directions that were ruled out.
- Follow-ups: later or deferred items that were explicitly stated. Omit if none.

Say each point once. Do not repeat a decision as an action item and again as a follow-up.

For action items, include the owner and timing only when stated or reliably established by speaker mapping. Assign an action to whoever took it on or was told to do it. Check the direction of a request: if A asks B and B hands it back, A owns it. Match the strength of the wording to what was said: use "consider" or "where feasible" for suggestions and hedged commitments, and do not turn examples of how much work exists into assignments.

Preserve uncertainty instead of guessing, including when the transcript is garbled about who or what is meant. Omit greetings, small talk, repetition, and tangents unless they materially affected an outcome.

When the user supplies a focus instruction, prioritize it while retaining important decisions and action items. For non-English meetings, translate the notes into natural English without translating or rewriting the raw transcript. Quote at most a few short original-language phrases, each with an English translation, and only when the exact wording materially matters. Avoid em dashes.
