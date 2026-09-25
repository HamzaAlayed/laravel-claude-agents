<?php

declare(strict_types=1);

namespace LaravelGuild\BenchmarkCapture\Commands;

use Illuminate\Console\Command;
use JsonException;
use LaravelGuild\BenchmarkCapture\CaptureRunner;
use LaravelGuild\BenchmarkCapture\Exceptions\BenchmarkCaptureException;
use LaravelGuild\BenchmarkCapture\Support\ScenarioLoader;
use Throwable;

final class BenchmarkCaptureCommand extends Command
{
    protected $signature = 'guild:benchmark-capture
        {--scenario= : Project-relative scenario JSON file}
        {--output= : Project-relative output below docs/delivery}
        {--allow-staging : Allow an explicitly dedicated staging target}';

    protected $description = 'Capture a repeated, read-only Laravel performance scenario';

    public function handle(ScenarioLoader $loader, CaptureRunner $runner): int
    {
        $scenarioPath = $this->option('scenario');
        $outputPath = $this->option('output');

        if (! is_string($scenarioPath) || $scenarioPath === '' || ! is_string($outputPath) || $outputPath === '') {
            $this->components->error('--scenario and --output are required.');

            return self::FAILURE;
        }

        try {
            $root = base_path();
            $definition = $loader->load($root, $scenarioPath);
            $output = $loader->outputPath($root, $outputPath);

            if (realpath($root.'/'.$scenarioPath) === realpath($output)) {
                throw new BenchmarkCaptureException('Output cannot overwrite the scenario.');
            }

            $capture = $runner->capture($definition, (bool) $this->option('allow-staging'));
            $this->writeAtomically($output, $capture);
        } catch (BenchmarkCaptureException|JsonException $exception) {
            $this->components->error($exception->getMessage());

            return self::FAILURE;
        } catch (Throwable) {
            $this->components->error('Scenario execution failed; no capture was written.');

            return self::FAILURE;
        }

        $this->components->info("Capture written to {$outputPath}");

        return self::SUCCESS;
    }

    /** @param array<string, mixed> $capture */
    private function writeAtomically(string $output, array $capture): void
    {
        $directory = dirname($output);
        if (! is_dir($directory) && ! mkdir($directory, 0755, true) && ! is_dir($directory)) {
            throw new BenchmarkCaptureException('Output directory could not be created.');
        }

        $json = json_encode($capture, JSON_THROW_ON_ERROR | JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)."\n";
        $temporary = tempnam($directory, '.benchmark-');
        if ($temporary === false) {
            throw new BenchmarkCaptureException('Temporary capture file could not be created.');
        }

        try {
            if (file_put_contents($temporary, $json, LOCK_EX) === false || ! rename($temporary, $output)) {
                throw new BenchmarkCaptureException('Capture could not be written atomically.');
            }
        } finally {
            if (is_file($temporary)) {
                unlink($temporary);
            }
        }
    }
}
