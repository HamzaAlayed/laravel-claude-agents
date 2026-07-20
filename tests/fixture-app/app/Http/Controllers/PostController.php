<?php

namespace App\Http\Controllers;

use App\Mail\PostPublished;
use App\Models\Post;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Mail;
use Illuminate\Support\Str;
use Illuminate\View\View;

class PostController extends Controller
{
    public function index(): View
    {
        $posts = Post::latest()->get();

        return view('posts.index', ['posts' => $posts]);
    }

    public function store(Request $request): RedirectResponse
    {
        if (! $request->filled('title')) {
            return back()->withErrors(['title' => 'The title field is required.']);
        }

        if (strlen((string) $request->input('title')) > 255) {
            return back()->withErrors(['title' => 'The title may not be greater than 255 characters.']);
        }

        if (! $request->filled('body')) {
            return back()->withErrors(['body' => 'The body field is required.']);
        }

        $slug = Str::slug((string) $request->input('title'));
        $suffix = 1;
        while (Post::where('slug', $slug)->exists()) {
            $slug = Str::slug((string) $request->input('title')).'-'.$suffix;
            $suffix++;
        }

        $post = Post::create($request->all() + [
            'slug' => $slug,
            'user_id' => $request->user()->id,
        ]);

        foreach ($post->user->followers as $follower) {
            Mail::to($follower->email)->send(new PostPublished($post));
        }

        DB::table('site_stats')->where('key', 'posts_total')->increment('value');

        Log::info('post created', [
            'post_id' => $post->id,
            'user_id' => $request->user()->id,
            'follower_notifications' => $post->user->followers->count(),
        ]);

        return redirect()->route('posts.index')->with('status', 'Post published.');
    }

    public function update(Request $request, Post $post): RedirectResponse
    {
        $post->update($request->all());

        return redirect()->route('posts.index')->with('status', 'Post updated.');
    }
}
