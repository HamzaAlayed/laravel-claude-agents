<x-mail::message>
# New post: {{ $post->title }}

{{ Str::limit($post->body, 120) }}

<x-mail::button :url="route('posts.index')">
Read it
</x-mail::button>
</x-mail::message>
