async function loadCatalog() {
    const viewerResponse = await fetch('/catalog/viewer', {
        headers: { 'X-Catalog-Viewer': sessionStorage.getItem('catalog-viewer') || 'new' },
    });
    const viewer = await viewerResponse.json();
    document.querySelector('#catalog-greeting').textContent = viewer.greeting;

    const itemsResponse = await fetch('/catalog/items');
    const items = await itemsResponse.json();

    document.querySelector('#catalog-heading').textContent = 'Find your next trail pack';
    const list = document.querySelector('#catalog-items');
    list.replaceChildren(...items.map(({ id, name }) => {
        const item = document.createElement('li');
        item.dataset.id = id;
        item.textContent = name;
        return item;
    }));
}

document.querySelector('#sort-packs').addEventListener('click', () => {
    const list = document.querySelector('#catalog-items');
    const items = [...list.children].reverse();
    list.replaceChildren(...items);
    for (const item of items) {
        const height = item.getBoundingClientRect().height;
        item.style.minHeight = `${height + 1}px`;
    }
});

loadCatalog();
