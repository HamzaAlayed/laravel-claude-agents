<?php

use App\Http\Controllers\PostController;
use Illuminate\Support\Facades\Route;

Route::get('/', function () {
    return view('welcome');
});

Route::get('/posts', [PostController::class, 'index'])->name('posts.index');
Route::post('/posts', [PostController::class, 'store'])->middleware('auth')->name('posts.store');
Route::put('/posts/{post}', [PostController::class, 'update'])->middleware('auth')->name('posts.update');
