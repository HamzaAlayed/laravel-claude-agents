<?php

declare(strict_types=1);

namespace LaravelGuild\BenchmarkCapture\Contracts;

use LaravelGuild\BenchmarkCapture\ScenarioResult;

interface BenchmarkScenario
{
    /** Execute one observable scenario iteration. */
    public function run(): ScenarioResult;

    /**
     * Return a normalized, non-secret summary of the database state that must
     * remain identical before and after every iteration.
     *
     * @return array<string, bool|float|int|string|null>
     */
    public function databaseState(): array;
}
