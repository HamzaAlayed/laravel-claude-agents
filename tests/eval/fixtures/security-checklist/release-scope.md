# Newsroom production release candidate

The staged release serves internal editors over a browser session and publishes
public articles. A post belongs to one editor. Editors may edit their own posts,
and only administrators may edit every editor's posts. Uploaded editorial
attachments can contain private records. The React admin runs on a different
first-party origin from the Laravel app, with credentialed browser requests.
The same site also hosts separately managed editorial previews. A preview
origin is outside the editor application's trust boundary.
Horizon, Passport, and Telescope are outside this release.

Laravel's source and local runtime capture come from the disposable fixture.
The edge, identity, infrastructure, backup, and CI exports model the proposed
deployment and are synthetic. Treat them as supplied release records, with no
live AWS or production system behind them. The asset response receipt has the
complete headers observed for the fixture's editor JavaScript file on an
isolated local static server. CDN delivery requires its own verification.
No raw credentials are included.

The PostgreSQL database has a 30-minute RPO and a two-hour RTO. The operations
policy requires restore evidence and an acknowledged security alert drill
before initial traffic. Auxiliary host hardening and response header gaps
should be reported and triaged according to the supplied scope and exposure.
