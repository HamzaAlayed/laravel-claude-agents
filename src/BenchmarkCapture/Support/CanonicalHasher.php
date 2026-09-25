<?php

declare(strict_types=1);

namespace LaravelGuild\BenchmarkCapture\Support;

use JsonException;
use LaravelGuild\BenchmarkCapture\Exceptions\BenchmarkCaptureException;

final class CanonicalHasher
{
    public function hash(mixed $value): string
    {
        try {
            return hash('sha256', json_encode(
                $this->normalize($value),
                JSON_THROW_ON_ERROR | JSON_PRESERVE_ZERO_FRACTION | JSON_UNESCAPED_SLASHES,
            ));
        } catch (JsonException $exception) {
            throw new BenchmarkCaptureException('A behavior fingerprint could not be encoded safely.', 0, $exception);
        }
    }

    private function normalize(mixed $value): mixed
    {
        if (is_float($value) && ! is_finite($value)) {
            throw new BenchmarkCaptureException('Non-finite numbers cannot be fingerprinted.');
        }

        if (is_array($value)) {
            if (! array_is_list($value)) {
                ksort($value, SORT_STRING);
            }

            return array_map(fn (mixed $item): mixed => $this->normalize($item), $value);
        }

        if (is_bool($value) || is_float($value) || is_int($value) || is_string($value) || $value === null) {
            return $value;
        }

        throw new BenchmarkCaptureException('Only arrays and scalar values may be fingerprinted.');
    }
}
