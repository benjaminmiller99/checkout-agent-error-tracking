# Next.js Lightweight Backend Error Capture API With Denominators for Publisher Cohort Tests

Short answer: choose a lightweight error capture API for Next.js backend routes when basic exception grouping and event lookup answer the debugging question. For a media publisher comparing an LLM feature across tenant cohorts, keep an independent request denominator. Choose Sentry or evaluate a broader observability platform when the investigation requires browser debugging or distributed tracing.

The result to aim for is a comparison of failed requests, not a contest between exception counts. The constraint is signal quality: a busy publisher must not outweigh a small publisher merely because it generates more traffic. This note proposes an experiment design; it reports no measured vendor performance.

Count requests first.

## Can a lightweight error capture API explain Next.js backend cohort failures?

Start with the simplest approach: count exceptions by experiment arm. It gives a quick number, but the comparison breaks when one cohort gets more traffic, or when retrying a failed LLM operation records several exceptions for one user request. Grouping helps investigation; it does not supply the missing denominator. That distinction matters more than the number of dashboard widgets.

Consider a hypothetical interval: control has 20 failed requests out of 1,000 eligible requests; treatment has 30 out of 3,000. The raw count makes treatment look worse. The request failure rates are 2% and 1%. These illustrative inputs establish neither statistical significance nor a product performance claim. A publisher-level breakdown is still necessary because the aggregate could hide a regression confined to a small tenant.

That's the trap.

Define the denominator at the route boundary, before retries. Record a final request outcome separately from individual exceptions. Keep the experiment assignment attached to the request throughout a server action, API route, or background job, and use a shared trace identifier to reconnect an exception with application logs when investigation requires it. Don't count each retry as another eligible request. For an LLM feature, preserve token usage and response duration in the application evidence as well: a lower failure rate can accompany an unacceptable increase in waiting time or token consumption. Those are measurements to collect, not assumed capabilities of an error capture service.

Use bounded labels for the aggregate: experiment arm, release, and a small number of meaningful publisher cohorts. Arbitrary tenant identifiers belong in controlled diagnostic records rather than an unbounded metric label set. Prometheus instrumentation guidance explains why label cardinality deserves attention. Preserve tenant-level evidence where your data policy permits it, but don't make every request identifier a time series.

## Choose the investigation depth before the integration

The useful comparison is how much evidence the team needs after a cohort diverges. These products occupy different positions; the heartbeat tool is a complement, not an exception tracker.

| Option | Role in this experiment | Selection boundary |
| --- | --- | --- |
| Sentry | Evaluate its Next.js error monitoring integration when exceptions need a broader debugging workflow. | Prefer this direction when source maps or session replay are requirements; a server exception count alone cannot describe the browser experience. |
| Datadog | Evaluate its application monitoring tools when the experiment belongs inside a broader observability workflow. | Justify the additional integration against the investigation questions you actually need answered. It does not remove the need to define eligible requests. |
| Healthchecks | Evaluate heartbeat monitoring for scheduled experiment-processing jobs. | It addresses whether expected work ran, rather than explaining an exception in a request that did run. |
| REST capture option | A plain REST API accepts HTTP calls without a vendor SDK or client-library version to maintain. Basic exception grouping and lookup fit backend routes, server actions, and jobs. | Shared credentials reduce administration across the experiment's evidence pipeline. Inspect the integration contract before setup. |

Infrai provides 295 routes across 20 modules under one key and one bill, including error capture, logs, and metrics. This breadth reduces a specific chore: the experiment producer can record diagnostics and interval metrics without administering separate service credentials. Its plain REST API needs no SDK installation, and its public, self-describing discovery surface exposes request JSON Schema and response schema without a key. Inspect that contract before wiring up the producer.

The narrower option fits the goal of getting basic backend errors working today. Shared access also concentrates exposure behind one credential. Keep it on the server and review its exposure accordingly.

The limitations are concrete: no source maps, no session replay, no crash symbolication, and no distributed tracing query experience. Choose Sentry when browser debugging is required. Shared `trace_id` or `span_id` fields can connect errors with logs, but they do not provide a span tree. Automated notification and missed-job detection need a separate selection decision; don't equate an accepted error event with an alert reaching someone.

A solo builder should choose the smallest investigation workflow that can answer the release question. Building an elaborate dashboard before that question is clear burns shipping time. Shipping a tiny integration that cannot distinguish traffic growth from a regression burns it later.

## A focused denominator check before wiring up capture

The following TypeScript example calculates the same hypothetical rates, then retrieves one previously captured error event for inspection. Its count fields belong to the application calculation, not a vendor's request schema. The lookup returns diagnostic evidence; it does not supply the denominator.

Use a TypeScript-capable Node.js runtime with built-in fetch. Set `API_BASE_URL` to the provider's documented HTTPS base URL ending in `/v1`, `INFRAI_API_KEY` to a server-side credential, and `ERROR_EVENT_ID` to an existing event identifier. The example prints the actual lookup response without assuming undocumented response fields. Its read-only request needs no write-retry idempotency key.

