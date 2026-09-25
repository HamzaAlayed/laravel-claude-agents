<?php

declare(strict_types=1);

namespace LaravelGuild\BenchmarkCapture\Support;

use Illuminate\Database\Connection;
use Illuminate\Database\DatabaseManager;
use Illuminate\Database\Events\ConnectionEstablished;
use Illuminate\Database\Events\QueryExecuted;
use Illuminate\Events\Dispatcher;
use LaravelGuild\BenchmarkCapture\Exceptions\WriteQueryDetected;
use SplObjectStorage;

final class QueryMonitor
{
    private bool $active = false;

    private bool $measuring = false;

    private int $queryCount = 0;

    /** @var SplObjectStorage<Connection, null> */
    private SplObjectStorage $guarded;

    public function __construct(
        private readonly DatabaseManager $database,
        private readonly Dispatcher $events,
        private readonly QueryClassifier $classifier,
    ) {
        $this->guarded = new SplObjectStorage;
    }

    public function install(): void
    {
        foreach ($this->database->getConnections() as $connection) {
            $this->guard($connection);
        }

        $this->events->listen(ConnectionEstablished::class, function (ConnectionEstablished $event): void {
            $this->guard($event->connection);
        });

        $this->events->listen(QueryExecuted::class, function (): void {
            if ($this->active && $this->measuring) {
                $this->queryCount++;
            }
        });

        $this->active = true;
    }

    public function guardConfiguredConnections(): void
    {
        $connections = config('database.connections', []);
        if (! is_array($connections)) {
            return;
        }

        foreach (array_keys($connections) as $name) {
            if (is_string($name)) {
                $this->guard($this->database->connection($name));
            }
        }
    }

    public function startMeasurement(): void
    {
        $this->queryCount = 0;
        $this->measuring = true;
    }

    public function stopMeasurement(): int
    {
        $this->measuring = false;

        return $this->queryCount;
    }

    private function guard(Connection $connection): void
    {
        if ($this->guarded->contains($connection)) {
            return;
        }

        $connection->beforeExecuting(function (string $query): void {
            if ($this->active && ! $this->classifier->isReadOnly($query)) {
                throw new WriteQueryDetected;
            }
        });

        $this->guarded->attach($connection);
    }
}
