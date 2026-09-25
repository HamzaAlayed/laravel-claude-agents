<?php

declare(strict_types=1);

namespace LaravelGuild\BenchmarkCapture;

use Illuminate\Support\ServiceProvider;
use LaravelGuild\BenchmarkCapture\Commands\BenchmarkCaptureCommand;
use LaravelGuild\BenchmarkCapture\Support\BehaviorRecorder;
use LaravelGuild\BenchmarkCapture\Support\CanonicalHasher;
use LaravelGuild\BenchmarkCapture\Support\EnvironmentPolicy;
use LaravelGuild\BenchmarkCapture\Support\QueryClassifier;
use LaravelGuild\BenchmarkCapture\Support\QueryMonitor;
use LaravelGuild\BenchmarkCapture\Support\ScenarioLoader;

final class BenchmarkCaptureServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        foreach ([
            CanonicalHasher::class,
            EnvironmentPolicy::class,
            QueryClassifier::class,
            ScenarioLoader::class,
            QueryMonitor::class,
            BehaviorRecorder::class,
            CaptureRunner::class,
        ] as $service) {
            $this->app->singleton($service);
        }
    }

    public function boot(): void
    {
        if ($this->app->runningInConsole()) {
            $this->commands([BenchmarkCaptureCommand::class]);
        }
    }
}
