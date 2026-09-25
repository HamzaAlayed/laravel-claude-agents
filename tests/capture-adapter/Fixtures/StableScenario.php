<?php

declare(strict_types=1);

namespace Tests\BenchmarkCapture\Fixtures;

use Illuminate\Database\DatabaseManager;
use Illuminate\Events\Dispatcher;
use Illuminate\Queue\Events\JobQueueing;
use LaravelGuild\BenchmarkCapture\Contracts\BenchmarkScenario;
use LaravelGuild\BenchmarkCapture\ScenarioResult;

final class StableScenario implements BenchmarkScenario
{
    private int $iteration = 0;

    public function __construct(
        private readonly DatabaseManager $database,
        private readonly Dispatcher $events,
    ) {
    }

    public function run(): ScenarioResult
    {
        $this->iteration++;
        $value = $this->database->selectOne('select 1 as value');
        $this->events->dispatch('benchmark.order-viewed', [
            'sensitive-payload' => 'must-not-appear-'.$this->iteration,
        ]);
        $this->events->dispatch(new JobQueueing(
            'sync',
            'benchmark',
            new FixtureJob,
            'secret-job-payload-'.$this->iteration,
            null,
        ));

        return new ScenarioResult('http:200', ['value' => (int) $value->value]);
    }

    public function databaseState(): array
    {
        return ['fixture' => 'stable'];
    }
}

final class FixtureJob
{
}
