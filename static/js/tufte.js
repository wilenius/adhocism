// Tufte-style sidenotes and margin notes
// Transforms Hugo footnotes and [note: ...] syntax into margin elements
(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        transformFootnotes();
        transformMarginNotes();
    });

    function transformFootnotes() {
        var content = document.querySelector(".post-content");
        if (!content) return;

        // Find all footnote references (Hugo renders them as <sup><a href="#fn:N">)
        var fnRefs = content.querySelectorAll("a[href^='#fn:']");

        fnRefs.forEach(function (ref) {
            var href = ref.getAttribute("href");
            var fnId = href.replace("#fn:", "");
            var sup = ref.closest("sup");
            if (!sup) return;

            // Find the corresponding footnote content
            var fnLi = document.getElementById("fn:" + fnId);
            if (!fnLi) return;

            // Get footnote text (strip the backref link)
            var fnContent = fnLi.cloneNode(true);
            var backref = fnContent.querySelector("a.footnote-backref");
            if (backref) backref.remove();

            var uniqueId = "sn-" + fnId;

            // Create the sidenote number label
            var label = document.createElement("label");
            label.setAttribute("for", uniqueId);
            label.className = "margin-toggle sidenote-number";

            // Create hidden checkbox for mobile toggle
            var input = document.createElement("input");
            input.type = "checkbox";
            input.id = uniqueId;
            input.className = "margin-toggle";

            // Create sidenote span
            var sidenote = document.createElement("span");
            sidenote.className = "sidenote";
            sidenote.innerHTML = fnContent.innerHTML;

            // Replace the <sup> with the sidenote elements
            sup.parentNode.insertBefore(label, sup);
            label.after(input);
            input.after(sidenote);
            sup.remove();
        });

        // Remove the original footnotes section
        var fnSection = content.querySelector("section.footnotes");
        if (fnSection) fnSection.remove();

        // Also try the <hr> + footnotes pattern Hugo sometimes uses
        var fnDiv = content.querySelector("div.footnotes");
        if (fnDiv) fnDiv.remove();
    }

    // Find [note: ...] in HTML string using bracket counting.
    // Returns array of {start, end, content} where content is the inner HTML.
    function findMarginNotesInHtml(html) {
        var results = [];
        var i = 0;
        while (i < html.length) {
            var marker = html.indexOf("[note:", i);
            if (marker === -1) break;

            // Count brackets to find the matching close, but skip
            // brackets inside HTML tags (e.g. <a href="...">) so they
            // don't throw off the depth count.
            var depth = 1;
            var j = marker + 6;
            while (j < html.length && depth > 0) {
                if (html[j] === "<") {
                    // Skip past the HTML tag entirely
                    var tagEnd = html.indexOf(">", j);
                    if (tagEnd !== -1) {
                        j = tagEnd + 1;
                        continue;
                    }
                }
                if (html[j] === "[") depth++;
                else if (html[j] === "]") depth--;
                j++;
            }

            if (depth === 0) {
                var noteContent = html.substring(marker + 6, j - 1).trim();
                results.push({ start: marker, end: j, content: noteContent });
                i = j;
            } else {
                i = marker + 6;
            }
        }
        return results;
    }

    function transformMarginNotes() {
        var content = document.querySelector(".post-content");
        if (!content) return;

        // Process margin notes in block-level elements (p, li) that
        // may contain a mix of text nodes and inline elements like <a>.
        var blocks = content.querySelectorAll("p, li");
        var noteCounter = 0;

        blocks.forEach(function (block) {
            var html = block.innerHTML;
            if (html.indexOf("[note:") === -1) return;

            var notes = findMarginNotesInHtml(html);
            if (notes.length === 0) return;

            var parts = [];
            var lastIndex = 0;

            notes.forEach(function (note) {
                if (note.start > lastIndex) {
                    parts.push(html.substring(lastIndex, note.start));
                }

                noteCounter++;
                var uniqueId = "mn-" + noteCounter;

                parts.push(
                    '<label for="' +
                        uniqueId +
                        '" class="margin-toggle">&#8853;</label>'
                );
                parts.push(
                    '<input type="checkbox" id="' +
                        uniqueId +
                        '" class="margin-toggle"/>'
                );
                parts.push(
                    '<span class="marginnote">' + note.content + "</span>"
                );

                lastIndex = note.end;
            });

            if (lastIndex < html.length) {
                parts.push(html.substring(lastIndex));
            }

            block.innerHTML = parts.join("");
        });
    }
})();