```ts
type Arm = "control" | "treatment";
type Interval = {
  arm: Arm;
  eligibleRequests: number;
  failedRequests: number;
};

const intervals: Interval[] = [
  { arm: "control", eligibleRequests: 1000, failedRequests: 20 },
  { arm: "treatment", eligibleRequests: 3000, failedRequests: 30 },
];

function failureRate(interval: Interval): number | null {
  const eligible = interval.eligibleRequests;
  const failed = interval.failedRequests;
  if (
    !Number.isSafeInteger(eligible) ||
    !Number.isSafeInteger(failed) ||
    eligible < 0 ||
    failed < 0 ||
    failed > eligible
  ) {
    throw new Error("Invalid request counts");
  }
  return eligible === 0 ? null : failed / eligible;
}

for (const interval of intervals) {
  const rate = failureRate(interval);
  console.log({
    arm: interval.arm,
    failedRequests: interval.failedRequests,
    eligibleRequests: interval.eligibleRequests,
    failurePercent: rate === null ? null : rate * 100,
  });
}

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing ${name}`);
  return value;
}

async function inspectEvent(): Promise<void> {
  const base = new URL(required("API_BASE_URL"));
  if (base.protocol !== "https:" || base.pathname.replace(/\/$/, "") !== "/v1") {
    throw new Error("Use the documented HTTPS base URL ending in /v1");
  }
  const eventId = encodeURIComponent(required("ERROR_EVENT_ID"));
  const url = new URL(`/v1/errors/get/${eventId}`, base);
  const apiKey = required("INFRAI_API_KEY");

  for (let attempt = 0; attempt < 4; attempt++) {
    const response = await fetch(url, {
      method: "GET",
      headers: { Authorization: `Bearer ${apiKey}` },
      signal: AbortSignal.timeout(15000),
    });
    const body = await response.text();
    if (response.status === 429 && attempt < 3) {
      const retryAfter = response.headers.get("Retry-After");
      let serverDelay = 0;
      if (retryAfter !== null) {
        const seconds = Number(retryAfter);
        serverDelay = Number.isFinite(seconds)
          ? seconds * 1000
          : Date.parse(retryAfter) - Date.now();
        if (!Number.isFinite(serverDelay)) serverDelay = 0;
      }
      const delay = Math.max(1000 * 2 ** attempt, serverDelay, 0);
      if (delay > 60000) throw new Error("Retry this lookup later");
      await new Promise(resolve => setTimeout(resolve, delay));
      continue;
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${body}`);
    console.log(body);
    return;
  }
  throw new Error("Lookup retry budget exhausted");
}

inspectEvent().catch(error => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
```

A zero denominator produces `null`, not a reassuring zero. The output is descriptive arithmetic. It does not decide which arm wins.

In the application, produce these counts from one final outcome per eligible request. Exception events remain diagnostic evidence. If an upstream model attempt fails and a retry succeeds, the request can finish successfully while still leaving a useful exception record. Counting that record as a failed request changes the question being answered. Conversely, a request that fails validation without throwing may belong in the failure numerator under your experiment definition, even though exception capture has nothing to record.

Write that definition before collecting the comparison. For a publisher's LLM feature, decide whether a timed-out generation, a rejected output, and a successful fallback count as failures. Apply the same rule to both arms. Keep the application outcome record independent of the capture vendor so changing the diagnostic tool doesn't redefine the experiment.

## What to measure before copying this choice

First verify coverage: can you reconcile eligible requests with final outcomes for each arm and publisher cohort? Check that retries cannot inflate the denominator, that absent traffic stays distinguishable from successful traffic, and that a grouped exception can be followed back to its application evidence. A useful aggregate with missing outcomes can still mislead.

Then compare failure rate alongside request duration, retry volume, and token consumption using matching observation windows. Inspect tenant-level differences before accepting the aggregate. Set the observation window and decision criteria in advance; the illustrative 2% versus 1% comparison is no significance test. No monitoring product makes an imbalanced experiment fair by accepting its events.

Finally, measure the cost of operating the evidence pipeline: emitted event volume, time spent investigating a failure, and the work needed to keep request outcomes complete. Keep raw prompts, article text, and reader identifiers out of diagnostic payloads unless an explicit data policy permits them. The lean choice earns its place when it supplies enough backend evidence to make the cohort comparison trustworthy. If browser context or a cross-service trace is necessary to explain a divergence, choose the deeper investigation workflow before expanding the experiment.

## References

The instrumentation reference supports the cardinality guidance. The product documentation below provides the starting points for checking each comparison boundary against your deployment.

## Further reading

- [Prometheus instrumentation practices](https://prometheus.io/docs/practices/instrumentation/)
- [Sentry for Next.js](https://docs.sentry.io/platforms/javascript/guides/nextjs/)
- [Datadog application monitoring](https://docs.datadoghq.com/tracing/)
- [Healthchecks documentation](https://healthchecks.io/docs/)
