<?php

declare(strict_types=1);

namespace Tests\BenchmarkCapture\Fixtures;

use LaravelGuild\BenchmarkCapture\Contracts\BenchmarkScenario;
use LaravelGuild\BenchmarkCapture\ScenarioResult;

final class ChangingDatabaseStateScenario implements BenchmarkScenario
{
    private bool $changed = false;

    public function run(): ScenarioResult
    {
        $this->changed = true;

        return new ScenarioResult('job:ok', ['result' => 'same']);
    }

    public function databaseState(): array
    {
        return ['changed' => $this->changed];
    }
}
