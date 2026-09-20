# Meeting transcript

## retrieval-domain-shift-research-sync.mp4

Language: en

[00:00:04] Dr. Maya Cohen
Let's focus today on the retrieval results and whether the evaluation actually supports the domain-shift claim. Can you summarize the current experiment?

[00:00:16] Daniel Levi
I built a corpus from approximately twelve thousand cybersecurity advisories published between 2018 and 2025. The evaluation set has 420 questions derived from advisories published in 2025. I compared BM25, E5-base, and a hybrid retriever that combines their rankings using reciprocal rank fusion.

[00:00:38] Dr. Maya Cohen
How did you construct the split? I'm concerned that chunks from the same advisory may appear in both training and evaluation.

[00:00:47] Daniel Levi
The current split is at the chunk level. I randomly selected 15 percent of all chunks for evaluation and then filtered those associated with older questions.

[00:01:02] Dr. Maya Cohen
That introduces leakage. If two chunks come from the same CVE advisory, the retriever can see nearly identical language during training. We need to group by advisory identifier before splitting.

[00:01:18] Daniel Levi
Agreed. I can group by CVE identifier. Advisories without a CVE can be grouped by source URL and publication month.

[00:01:30] Dr. Maya Cohen
Good. For the temporal experiment, training documents should stop at the end of 2024. The 2025 advisories and their associated questions should only appear in the test partition. Otherwise, we are measuring random holdout performance rather than temporal domain shift.

[00:01:49] Daniel Levi
That will reduce the number of test questions. Around 90 of the 420 questions refer to advisories that were already partially represented in late 2024.

[00:02:03] Dr. Maya Cohen
Remove those from the primary evaluation. You can report them separately as a near-duplicate condition, but they should not contribute to the main result.

[00:02:17] Daniel Levi
With the current split, BM25 gets 0.71 Recall@20, E5 gets 0.78, and the hybrid reaches 0.83. At nDCG@10, the scores are 0.54, 0.61, and 0.66 respectively.

[00:02:35] Dr. Maya Cohen
Those numbers will probably decrease after fixing the split. What similarity index are you using for E5?

[00:02:44] Daniel Levi
FAISS with an HNSW index. Embeddings are normalized, and I use inner-product similarity. The index uses 32 neighbors and an `efSearch` value of 64.

[00:03:03] Dr. Maya Cohen
For the scientific comparison, use an exact `IndexFlatIP` index first. Approximate nearest-neighbor search introduces another variable. HNSW belongs in the latency and deployment analysis, not in the main retrieval-quality experiment.

[00:03:22] Daniel Levi
Understood. I'll report exact-search quality in the main table and compare HNSW latency and recall in an appendix.

[00:03:34] Dr. Maya Cohen
How are you evaluating the generated answers?

[00:03:38] Daniel Levi
The generator is a fixed seven-billion-parameter instruction model. I currently measure token-level F1 against reference answers and use an LLM judge for faithfulness.

[00:03:54] Dr. Maya Cohen
Token F1 is weak for this task because two correct security explanations can use very different wording. Keep it as a secondary metric. We need citation precision and citation recall, plus a small human evaluation of whether each technical claim is supported by a retrieved passage.

[00:04:15] Daniel Levi
I can sample 60 answers across the three retrieval systems and annotate every factual claim as supported, unsupported, or contradicted.

[00:04:28] Dr. Maya Cohen
Sixty is reasonable for an initial pass. Blind the system identity during annotation. I'll independently annotate 30 of them so we can calculate inter-annotator agreement.

[00:04:42] Daniel Levi
Should we use Cohen's kappa?

[00:04:45] Dr. Maya Cohen
Yes, but also report raw agreement because kappa can behave strangely when almost every claim is supported. Define the annotation unit carefully. One sentence may contain several independently verifiable claims.

[00:05:04] Daniel Levi
For retrieval significance, I planned to run a paired t-test over per-query nDCG.

[00:05:11] Dr. Maya Cohen
Use paired bootstrap confidence intervals instead. The per-query metric distribution is unlikely to be normal, especially when many queries have zero relevant results. Ten thousand bootstrap samples should be sufficient.

[00:05:29] Daniel Levi
There is another issue. Most hybrid gains come from queries containing exact CVE identifiers. BM25 retrieves those almost perfectly. E5 performs better on conceptual questions such as mitigation strategies.

[00:05:45] Dr. Maya Cohen
That distinction is important. Create an error taxonomy with at least identifier lookup, conceptual explanation, affected-product lookup, and mitigation. Report results by category rather than only as one aggregate number.

[00:06:05] Daniel Levi
Should the hybrid use fixed reciprocal rank fusion, or should I tune the lexical and dense weights?

[00:06:13] Dr. Maya Cohen
Use fixed reciprocal rank fusion as the primary hybrid because it avoids tuning on a small validation set. You can include a weighted version as an ablation if time permits.

[00:06:28] Daniel Levi
For dense-retriever fine-tuning, I'm currently using random in-batch negatives. I considered adding hard negatives retrieved by BM25.

[00:06:38] Dr. Maya Cohen
Do not add that to the main experiment yet. First establish the leakage-free baseline. Hard-negative mining changes the training method and could obscure whether improvements come from the hybrid architecture or better supervision.

[00:06:57] Daniel Levi
So the immediate sequence is to rebuild the split, rerun exact retrieval, categorize queries, and then repeat answer generation with the frozen generator.

[00:07:07] Dr. Maya Cohen
Correct. Freeze the generator prompt and decoding parameters as well. Save them in the experiment configuration so we can reproduce the results.

[00:07:21] Daniel Levi
I've already fixed temperature at zero, but the prompt currently includes the top five passages. Should we test different context sizes?

[00:07:30] Dr. Maya Cohen
Keep five for the primary comparison. Context size can be a later ablation. Right now, changing it would make it harder to attribute answer-quality differences to retrieval.

[00:07:45] Daniel Levi
What should I prioritize for Friday?

[00:07:48] Dr. Maya Cohen
By Friday, produce the corrected dataset manifest, the main retrieval table with bootstrap intervals, and ten representative failure cases. The generated-answer evaluation can wait until the retrieval results are stable.

[00:08:06] Daniel Levi
I'll also include counts showing how many questions were removed because of advisory overlap.

[00:08:12] Dr. Maya Cohen
Yes. That needs to be explicit. Keep the removed questions in a separate manifest so the exclusion is auditable.

[00:08:25] Daniel Levi
One final question: should we include Hebrew security advisories? I found about 600, but E5-base seems noticeably weaker on them.

[00:08:37] Dr. Maya Cohen
Not in the current thesis experiment. Multilingual retrieval is a valuable extension, but it creates a separate research question. Record it as future work and keep the present evaluation English-only.

[00:08:52] Daniel Levi
Okay. I'll send the revised retrieval results and failure analysis by Friday afternoon.

[00:08:59] Dr. Maya Cohen
Good. I'll prepare the annotation sheet and independently label 30 answers once the new retrieval run is complete.
