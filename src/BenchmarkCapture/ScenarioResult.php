<?php

declare(strict_types=1);

namespace LaravelGuild\BenchmarkCapture;

final readonly class ScenarioResult
{
    /**
     * @param array<array-key, mixed>|bool|float|int|string|null $response
     */
    public function __construct(
        public string $status,
        public array|bool|float|int|string|null $response,
    ) {
    }
}
