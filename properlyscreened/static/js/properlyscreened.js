// when any unpoly link is followed...
up.on('up:link:follow', function(event) {
    // ping goatcounter
    window.goatcounter.count({
        path: event.target.attributes.href.value,
        title: '',
    });
});
