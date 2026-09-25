<?php

declare(strict_types=1);

namespace LaravelGuild\BenchmarkCapture\Support;

use JsonException;
use LaravelGuild\BenchmarkCapture\Exceptions\BenchmarkCaptureException;
use LaravelGuild\BenchmarkCapture\ScenarioDefinition;

final class ScenarioLoader
{
    public function load(string $root, string $relativePath): ScenarioDefinition
    {
        $path = $this->existingFile($root, $relativePath, 'Scenario');

        try {
            $payload = json_decode(file_get_contents($path) ?: '', true, flags: JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new BenchmarkCaptureException('Scenario JSON is invalid.', 0, $exception);
        }

        if (! is_array($payload)) {
            throw new BenchmarkCaptureException('Scenario JSON must contain an object.');
        }

        return ScenarioDefinition::fromArray($payload);
    }

    public function outputPath(string $root, string $relativePath): string
    {
        $this->relative($relativePath, 'Output');
        if (! str_ends_with($relativePath, '.json')) {
            throw new BenchmarkCaptureException('Output must be a JSON file.');
        }

        $root = realpath($root);
        if ($root === false) {
            throw new BenchmarkCaptureException('Application root cannot be resolved.');
        }

        $deliveryRoot = $root.'/docs/delivery';
        $candidate = $root.'/'.str_replace('/', DIRECTORY_SEPARATOR, $relativePath);
        $normalized = $this->normalize($candidate);
        $required = $this->normalize($deliveryRoot).DIRECTORY_SEPARATOR;

        if (! str_starts_with($normalized, $required)) {
            throw new BenchmarkCaptureException('Output must stay below docs/delivery.');
        }

        $cursor = $root;
        foreach (explode('/', dirname($relativePath)) as $segment) {
            if ($segment === '.' || $segment === '') {
                continue;
            }
            $cursor .= DIRECTORY_SEPARATOR.$segment;
            if (is_link($cursor)) {
                throw new BenchmarkCaptureException('Output path cannot traverse a symlink.');
            }
        }

        return $normalized;
    }

    private function existingFile(string $root, string $relativePath, string $label): string
    {
        $this->relative($relativePath, $label);
        $root = realpath($root);
        $path = $root === false ? false : realpath($root.'/'.$relativePath);

        if ($root === false || $path === false || is_link($root.'/'.$relativePath) || ! is_file($path)) {
            throw new BenchmarkCaptureException("{$label} must be a regular existing file.");
        }

        if (! str_starts_with($path, $root.DIRECTORY_SEPARATOR)) {
            throw new BenchmarkCaptureException("{$label} must stay inside the application.");
        }

        return $path;
    }

    private function relative(string $path, string $label): void
    {
        if ($path === '' || str_starts_with($path, '/') || preg_match('/\A[A-Za-z]:[\\\\\/]/', $path) === 1) {
            throw new BenchmarkCaptureException("{$label} path must be project-relative.");
        }

        if (in_array('..', preg_split('#[\\\\/]#', $path) ?: [], true)) {
            throw new BenchmarkCaptureException("{$label} path cannot escape the application.");
        }
    }

    private function normalize(string $path): string
    {
        $parts = [];
        foreach (explode(DIRECTORY_SEPARATOR, $path) as $part) {
            if ($part === '' || $part === '.') {
                continue;
            }
            if ($part === '..') {
                array_pop($parts);
                continue;
            }
            $parts[] = $part;
        }

        return DIRECTORY_SEPARATOR.implode(DIRECTORY_SEPARATOR, $parts);
    }
}
