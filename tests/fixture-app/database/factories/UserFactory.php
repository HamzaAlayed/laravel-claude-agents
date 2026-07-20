<?php

namespace Database\Factories;

use App\Models\User;
use Illuminate\Database\Eloquent\Factories\Factory;
use Illuminate\Support\Str;

/**
 * @extends Factory<User>
 */
class UserFactory extends Factory
{
    protected $model = User::class;

    public function definition(): array
    {
        return [
            'name' => fake()->name(),
            'email' => fake()->unique()->safeEmail(),
            'password' => '$2y$12$5xN0O0ZTUk9C4vd1oZ0kOeBpRTUuY7DldPpn0vUu4vXcVX2fS7DPa',
            'remember_token' => Str::random(10),
        ];
    }
}
