<?php

declare(strict_types=1);

namespace LaravelGuild\BenchmarkCapture\Support;

use LaravelGuild\BenchmarkCapture\Exceptions\BenchmarkCaptureException;

final class EnvironmentPolicy
{
    public function assertAllowed(string $environment, bool $dedicatedTarget, bool $allowStaging): void
    {
        $environment = strtolower(trim($environment));

        if (in_array($environment, ['local', 'testing'], true)) {
            return;
        }

        if ($environment === 'staging' && $dedicatedTarget && $allowStaging) {
            return;
        }

        throw new BenchmarkCaptureException(
            'Capture is allowed only in local/testing, or dedicated staging with --allow-staging.'
        );
    }
}
