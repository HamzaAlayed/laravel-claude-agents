<?php

declare(strict_types=1);

namespace LaravelGuild\BenchmarkCapture;

use Illuminate\Contracts\Container\Container;
use Illuminate\Contracts\Foundation\Application;
use LaravelGuild\BenchmarkCapture\Contracts\BenchmarkScenario;
use LaravelGuild\BenchmarkCapture\Exceptions\BenchmarkCaptureException;
use LaravelGuild\BenchmarkCapture\Support\BehaviorRecorder;
use LaravelGuild\BenchmarkCapture\Support\CanonicalHasher;
use LaravelGuild\BenchmarkCapture\Support\EnvironmentPolicy;
use LaravelGuild\BenchmarkCapture\Support\QueryMonitor;
use Throwable;

final class CaptureRunner
{
    public function __construct(
        private readonly Container $container,
        private readonly QueryMonitor $queries,
        private readonly BehaviorRecorder $behavior,
        private readonly CanonicalHasher $hasher,
        private readonly EnvironmentPolicy $environments,
    ) {
    }

    /** @return array{schemaVersion: int, scenario: array<string, int|string>, runs: list<array<string, float|int|string>>} */
    public function capture(ScenarioDefinition $definition, bool $allowStaging = false): array
    {
        $application = $this->application();
        $this->environments->assertAllowed(
            $application->environment(),
            $definition->dedicatedTarget,
            $allowStaging,
        );

        $scenario = $this->container->make($definition->handler);
        if (! $scenario instanceof BenchmarkScenario) {
            throw new BenchmarkCaptureException('Scenario handler must implement BenchmarkScenario.');
        }

        $this->queries->install();
        $this->queries->guardConfiguredConnections();
        $this->behavior->install();

        for ($index = 0; $index < $definition->warmupRuns; $index++) {
            $this->iteration($scenario, false);
        }

        $runs = [];
        for ($index = 0; $index < $definition->measuredRuns; $index++) {
            $runs[] = $this->iteration($scenario, true);
        }

        $this->assertStable($runs);

        return [
            'schemaVersion' => 1,
            'scenario' => $definition->captureMetadata($this->runtimeHash($application)),
            'runs' => $runs,
        ];
    }

    /** @return array<string, float|int|string> */
    private function iteration(BenchmarkScenario $scenario, bool $measured): array
    {
        $before = $this->hasher->hash($scenario->databaseState());
        $this->queries->startMeasurement();
        $this->behavior->start();
        $started = hrtime(true);

        try {
            $result = $scenario->run();
        } catch (Throwable $exception) {
            $this->queries->stopMeasurement();
            $this->behavior->stop();
            throw $exception;
        }

        $elapsed = (hrtime(true) - $started) / 1_000_000;
        $queryCount = $this->queries->stopMeasurement();
        $behavior = $this->behavior->stop();
        $after = $this->hasher->hash($scenario->databaseState());

        if ($before !== $after) {
            throw new BenchmarkCaptureException('Database state changed during a supposedly read-only scenario.');
        }

        if (! $measured) {
            return [];
        }

        if (
            $result->status === ''
            || strlen($result->status) > 128
            || str_contains($result->status, "\n")
            || str_contains($result->status, "\r")
        ) {
            throw new BenchmarkCaptureException('Scenario status must be a nonempty single line.');
        }

        return [
            'queryCount' => $queryCount,
            'writeQueryCount' => 0,
            'latencyMs' => round($elapsed, 6),
            'status' => $result->status,
            'responseHash' => $this->hasher->hash($result->response),
            'databaseHash' => $after,
            'eventsHash' => $behavior['eventsHash'],
            'jobsHash' => $behavior['jobsHash'],
        ];
    }

    /** @param list<array<string, float|int|string>> $runs */
    private function assertStable(array $runs): void
    {
        foreach (['status', 'responseHash', 'databaseHash', 'eventsHash', 'jobsHash'] as $field) {
            if (count(array_unique(array_column($runs, $field), SORT_REGULAR)) !== 1) {
                throw new BenchmarkCaptureException("Measured behavior is unstable: {$field} changed between runs.");
            }
        }
    }

    private function application(): Application
    {
        $application = $this->container->make(Application::class);
        if (! $application instanceof Application) {
            throw new BenchmarkCaptureException('Laravel application could not be resolved.');
        }

        return $application;
    }

    private function runtimeHash(Application $application): string
    {
        $database = $this->container->make('db');
        $driver = method_exists($database, 'getDefaultConnection')
            ? (string) config('database.default', 'unknown')
            : 'unknown';

        return $this->hasher->hash([
            'php' => PHP_MAJOR_VERSION.'.'.PHP_MINOR_VERSION,
            'laravel' => $application->version(),
            'environment' => $application->environment(),
            'databaseConnection' => $driver,
            'osFamily' => PHP_OS_FAMILY,
        ]);
    }
}
