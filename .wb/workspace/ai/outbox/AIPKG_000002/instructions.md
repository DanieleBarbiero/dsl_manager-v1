# AI Package Handoff AIPKG_000002

You are an external AI tool. Treat this package as read-only evidence.

Rules:
- Do not update databases, registries, DSL snapshots, or project files.
- Produce only JSONL candidate records.
- Use only evidence blocks present in content.md.
- Copy source_revision_id, chunk_id, and fragment_id exactly as provided.
- Set evidence_text to text contained literally in the referenced evidence.
- Use record_type candidate_fact, candidate_relation, candidate_mapping, candidate_conflict, or candidate_question.
- Do not invent evidence.
- Prefer assertion_type explicit for declarative text.
- Use assertion_type observed for logs or runtime events.
- Use assertion_type inferred only when inference is truly required.
- Use assertion_type ambiguous for ambiguity.

Expected output path:

```text
ai/inbox/AIPKG_000002_candidates.jsonl
```
