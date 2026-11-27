<?php

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;

Route::get('/catalog', function () {
    return view('catalog');
});

Route::get('/catalog/viewer', function (Request $request) {
    $isReturning = $request->header('X-Catalog-Viewer') === 'returning';

    return response()->json([
        'greeting' => $isReturning ? 'Welcome back' : 'Welcome',
    ])->header('Cache-Control', 'public, s-maxage=300');
});

Route::get('/catalog/items', function () {
    return response()->json(array_map(static fn ($id) => [
        'id' => $id,
        'name' => "Trail pack {$id}",
        'listing_history' => array_fill(0, 12, "Catalog listing {$id} change archive."),
    ], range(1, 180)));
});

Route::get('/catalog-assets/catalog.8c4e21af.js', function () {
    return response()->file(resource_path('catalog/catalog.js'), [
        'Content-Type' => 'application/javascript',
        'Cache-Control' => 'public, max-age=0, must-revalidate',
    ]);
});
