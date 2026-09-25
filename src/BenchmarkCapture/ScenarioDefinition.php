<?php

declare(strict_types=1);

namespace LaravelGuild\BenchmarkCapture;

use LaravelGuild\BenchmarkCapture\Exceptions\BenchmarkCaptureException;

final readonly class ScenarioDefinition
{
    private const FIELDS = [
        'schemaVersion', 'id', 'version', 'kind', 'target', 'objective',
        'handler', 'datasetHash', 'datasetRows', 'databaseMode',
        'warmupRuns', 'measuredRuns', 'dedicatedTarget',
    ];

    private const KINDS = ['http', 'command', 'job', 'livewire'];

    private const OBJECTIVES = ['query-count', 'latency', 'query-and-latency'];

    public function __construct(
        public string $id,
        public int $version,
        public string $kind,
        public string $target,
        public string $objective,
        public string $handler,
        public string $datasetHash,
        public int $datasetRows,
        public string $databaseMode,
        public int $warmupRuns,
        public int $measuredRuns,
        public bool $dedicatedTarget,
    ) {
    }

    /** @param array<string, mixed> $input */
    public static function fromArray(array $input): self
    {
        $keys = array_keys($input);
        sort($keys);
        $fields = self::FIELDS;
        sort($fields);

        if ($keys !== $fields) {
            throw new BenchmarkCaptureException('Scenario fields do not match the capture schema.');
        }

        if ($input['schemaVersion'] !== 1) {
            throw new BenchmarkCaptureException('Scenario schemaVersion must be 1.');
        }

        self::string($input['id'], 'id', '/\A[a-z0-9][a-z0-9-]{0,63}\z/');
        self::integer($input['version'], 'version', 1, PHP_INT_MAX);
        self::oneOf($input['kind'], 'kind', self::KINDS);
        self::string($input['target'], 'target', '/\A[^\r\n]{1,256}\z/');
        self::oneOf($input['objective'], 'objective', self::OBJECTIVES);
        self::string(
            $input['handler'],
            'handler',
            '/\A[A-Za-z_][A-Za-z0-9_]*(?:\\\\[A-Za-z_][A-Za-z0-9_]*)*\z/',
        );
        self::string($input['datasetHash'], 'datasetHash', '/\A[0-9a-f]{64}\z/');
        self::integer($input['datasetRows'], 'datasetRows', 1, PHP_INT_MAX);

        if ($input['databaseMode'] !== 'read-only') {
            throw new BenchmarkCaptureException('databaseMode must be read-only.');
        }

        self::integer($input['warmupRuns'], 'warmupRuns', 2, 100);
        self::integer($input['measuredRuns'], 'measuredRuns', 7, 100);

        if (! is_bool($input['dedicatedTarget'])) {
            throw new BenchmarkCaptureException('dedicatedTarget must be a boolean.');
        }

        return new self(
            $input['id'],
            $input['version'],
            $input['kind'],
            $input['target'],
            $input['objective'],
            $input['handler'],
            $input['datasetHash'],
            $input['datasetRows'],
            $input['databaseMode'],
            $input['warmupRuns'],
            $input['measuredRuns'],
            $input['dedicatedTarget'],
        );
    }

    /** @return array<string, int|string> */
    public function captureMetadata(string $runtimeHash): array
    {
        return [
            'id' => $this->id,
            'version' => $this->version,
            'kind' => $this->kind,
            'target' => $this->target,
            'objective' => $this->objective,
            'datasetHash' => $this->datasetHash,
            'datasetRows' => $this->datasetRows,
            'runtimeHash' => $runtimeHash,
            'databaseMode' => $this->databaseMode,
            'warmupRuns' => $this->warmupRuns,
        ];
    }

    private static function string(mixed $value, string $field, string $pattern): void
    {
        if (! is_string($value) || preg_match($pattern, $value) !== 1) {
            throw new BenchmarkCaptureException("Scenario {$field} is invalid.");
        }
    }

    /** @param list<string> $allowed */
    private static function oneOf(mixed $value, string $field, array $allowed): void
    {
        if (! is_string($value) || ! in_array($value, $allowed, true)) {
            throw new BenchmarkCaptureException("Scenario {$field} is invalid.");
        }
    }

    private static function integer(mixed $value, string $field, int $minimum, int $maximum): void
    {
        if (! is_int($value) || $value < $minimum || $value > $maximum) {
            throw new BenchmarkCaptureException("Scenario {$field} is invalid.");
        }
    }
}
