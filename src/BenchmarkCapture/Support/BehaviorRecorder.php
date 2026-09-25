<?php

declare(strict_types=1);

namespace LaravelGuild\BenchmarkCapture\Support;

use Illuminate\Database\Events\QueryExecuted;
use Illuminate\Events\Dispatcher;
use Illuminate\Queue\Events\JobQueued;
use Illuminate\Queue\Events\JobQueueing;

final class BehaviorRecorder
{
    private bool $recording = false;

    /** @var list<string> */
    private array $events = [];

    /** @var list<string> */
    private array $jobs = [];

    public function __construct(
        private readonly Dispatcher $dispatcher,
        private readonly CanonicalHasher $hasher,
    ) {
    }

    public function install(): void
    {
        $this->dispatcher->listen('*', function (string $eventName): void {
            if (! $this->recording || $this->isInfrastructureEvent($eventName)) {
                return;
            }
            $this->events[] = $eventName;
        });

        $this->dispatcher->listen([JobQueueing::class, JobQueued::class], function (object $event): void {
            if (! $this->recording) {
                return;
            }
            $job = $event->job ?? null;
            $this->jobs[] = is_object($job) ? $job::class : 'queued-job';
        });
    }

    public function start(): void
    {
        $this->events = [];
        $this->jobs = [];
        $this->recording = true;
    }

    /** @return array{eventsHash: string, jobsHash: string} */
    public function stop(): array
    {
        $this->recording = false;

        return [
            'eventsHash' => $this->hasher->hash($this->events),
            'jobsHash' => $this->hasher->hash($this->jobs),
        ];
    }

    private function isInfrastructureEvent(string $event): bool
    {
        return $event === QueryExecuted::class
            || str_starts_with($event, 'Illuminate\\Database\\Events\\')
            || str_starts_with($event, 'Illuminate\\Queue\\Events\\');
    }
}
