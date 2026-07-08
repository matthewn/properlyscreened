import PhotoSwipeLightbox from './vendor/photoswipe-lightbox.esm.js';

// fullscreen toolbar icons (enter / exit), styled like PhotoSwipe's own icons
const fsIcon = (d) => `<svg class="pswp__icn" viewBox="0 0 32 32" width="32" height="32" aria-hidden="true"><path transform="translate(4 4)" d="${d}"/></svg>`;
const FS_ENTER = fsIcon('M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z');
const FS_EXIT = fsIcon('M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z');

// parse '#&gid=1&pid=2' into {gid: 1, pid: 2}; missing/invalid parts are NaN
const parseHash = () => {
    const params = {};
    for (const pair of window.location.hash.replace(/^#&?/, '').split('&')) {
        const [key, val] = pair.split('=');
        params[key] = parseInt(val, 10);
    }
    return params;
};

// Register one lightbox per gallery.
// unpoly runs this on page load and after each unpoly navigation, and calls
// the returned destructor when the element goes away.
up.compiler('.pswp-gallery', (element) => {
    const gid = [...document.querySelectorAll('.pswp-gallery')].indexOf(element) + 1;

    const lightbox = new PhotoSwipeLightbox({
        gallery: element,
        children: 'a.slide-thumb',
        showHideAnimationType: 'fade',
        bgOpacity: 0.9,
        pswpModule: () => import('./vendor/photoswipe.esm.js'),
    });

    // Reflect the open slide in the URL hash so it can be shared, and clear it
    // on close. replaceState keeps this out of the browser history.
    lightbox.on('change', () => {
        const pid = lightbox.pswp.currIndex + 1;
        history.replaceState(null, '', `#&gid=${gid}&pid=${pid}`);
    });
    lightbox.on('close', () => {
        history.replaceState(null, '', window.location.pathname + window.location.search);
    });

    // Our thumbnails are square crops, so PhotoSwipe's low-res placeholder (the
    // thumbnail stretched to the full image's aspect ratio) looks distorted.
    // Skip it and just fade the full image in.
    lightbox.addFilter('useContentPlaceholder', () => false);

    lightbox.on('uiRegister', () => {
        // fullscreen toggle button (PhotoSwipe has no built-in one)
        lightbox.pswp.ui.registerElement({
            name: 'fullscreen',
            title: 'Toggle fullscreen',
            ariaLabel: 'Toggle fullscreen',
            order: 9,
            isButton: true,
            html: FS_ENTER,
            onInit: (el, pswp) => {
                const sync = () => { el.innerHTML = document.fullscreenElement ? FS_EXIT : FS_ENTER; };
                document.addEventListener('fullscreenchange', sync);
                pswp.on('destroy', () => {
                    document.removeEventListener('fullscreenchange', sync);
                    if (document.fullscreenElement) document.exitFullscreen();
                });
            },
            onClick: (e, el, pswp) => {
                if (document.fullscreenElement) {
                    document.exitFullscreen();
                } else {
                    pswp.element.requestFullscreen();
                }
            },
        });

        // show the (optional) per-slide caption inside the viewer
        lightbox.pswp.ui.registerElement({
            name: 'caption',
            appendTo: 'root',
            onInit: (el, pswp) => {
                el.className = 'pswp__custom-caption';
                pswp.on('change', () => {
                    const slide = pswp.currSlide.data.element;
                    const caption = slide && slide.querySelector('.pswp-caption-content');
                    el.innerHTML = caption ? caption.innerHTML : '';
                });
            },
        });
    });

    lightbox.init();

    // if the page was opened with a hash pointing at this gallery, open it
    const { gid: hashGid, pid: hashPid } = parseHash();
    if (hashGid === gid && hashPid > 0) {
        lightbox.loadAndOpen(hashPid - 1);
    }

    return () => lightbox.destroy();
});
