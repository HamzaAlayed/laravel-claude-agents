<?php

declare(strict_types=1);

use LaravelGuild\BenchmarkCapture\Exceptions\BenchmarkCaptureException;
use LaravelGuild\BenchmarkCapture\ScenarioDefinition;
use LaravelGuild\BenchmarkCapture\Support\CanonicalHasher;
use LaravelGuild\BenchmarkCapture\Support\EnvironmentPolicy;
use LaravelGuild\BenchmarkCapture\Support\QueryClassifier;

it('allows a narrow read only SQL grammar', function (string $query): void {
    expect((new QueryClassifier)->isReadOnly($query))->toBeTrue();
})->with([
    'select' => 'select * from orders where id = ?',
    'commented select' => "/* benchmark */\nSELECT count(*) from orders",
    'show' => 'SHOW TABLES',
    'describe' => 'DESCRIBE orders',
    'explain select' => 'EXPLAIN SELECT * FROM orders',
]);

it('rejects writes ambiguous statements and bypass attempts', function (string $query): void {
    expect((new QueryClassifier)->isReadOnly($query))->toBeFalse();
})->with([
    'insert' => 'INSERT INTO orders values (1)',
    'update' => 'UPDATE orders SET paid = 1',
    'delete' => 'DELETE FROM orders',
    'cte write' => 'WITH changed AS (DELETE FROM orders RETURNING *) SELECT * FROM changed',
    'explain analyze write' => 'EXPLAIN ANALYZE UPDATE orders SET paid = 1',
    'multiple statements' => 'SELECT 1; DELETE FROM orders',
    'outfile' => "SELECT secret INTO OUTFILE '/tmp/leak' FROM users",
    'select into table' => 'SELECT * INTO archived_orders FROM orders',
    'locking select' => 'SELECT * FROM orders FOR UPDATE',
    'shared locking select' => 'SELECT * FROM orders FOR SHARE',
    'sequence mutation' => "SELECT nextval('orders_id_seq')",
    'executable comment' => '/*!50000 INSERT INTO orders VALUES (1) */ SELECT 1',
    'pragma mutation' => 'PRAGMA user_version = 2',
    'unterminated comment' => '/* select */ /*',
]);

it('canonicalizes associative key order and rejects objects', function (): void {
    $hasher = new CanonicalHasher;

    expect($hasher->hash(['b' => 2, 'a' => 1]))
        ->toBe($hasher->hash(['a' => 1, 'b' => 2]));

    expect(fn () => $hasher->hash((object) ['secret' => true]))
        ->toThrow(BenchmarkCaptureException::class);
});

it('allows only safe execution environments', function (): void {
    $policy = new EnvironmentPolicy;

    $policy->assertAllowed('testing', false, false);
    $policy->assertAllowed('staging', true, true);

    expect(fn () => $policy->assertAllowed('production', true, true))
        ->toThrow(BenchmarkCaptureException::class);
    expect(fn () => $policy->assertAllowed('staging', false, true))
        ->toThrow(BenchmarkCaptureException::class);
});

it('requires the exact scenario schema and sample floors', function (): void {
    $scenario = validScenario();

    expect(ScenarioDefinition::fromArray($scenario)->measuredRuns)->toBe(7);

    $scenario['unexpected'] = true;
    expect(fn () => ScenarioDefinition::fromArray($scenario))
        ->toThrow(BenchmarkCaptureException::class);
});

it('keeps the capture manifest aligned with runtime floors and safety rules', function (): void {
    $manifest = json_decode(
        file_get_contents(dirname(__DIR__, 2).'/config/capture-harness.json'),
        true,
        flags: JSON_THROW_ON_ERROR,
    );

    expect($manifest['command'])->toBe('guild:benchmark-capture')
        ->and($manifest['databaseMode'])->toBe('read-only')
        ->and($manifest['minimumWarmupRuns'])->toBe(2)
        ->and($manifest['minimumMeasuredRuns'])->toBe(7)
        ->and($manifest['artifactDirectory'])->toBe('docs/delivery')
        ->and($manifest['deniedEnvironments'])->toContain('production')
        ->and($manifest['forbiddenArtifactPayloads'])->toContain('raw SQL');
});

it('declares Laravel package discovery for the capture provider', function (): void {
    $composer = json_decode(
        file_get_contents(dirname(__DIR__, 2).'/composer.json'),
        true,
        flags: JSON_THROW_ON_ERROR,
    );

    expect($composer['extra']['laravel']['providers'])->toBe([
        LaravelGuild\BenchmarkCapture\BenchmarkCaptureServiceProvider::class,
    ]);
});

/** @return array<string, mixed> */
function validScenario(string $handler = Tests\BenchmarkCapture\Fixtures\StableScenario::class): array
{
    return [
        'schemaVersion' => 1,
        'id' => 'orders-index',
        'version' => 1,
        'kind' => 'http',
        'target' => 'GET /api/orders',
        'objective' => 'query-count',
        'handler' => $handler,
        'datasetHash' => str_repeat('a', 64),
        'datasetRows' => 10000,
        'databaseMode' => 'read-only',
        'warmupRuns' => 2,
        'measuredRuns' => 7,
        'dedicatedTarget' => false,
    ];
}
