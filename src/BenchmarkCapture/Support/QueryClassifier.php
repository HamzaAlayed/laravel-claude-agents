<?php

declare(strict_types=1);

namespace LaravelGuild\BenchmarkCapture\Support;

final class QueryClassifier
{
    public function isReadOnly(string $sql): bool
    {
        $sql = $this->stripLeadingComments($sql);
        $sql = rtrim($sql);

        if ($sql === '') {
            return false;
        }

        if (str_ends_with($sql, ';')) {
            $sql = rtrim(substr($sql, 0, -1));
        }

        if ($sql === '' || str_contains($sql, ';') || str_contains($sql, "\0")) {
            return false;
        }

        if (preg_match('/\A(?:SHOW|DESCRIBE|DESC)\b/i', $sql) === 1) {
            return true;
        }

        if (preg_match('/\AEXPLAIN\s+(?!ANALYZE\b)(?:\([^)]*\)\s*)?SELECT\b/is', $sql) === 1) {
            return $this->safeSelect($sql);
        }

        return preg_match('/\ASELECT\b/i', $sql) === 1 && $this->safeSelect($sql);
    }

    private function safeSelect(string $sql): bool
    {
        return preg_match(
            '/(?:\/\*!|\b(?:INTO|NEXTVAL|SETVAL|PG_ADVISORY_LOCK|GET_LOCK|RELEASE_LOCK)\b|\bFOR\s+(?:UPDATE|SHARE)\b|\bLOCK\s+IN\s+SHARE\s+MODE\b)/i',
            $sql,
        ) !== 1;
    }

    private function stripLeadingComments(string $sql): string
    {
        $remaining = ltrim($sql);

        while ($remaining !== '') {
            if (str_starts_with($remaining, '--') || str_starts_with($remaining, '#')) {
                $newline = strpos($remaining, "\n");
                if ($newline === false) {
                    return '';
                }
                $remaining = ltrim(substr($remaining, $newline + 1));
                continue;
            }

            if (str_starts_with($remaining, '/*')) {
                if (str_starts_with($remaining, '/*!')) {
                    return '';
                }
                $end = strpos($remaining, '*/', 2);
                if ($end === false) {
                    return '';
                }
                $remaining = ltrim(substr($remaining, $end + 2));
                continue;
            }

            break;
        }

        return $remaining;
    }
}
