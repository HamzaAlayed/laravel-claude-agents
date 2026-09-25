<?php

declare(strict_types=1);

use Illuminate\Support\Facades\Artisan;
use Tests\BenchmarkCapture\Fixtures\ChangingDatabaseStateScenario;
use Tests\BenchmarkCapture\Fixtures\StableScenario;
use Tests\BenchmarkCapture\Fixtures\UnstableScenario;
use Tests\BenchmarkCapture\Fixtures\WriteScenario;

it('registers the artisan capture command', function (): void {
    expect(Artisan::all())->toHaveKey('guild:benchmark-capture');
});

it('writes a comparator compatible capture with stable fingerprints', function (): void {
    [$scenario, $output] = capturePaths('stable');
    writeScenario($scenario, StableScenario::class);

    $this->artisan('guild:benchmark-capture', [
        '--scenario' => relativeToBase($scenario),
        '--output' => relativeToBase($output),
    ])->assertSuccessful();

    $capture = json_decode(file_get_contents($output), true, flags: JSON_THROW_ON_ERROR);
    $serialized = file_get_contents($output);
    $emptyHash = hash('sha256', '[]');
    expect($capture)->toHaveKeys(['schemaVersion', 'scenario', 'runs'])
        ->and($capture['runs'])->toHaveCount(7)
        ->and($capture['runs'][0]['queryCount'])->toBe(1)
        ->and($capture['runs'][0]['writeQueryCount'])->toBe(0)
        ->and(array_unique(array_column($capture['runs'], 'responseHash')))->toHaveCount(1)
        ->and(array_keys($capture['scenario']))->toBe([
            'id', 'version', 'kind', 'target', 'objective', 'datasetHash',
            'datasetRows', 'runtimeHash', 'databaseMode', 'warmupRuns',
        ])
        ->and($capture['runs'][0]['eventsHash'])->not->toBe($emptyHash)
        ->and($capture['runs'][0]['jobsHash'])->not->toBe($emptyHash)
        ->and($serialized)->not->toContain('sensitive-payload')
        ->and($serialized)->not->toContain('secret-job-payload')
        ->and($serialized)->not->toContain('select 1');
});

it('blocks a write before execution and leaves no output', function (): void {
    [$scenario, $output] = capturePaths('write');
    writeScenario($scenario, WriteScenario::class);

    $this->artisan('guild:benchmark-capture', [
        '--scenario' => relativeToBase($scenario),
        '--output' => relativeToBase($output),
    ])->assertFailed();

    expect($output)->not->toBeFile();
});

it('rejects path escape before creating output', function (): void {
    [$scenario] = capturePaths('escape');
    writeScenario($scenario, StableScenario::class);

    $this->artisan('guild:benchmark-capture', [
        '--scenario' => relativeToBase($scenario),
        '--output' => '../outside.json',
    ])->assertFailed();

    expect(dirname(base_path()).'/outside.json')->not->toBeFile();
});

it('rejects changed database state before writing output', function (): void {
    [$scenario, $output] = capturePaths('database-state');
    writeScenario($scenario, ChangingDatabaseStateScenario::class);

    $this->artisan('guild:benchmark-capture', [
        '--scenario' => relativeToBase($scenario),
        '--output' => relativeToBase($output),
    ])->assertFailed();

    expect($output)->not->toBeFile();
});

it('rejects unstable measured behavior before writing output', function (): void {
    [$scenario, $output] = capturePaths('unstable');
    writeScenario($scenario, UnstableScenario::class);

    $this->artisan('guild:benchmark-capture', [
        '--scenario' => relativeToBase($scenario),
        '--output' => relativeToBase($output),
    ])->assertFailed();

    expect($output)->not->toBeFile();
});

/** @return array{string, string} */
function capturePaths(string $name): array
{
    $scenario = base_path("benchmarks/{$name}.json");
    $output = base_path("docs/delivery/capture-tests/{$name}.json");
    @mkdir(dirname($scenario), 0755, true);
    @unlink($output);

    return [$scenario, $output];
}

function writeScenario(string $path, string $handler): void
{
    file_put_contents($path, json_encode(validScenario($handler), JSON_THROW_ON_ERROR));
}

function relativeToBase(string $path): string
{
    return ltrim(substr($path, strlen(base_path())), DIRECTORY_SEPARATOR);
}
