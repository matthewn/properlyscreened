// On the BlogPost form, show the icon for the selected category next to the
// dropdown. Icons are registered in the admin sprite as 'icon-blog_<value>'.
document.addEventListener('DOMContentLoaded', function () {
    var select = document.querySelector('#id_category');
    if (!select) return;

    // build via SVG namespace so <use> resolves against the admin icon sprite
    var preview = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    preview.setAttribute('class', 'icon blog-category-icon-preview');
    preview.setAttribute('aria-hidden', 'true');
    preview.style.width = '2rem';
    preview.style.height = '2rem';
    preview.style.marginLeft = '0.5rem';
    preview.style.verticalAlign = 'middle';
    var use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    preview.appendChild(use);
    select.insertAdjacentElement('afterend', preview);

    function update() {
        if (select.value) {
            use.setAttribute('href', '#icon-blog_' + select.value);
            preview.style.display = '';
        } else {
            preview.style.display = 'none';
        }
    }

    select.addEventListener('change', update);
    update();
});
