<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Trail packs</title>
    <link rel="stylesheet" href="/catalog-assets/catalog.css">
    <script defer src="/catalog-assets/catalog.8c4e21af.js"></script>
</head>
<body>
    <main>
        <h1 id="catalog-heading"></h1>
        <p id="catalog-greeting" aria-live="polite"></p>
        <img id="catalog-hero" src="/catalog-assets/trail.jpg" width="1400" height="788"
             loading="lazy" alt="An overview of the trail collection">
        <section aria-labelledby="listing-heading">
            <h2 id="listing-heading">All packs</h2>
            <button id="sort-packs" type="button">Sort packs</button>
            <ul id="catalog-items"></ul>
        </section>
        <section aria-labelledby="materials-heading">
            <h2 id="materials-heading">Pack materials</h2>
            <img src="/catalog-assets/material-160.jpg"
                 srcset="/catalog-assets/material-160.jpg 160w, /catalog-assets/material-320.jpg 320w"
                 sizes="(max-width: 480px) 160px, 320px" width="320" height="180" loading="lazy"
                 alt="Trail pack material swatches">
            <h2>How to fit a pack</h2>
            <video controls preload="auto" width="640" height="360" aria-label="Pack fitting demonstration">
                <source src="/catalog-assets/fitting.mp4" type="video/mp4">
            </video>
        </section>
    </main>
</body>
</html>
