// On the ReviewPage form, when the title is blurred and the film field is still
// empty, look the title up against Films and auto-fill on a single exact match.
document.addEventListener('DOMContentLoaded', function () {
    var title = document.querySelector('#id_title');
    function filmSpan() { return document.querySelector('[data-autocomplete-input-name="film"]'); }
    if (!title || !filmSpan()) return;

    function isEmpty(span) {
        var hidden = span.querySelector('input[type=hidden]');
        var value = hidden ? hidden.value : 'null';
        return value === '' || value === 'null';
    }

    function fill(span, match) {
        var fresh = span.cloneNode(false);  // a clone has no React root, so init does a fresh mount
        fresh.dataset.autocompleteInputValue = JSON.stringify({ pk: match.pk, title: match.title });
        span.replaceWith(fresh);
        window.initAutoCompleteWidget(fresh);
    }

    title.addEventListener('blur', function () {
        var query = title.value.trim();
        var span = filmSpan();
        if (!query || !isEmpty(span)) return;

        var token = (document.querySelector('input[name=csrfmiddlewaretoken]') || {}).value || '';
        fetch(span.dataset.autocompleteWagtailadminHome + 'autocomplete/search/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': token },
            body: new URLSearchParams({ type: span.dataset.autocompleteInputType, query: query }),
        })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                var hits = (data.items || []).filter(function (item) {
                    return item.title.toLowerCase() === query.toLowerCase();
                });
                if (hits.length === 1) fill(filmSpan(), hits[0]);
            })
            .catch(function () {});  // silent no-op; this is a convenience, not a requirement
    });
});
