<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Donations table.
     *
     * Query patterns served:
     * - Filter/report by status (admin dashboards, reconciliation) -> index on `status`.
     * - Lookup donor's donation history -> FK on `user_id` (nullable; guest donations have none).
     * - Webhook reconciliation by gateway transaction id -> unique index on `payment_reference`.
     *
     * Taught conventions applied (docs/team/conventions.md):
     * - Primary key is a ULID, not auto-increment — "New tables use ULID primary keys".
     * - Monetary amount stored as `amount_cents` (unsigned integer, no decimals) — "Money is
     *   integer cents". Deviates from the requested `amount` column name to satisfy this rule.
     *
     * - `amount_cents` is `unsignedBigInteger`, not `unsignedInteger`: an unsigned int caps at
     *   ~$42.9M (4,294,967,295 cents), which a single large donation could exceed with no ceiling
     *   validation in StoreDonationRequest (`min:100`, no `max`) — bigint headroom avoids a silent
     *   overflow on MySQL/Postgres. PHP's native `int` cast on 64-bit platforms holds this range,
     *   so the model cast stays `'integer'`.
     *
     * Constraints:
     * - `user_id` nullable + `nullOnDelete()`: donor may be a guest; if the user account is later
     *   deleted, the donation record (financial/audit history) is kept with the FK nulled rather
     *   than cascade-deleted.
     * - `payment_reference` nullable + unique: gateway transaction id. Nullable because not every
     *   donation (e.g. manual/pending entries) has one yet; unique when present is supported by
     *   both MySQL and Postgres (multiple NULLs allowed).
     * - `user_id` FK column: on MySQL this is auto-indexed by the FK constraint. If this app moves
     *   to Postgres, add `$table->index('user_id')` explicitly — Postgres does not auto-index FKs.
     *
     * Rollback: `down()` drops the table. No data-loss concern — this table has not shipped to
     * any shared environment yet.
     */
    public function up(): void
    {
        Schema::create('donations', function (Blueprint $table) {
            $table->ulid('id')->primary();
            $table->foreignId('user_id')->nullable()->constrained()->nullOnDelete();
            $table->string('donor_name')->nullable();
            $table->string('donor_email')->nullable();
            $table->unsignedBigInteger('amount_cents');
            $table->char('currency', 3)->default('USD');
            $table->text('message')->nullable();
            $table->boolean('anonymous')->default(false);
            $table->string('status')->default('pending');
            $table->string('payment_reference')->nullable()->unique();
            $table->timestamps();

            $table->index('status');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('donations');
    }
};
