<?php

declare(strict_types=1);

namespace Tests\BenchmarkCapture\Fixtures;

use LaravelGuild\BenchmarkCapture\Contracts\BenchmarkScenario;
use LaravelGuild\BenchmarkCapture\ScenarioResult;

final class UnstableScenario implements BenchmarkScenario
{
    private int $iteration = 0;

    public function run(): ScenarioResult
    {
        $this->iteration++;

        return new ScenarioResult('command:0', ['iteration' => $this->iteration]);
    }

    public function databaseState(): array
    {
        return ['fixture' => 'stable'];
    }
}
