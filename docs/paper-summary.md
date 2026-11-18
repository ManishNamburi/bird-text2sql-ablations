# The paper in brief

**Shkapenyuk, Srivastava, Johnson, Ghane (AT&T CDO), *Automatic Metadata Extraction for Text-to-SQL*, arXiv:2505.19988, 2025.** This is my own summary; read [the paper](https://arxiv.org/abs/2505.19988) for the authors' words. Its PDF isn't included in this repo.

## The argument

The authors' experience with large industrial databases is that writing SQL is the easy part. The hard part is knowing what the data in each field actually means. Benchmarks like BIRD supply that knowledge as hand-written column descriptions, and per-question hints. Real databases rarely have either, and subject-matter experts are expensive and often don't know every corner of their own data. So the paper asks: can the metadata a text-to-SQL system needs be *extracted automatically*?

It studies three sources:

1. **Database profiling:** for each column, compute standard statistics, such as
   - NULL counts and distinct counts;
   - value shapes (length, character classes, common prefixes);
   - frequent values;
   - MinHash sketches, which estimate how much two columns' values overlap.

   An LLM then turns each column's profile, read alongside the table schema, into a short or long English description. The descriptions turn out to be surprisingly informative. One discovered that a field held JSON.
2. **Query-log analysis:** parse past SQL queries to recover join paths, complex join predicates and recurring business formulas. On BIRD's queries this found a substantial share of join paths that the documentation doesn't mention.
3. **SQL-to-text:** have an LLM write the question for an existing query, to make few-shot examples cheaply. The paper finds the generated questions about as good as human-written ones.

## The pipeline (paper §3–4)

- **Fused metadata:** BIRD's expert descriptions plus the LLM's profiling summaries.
- **Schema linking by writing SQL.** LLMs pick relevant columns poorly when asked directly, but they write SQL well. So the pipeline:
  1. generates draft SQL under several schema views (focused or full schema, short or long descriptions);
  2. collects the columns those drafts use;
  3. checks each string literal against a MinHash LSH index of database values, adding the columns that actually contain it and revising the draft;
  4. takes the union of all of that as the linked schema.

  Recall matters more than precision here.
- **Final generation** on the linked schema, with 8 few-shot examples retrieved by similarity of *masked* questions (names replaced by placeholders).
- **Three candidates**, made different by changing the seed and shuffling the schema's column order.
- **SQL sanity checks** with up to three LLM correction retries:
  - an ascending sort or MIN on a column that can be NULL;
  - min/max via a nested subquery instead of ORDER BY … LIMIT;
  - concatenating fields into one output string.
- **A majority vote** over the candidates' result sets.

## Results the paper reports (GPT-4o, BIRD dev)

| | No hints | With hints |
|---|---|---|
| No metadata | 49.8 | — |
| BIRD descriptions | 59.6 | 72.0 |
| Profiling summaries | 61.2 | 72.6 |
| Fused | 63.2 | 73.0 |
| Schema linking (Table 2) | 63.2 | 73.0 |
| Perfect linking (Table 2) | 69.0 | 77.4 |

(Table 2 gives full schema as 61.2 / 71.2, which differs from Table 1's fused row.)

Profiling-generated metadata beats the expert descriptions, and fusing both is best. The submission, which used profiling only since BIRD's test set has no query logs, reached #1 on the BIRD leaderboard several times between September 2024 and May 2025, with and without hints. The paper reports no separate ablation for few-shot, voting or the SQL checks.

## What this project tests from it

| Paper claim | Here (qwen3.5:9b, 150 questions) |
|---|---|
| Profiling summaries ≥ expert descriptions | Reproduces: 34.0 vs 32.7, a tie (n.s.) |
| Fused metadata is best | Same direction (34.7) but not significant; costs 4× C1's tokens |
| Linking helps a little; perfect linking a lot | Reproduces: +4.7 (n.s.); oracle +14.0 over linking (p < 0.001) |
| Few-shot, voting, SQL checks | Not isolated in the paper. Here: 0, +0.7, +1.3 pp, none significant |
| Profiling's value lies in literal formats (§2) | Reproduces: masking the example values in the summaries costs −10.7 pp with hints (Holm p = 0.012), and short summaries, which drop about half of them, cost −4.5 pp without hints on the 468-question test split (Holm p = 0.025) |

The details are in [results.md](results.md). The implementation choices, and where they deviate from the paper, are in [decisions.md](decisions.md) (D10–D20).
