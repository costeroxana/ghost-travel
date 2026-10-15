# Agent workflow comparison

Measured on 2026-10-15 using the configured gpt-4o-mini model. Same example: London to Paris, two days, EUR 500, English, no specified departure date. Each mode was run once, without itinerary-cache reuse.

| Workflow | Seconds | Total tokens | Days | Activities | Budget assessment |
| --- | ---: | ---: | ---: | ---: | --- |
| crew | 22.83 | 6,887 | 2 | 6 | unknown |
| single | 8.88 | 3,731 | 2 | 6 | over_budget |

Both runs passed structured-output and day-count validation. Calendar dates were intentionally unspecified. The normal workflow includes flight research, local research and coordination; the baseline is one coordinator with delegation disabled.

The single-agent example was faster and used fewer tokens. This is one sample, not evidence of equivalent recommendation quality. Different estimated budgets also show why model-generated costs should remain explicitly uncertain. Keep the three-agent production workflow until a larger set of destinations, budgets and trip lengths has been reviewed for factual accuracy, geographic coherence, budget completeness and practical usefulness. No architecture switch was made. Token counts are not currency costs.

Reproduce explicitly with `python compare_agents.py --live`; this makes model calls using your API account. Inspect normal app runs with `python agent_metrics.py`.
