# How do I capture a trustworthy Laravel performance benchmark?

The Laravel benchmark capture adapter runs one application-owned scenario
repeatedly, blocks non-read-only SQL before execution, measures query count and
latency, fingerprints observable behavior, and writes a capture accepted by
the [outcome benchmark comparator](outcome-benchmark.md). It supports Laravel
11, 12, and 13 and PHP 8.3 or newer.

The adapter is a Composer package in this repository. Laravel discovers its
service provider automatically and registers `php artisan
guild:benchmark-capture` for console use.

## Install the adapter

Until the package is published to Packagist, install the tagged GitHub package
as a VCS repository in the Laravel application you want to measure:

```sh
composer config repositories.laravel-guild-benchmark vcs \
  https://github.com/HamzaAlayed/laravel-claude-agents
composer require --dev hamzaalayed/laravel-guild-benchmark-capture:^9.3
```

Keep it in `require-dev`. The command rejects production even if the package is
accidentally present there.

## Define one observable scenario

Create a small application class that implements
`LaravelGuild\BenchmarkCapture\Contracts\BenchmarkScenario`. The class is
resolved through Laravel's container, so normal constructor injection works.

```php
<?php

declare(strict_types=1);

namespace App\Benchmarks;

use App\Models\Order;
use Illuminate\Contracts\Http\Kernel;
use Illuminate\Http\Request;
use LaravelGuild\BenchmarkCapture\Contracts\BenchmarkScenario;
use LaravelGuild\BenchmarkCapture\ScenarioResult;

final class OrdersIndexScenario implements BenchmarkScenario
{
    public function __construct(private readonly Kernel $kernel) {}

    public function run(): ScenarioResult
    {
        $response = $this->kernel->handle(
            Request::create('/api/orders', 'GET')
        );

        return new ScenarioResult(
            status: 'http:'.$response->getStatusCode(),
            response: [
                'status' => $response->getStatusCode(),
                'count' => count($response->getData(true)['data']),
            ],
        );
    }

    public function databaseState(): array
    {
        return [
            'orders' => Order::query()->count(),
            'latest_update' => Order::query()->max('updated_at')?->toISOString(),
        ];
    }
}
```

Return only the minimum normalized shape that proves behavior stayed the same.
Do not return response bodies, database rows, personal data, tokens, or other
secrets. `databaseState()` runs before and after every iteration; its hash must
not change. Its own read queries are guarded but excluded from the measured
query count.

The handler decides how to invoke the application:

| Kind | Typical `run()` action | Suggested status |
| --- | --- | --- |
| `http` | Send a request through Laravel's HTTP kernel | `http:200` |
| `command` | Call an Artisan command programmatically | `command:0` |
| `job` | Invoke a job synchronously with controlled dependencies | `job:ok` |
| `livewire` | Exercise the component through its test API | `livewire:ok` |

Queued jobs and dispatched events are fingerprinted by name/class and order;
their payloads are never serialized. The response and database fingerprints
remain application-owned because only the application knows which fields
define equivalent behavior.

## Declare and run the scenario

Copy [`benchmarks/orders-index.example.json`](../benchmarks/orders-index.example.json)
and replace its handler, dataset hash, target, and row count. The dataset hash
must identify the same prepared data for both captures without containing the
data itself.

```sh
php artisan guild:benchmark-capture \
  --scenario=benchmarks/orders-index.json \
  --output=docs/delivery/orders/benchmarks/baseline.json
```

After changing only the application query shape, run the same command with
`candidate.json`, then compare:

```sh
python3 scripts/outcome-benchmark.py compare \
  --root . \
  --baseline docs/delivery/orders/benchmarks/baseline.json \
  --candidate docs/delivery/orders/benchmarks/candidate.json \
  --output docs/delivery/orders/benchmarks/receipt.json
```

Use a production-representative local/test fixture where possible. Staging is
allowed only when the scenario declares `dedicatedTarget: true` and the command
receives `--allow-staging`. Production and unknown environments are denied.

## What does the safety boundary prove?

The adapter installs a `beforeExecuting` callback on configured Laravel
database connections. It permits a narrow grammar beginning with `SELECT`,
`SHOW`, `DESCRIBE`, `DESC`, or a non-`ANALYZE` `EXPLAIN SELECT`; ambiguous CTEs,
multiple statements, locking reads, export clauses, PRAGMA, DML, and DDL fail
closed. A blocked statement produces no capture.

This is defense in depth, not a SQL theorem. A database function invoked by a
read statement may have side effects, and application code can mutate external
systems that Laravel's database connection does not observe. Use a read-only
database credential, a disposable representative dataset, faked outbound
services, and an application-specific database fingerprint. Never target a
shared or production system.

The runtime fingerprint covers PHP minor version, Laravel version, environment,
configured database connection, and OS family. It intentionally excludes the
Git commit so baseline and candidate code can differ; the comparator binds the
capture files themselves into its receipt.

## Symptoms → Triage → Resolve

### The command says a non-read-only statement was blocked

**Symptoms:** the command exits unsuccessfully and no output file is written.

**Triage:** inspect the scenario path and its invoked listeners, middleware,
model touches, session driver, and queue driver. The adapter deliberately does
not print SQL or bindings.

**Resolve:** remove the write from the measured path, use safe fakes for
side-effecting collaborators, and rerun. Do not weaken the classifier. If the
feature inherently writes, this adapter cannot prove a read-only benchmark;
stop and design a dedicated disposable measurement environment.

### Behavior is unstable between measured runs

**Symptoms:** response, database, event, job, or status fingerprints differ.

**Triage:** look for timestamps, random IDs, cursor movement, changing order,
global state, asynchronous work, or a response summary that includes volatile
values.

**Resolve:** freeze time and randomness, reset application-local state without
database mutation, make ordering deterministic, and normalize only meaningful
behavior. Do not remove a field merely to hide a real behavior change.

### Baseline and candidate do not match

**Symptoms:** the comparator rejects the pair as different scenarios.

**Triage:** compare scenario version, kind, target, objective, dataset hash and
row count, runtime hash, database mode, and warmup count.

**Resolve:** recapture both sides in the same runtime against the same prepared
dataset. Preserve failed artifacts for diagnosis; delete or replace them only
through normal project review.

Escalate when a representative dataset cannot be used safely, a read-only
credential is unavailable, the scenario reaches shared infrastructure, or
external side effects cannot be faked. A manual speed impression is useful
context, but it is not a substitute for a passing repeated receipt.
