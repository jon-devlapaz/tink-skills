# Vendored graph library

`cytoscape.min.js` is Cytoscape.js **3.30.2**, copied unmodified from
`https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.30.2/cytoscape.min.js`.
License: MIT (the notice is in the file's own header).

The viewer inlines this file into the page it serves and into every saved snapshot, so the graph
works with no network. `ledger-view.html` still names the same CDN URL with its
`integrity="sha384-..."` hash as the pin of record; a test checks that these bytes match that hash.

To update: download the new build, replace this file, update the URL and `integrity` in
`ledger-view.html`, and run the tests.
