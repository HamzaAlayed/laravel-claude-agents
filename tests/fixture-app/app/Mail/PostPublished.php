<?php

namespace App\Mail;

use App\Models\Post;
use Illuminate\Bus\Queueable;
use Illuminate\Mail\Mailable;
use Illuminate\Mail\Mailables\Content;
use Illuminate\Mail\Mailables\Envelope;
use Illuminate\Queue\SerializesModels;

class PostPublished extends Mailable
{
    use Queueable, SerializesModels;

    public function __construct(
        public Post $post,
    ) {}

    public function envelope(): Envelope
    {
        return new Envelope(
            subject: 'New post: '.$this->post->title,
        );
    }

    public function content(): Content
    {
        return new Content(
            markdown: 'mail.post-published',
        );
    }
}
