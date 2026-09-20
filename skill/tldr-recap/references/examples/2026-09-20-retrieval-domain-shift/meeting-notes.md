# Retrieval under temporal domain shift

- **Project:** Thesis on retrieval-augmented question answering over cybersecurity advisories
- **Participants:** Dr. Maya Cohen (advisor), Daniel Levi (student)

## Summary

Dr. Maya Cohen and Daniel Levi reviewed an experiment comparing lexical, dense, and hybrid retrieval over cybersecurity advisories. They identified leakage in the current chunk-level dataset split and agreed to rebuild the evaluation around a strict temporal boundary before drawing conclusions from the reported retrieval gains.

## Decisions

- Group documents by CVE identifier before splitting the dataset.
- Group advisories without a CVE by source URL and publication month.
- Use documents published through the end of 2024 for training and validation.
- Reserve 2025 advisories exclusively for the temporal test set.
- Exclude questions with advisory overlap from the primary evaluation and report them separately.
- Use exact FAISS `IndexFlatIP` search for the main retrieval-quality experiment.
- Move HNSW performance to a latency and deployment appendix.
- Keep the generator, prompt, decoding parameters, and five-passage context size fixed.
- Use fixed reciprocal rank fusion for the primary hybrid system.
- Use paired bootstrap confidence intervals with 10,000 samples instead of a paired t-test.
- Keep the current thesis evaluation English-only.
- Defer hard-negative mining and context-size experiments until the leakage-free baseline is established.

## Action items

- **Daniel**
  - Rebuild the dataset using advisory-level grouping and a strict 2024/2025 temporal boundary.
  - Produce an auditable manifest of excluded overlapping questions.
  - Rerun BM25, E5-base, and hybrid retrieval using exact search.
  - Report Recall@20 and nDCG@10 with paired bootstrap confidence intervals.
  - Categorize queries as identifier lookup, conceptual explanation, affected-product lookup, or mitigation.
  - Prepare ten representative retrieval failures.
  - Deliver the corrected manifest, retrieval table, and failure analysis by Friday afternoon.

- **Dr. Maya Cohen**
  - Prepare a blinded claim-level annotation sheet.
  - Independently annotate 30 generated answers after the corrected retrieval run is complete.

## Open questions

- Whether BM25 hard negatives improve dense-retriever fine-tuning.
- Whether a weighted hybrid outperforms fixed reciprocal rank fusion.
- How retrieval quality changes with different context sizes.
- Whether multilingual retrieval over Hebrew advisories should become future work.

## Important discussion

### Dataset leakage

The current chunk-level random split allows nearly identical passages from the same advisory to appear in training and evaluation. This means the existing scores do not reliably measure temporal domain shift.

### Retrieval evaluation

The current hybrid system scores highest, but much of its gain comes from exact CVE-identifier queries where BM25 is naturally strong. Results should therefore be broken down by query category rather than reported only as aggregate metrics.

### Approximate versus exact search

HNSW introduces approximation error into the scientific comparison. Exact inner-product search will isolate retrieval-model quality, while HNSW will be evaluated separately for deployment latency and recall.

### Answer quality

Token-level F1 will remain a secondary metric. The primary answer-quality analysis will examine citation precision, citation recall, and whether individual technical claims are supported by retrieved passages.

## Follow-ups

- Revisit hard-negative mining after the corrected baseline is stable.
- Consider weighted fusion and context-size experiments as ablations.
- Record Hebrew and multilingual retrieval as a possible thesis extension.
