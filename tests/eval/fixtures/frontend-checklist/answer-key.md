# Catalog audit answer key

The runner copies the six fixture inputs individually and leaves this answer key
outside the app. Each check scores one point for an identifiable fixture location,
the causal problem, and a fix that addresses it. A combined finding can earn two
points if it describes both mechanisms and both fixes. Check source lines or
recorded HTTP evidence. Count an otherwise sound finding once, regardless of how
many times it is mentioned. Track false positives on the three controls separately.

| ID | Check and scoring condition | Expected evidence |
| --- | --- | --- |
| F1 | Render first-view content server-side. Identify the empty initial heading or first-view list whose content waits on JS/API, and propose including it in the Blade response. | Blade heading and list, JS population, initial HTML |
| F2 | Remove a runtime CSS import from the critical path. Identify the serial stylesheet dependency and move it to build-time bundling or early loading. | Catalog CSS line 1 |
| F3 | Serve a smaller, responsive hero. Identify its one large JPEG and propose responsive sizes/source variants appropriate to the displayed width. | Hero markup, hero CSS, HTTP bytes |
| F4 | Load the likely LCP hero eagerly. Identify the above-the-fold hero's lazy loading and remove it or make loading eager. A source-based statement that the hero is a candidate is sufficient. | Hero markup |
| F5 | Avoid downloading the optional video at page load. Identify automatic preload and recommend metadata-only, no preload, or deferred source insertion. | Blade video |
| F6 | Avoid font-blocked text. Identify `font-display: block` and recommend `swap` or `optional`. | Catalog CSS font-face |
| F7 | Batch DOM measurements and updates. Identify the sort loop alternating a geometry read with a style write and propose grouping reads then writes or eliminating the per-row measurements. | Catalog JS sort handler |
| F8 | Limit rendered rows. Identify that all 180 items are inserted in one go and propose pagination or virtualization. | Catalog JS list rendering, items route |
| P1 | Cache fingerprinted JS for repeat visits. Identify revalidation of the hashed bundle and propose a long-lived immutable policy tied to content hashes. | Asset route, HTTP cache header |
| P2 | Keep viewer-specific output out of a shared cache. Identify the public cache policy on a header-dependent response and propose private or no-store caching, or explicitly correct the restricted fixture's shared key by viewer variant. | Viewer route, two captured variants |
| P3 | Trim response fields unused by the page. Identify `listing_history` in the response and the listing consuming only ID/name, and propose omitting history or fetching it separately when needed. | Items route, local JSON, list rendering |
| P4 | Remove avoidable fetch serialization. Identify the independent viewer and items requests running in sequence and propose launching them together or removing the critical network chain by server rendering. | Catalog JS fetches |
| P5 | Enforce a CI budget on the affected route. Identify missing `/catalog` coverage or the warning-only LCP check, and propose adding route coverage or an enforced budget for `/catalog`. | LHCI configuration |

The responsive, lazy secondary thumbnail, the explicit media dimensions, and
the deferred main script are controls. Report any claim that they lack those
properties. Optional follow-up validation is not a false positive. A measured
effect must be supported by the supplied evidence. No browser trace, user field
data, production edge timing, or actual CDN hit is part of this fixture. The PHP
development server's encoding and protocol are not production findings.
