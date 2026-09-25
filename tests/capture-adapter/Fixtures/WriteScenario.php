<?php

declare(strict_types=1);

namespace Tests\BenchmarkCapture\Fixtures;

use Illuminate\Database\DatabaseManager;
use LaravelGuild\BenchmarkCapture\Contracts\BenchmarkScenario;
use LaravelGuild\BenchmarkCapture\ScenarioResult;

final class WriteScenario implements BenchmarkScenario
{
    public function __construct(private readonly DatabaseManager $database)
    {
    }

    public function run(): ScenarioResult
    {
        $this->database->statement('delete from forbidden_table');

        return new ScenarioResult('command:0', []);
    }

    public function databaseState(): array
    {
        return ['fixture' => 'stable'];
    }
}
