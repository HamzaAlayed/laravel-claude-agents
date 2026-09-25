<?php

declare(strict_types=1);

namespace LaravelGuild\BenchmarkCapture\Exceptions;

final class WriteQueryDetected extends BenchmarkCaptureException
{
    public function __construct()
    {
        parent::__construct('A non-read-only database statement was blocked before execution.');
    }
}
