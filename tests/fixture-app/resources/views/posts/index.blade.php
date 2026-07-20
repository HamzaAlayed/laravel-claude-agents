<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Posts</title>
</head>
<body>
    @if (session('status'))
        <p role="status">{{ session('status') }}</p>
    @endif

    @foreach ($posts as $post)
        <article>
            <h2>{{ $post->title }}</h2>
            <p>by {{ $post->user->name }} &middot; {{ $post->comments->count() }} comments</p>
            @if ($post->comments->isNotEmpty())
                <blockquote>{{ $post->comments->sortByDesc('created_at')->first()->body }}</blockquote>
            @endif
        </article>
    @endforeach
</body>
</html>
