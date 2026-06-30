const nav = document.querySelector('.bottom-nav');
const indicator = document.querySelector('.nav-indicator');
const navItems = [...document.querySelectorAll('.nav-item')];
const panels = [...document.querySelectorAll('.screen-panel')];
const routeButtons = [...document.querySelectorAll('[data-route]')];
const sizeGrid = document.querySelector('.size-grid');
const sizeButtons = [...document.querySelectorAll('.size-grid button')];
const openFiltersButton = document.querySelector('[data-open-filters]');
const filterOverlay = document.querySelector('[data-filter-overlay]');
const closeFiltersButtons = [...document.querySelectorAll('[data-close-filters]')];
const resetFiltersButton = document.querySelector('[data-reset-filters]');
const filterOptions = [...document.querySelectorAll('.filter-option')];
const categoryButtons = [...document.querySelectorAll('.category-row button[data-category]')];
const openCheckoutButton = document.querySelector('[data-open-checkout]');
const checkoutOverlay = document.querySelector('[data-checkout-overlay]');
const closeCheckoutButtons = [...document.querySelectorAll('[data-close-checkout]')];
const deliveryButtons = [...document.querySelectorAll('[data-delivery-method]')];
const deliveryCards = [...document.querySelectorAll('[data-delivery-card]')];
const checkoutSubmitButton = document.querySelector('.checkout-submit');
const adminContactUrl = document.body?.dataset.adminContactUrl || '';
const productCards = [...document.querySelectorAll('[data-product-id]')];
const addToCartButton = document.querySelector('[data-add-to-cart]');
const productDetailImage = document.querySelector('[data-product-detail-image]');
const productDetailBrand = document.querySelector('[data-product-detail-brand]');
const productDetailName = document.querySelector('[data-product-detail-name]');
const productDetailPrice = document.querySelector('[data-product-detail-price]');
const cartItemsRoot = document.querySelector('[data-cart-items]');
const cartEmpty = document.querySelector('[data-cart-empty]');
const cartTotal = document.querySelector('[data-cart-total]');
const cartTotalBlock = document.querySelector('.cart-total-block');
const purchaseRequestButton = document.querySelector('.purchase-request');
const cartCountBadge = document.querySelector('[data-cart-count]');
const productGrid = document.querySelector('[data-product-grid]');
const catalogEmpty = document.querySelector('[data-catalog-empty]');
const catalogResetButton = document.querySelector('[data-catalog-reset]');
const searchInputs = [...document.querySelectorAll('[data-search-input]')];
const detailsToggle = document.querySelector('[data-details-toggle]');
const detailsPanel = document.querySelector('[data-details-panel]');
const productDetailsList = document.querySelector('[data-product-details-list]');
const ordersCard = document.querySelector('[data-orders-card]');
const ordersToggle = document.querySelector('[data-orders-toggle]');
const ordersPanel = document.querySelector('[data-orders-panel]');
const infoCard = document.querySelector('[data-info-card]');
const infoToggle = document.querySelector('[data-info-toggle]');
const infoPanel = document.querySelector('[data-info-panel]');
const openMenuButton = document.querySelector('[data-open-menu]');
const sideMenuOverlay = document.querySelector('[data-side-menu-overlay]');
const closeMenuButtons = [...document.querySelectorAll('[data-close-menu]')];
const sideMenuFilterButton = document.querySelector('[data-menu-open-filters]');
const sideMenuCategoryButtons = [...document.querySelectorAll('[data-side-category]')];
const sideMenuAdminButton = document.querySelector('[data-menu-admin-contact]');

const pageOrder = navItems.map((item) => item.dataset.tab);
const transitionDuration = 420;
const transitionEasing = 'cubic-bezier(.22, 1, .36, 1)';
let activeScreen = document.querySelector('.screen-panel.is-active')?.dataset.screen || 'home';
let activeNavTab = document.querySelector('.nav-item.is-active')?.dataset.tab || 'home';
let isTransitioning = false;
let transitionTimer = null;

const products = {
  mihara: {
    id: 'mihara',
    brand: 'MIHARA YASUHIRO',
    name: 'BLACK LOGO TEE',
    price: 12500,
    priceLabel: '12.500₽',
    image: './assets/product-mihara-black-logo-tee.png',
    detailImage: './assets/product-detail-mihara-black-logo-tee.png',
    defaultSize: 'M',
    categories: ['new', 'tees'],
    sizes: ['S', 'M', 'L', 'XL'],
    brandFilter: 'mihara',
    order: 2,
  },
  rhude: {
    id: 'rhude',
    brand: 'RHUDE',
    name: 'BLACK WASHED LOGO TEE',
    price: 10500,
    priceLabel: '10.500₽',
    image: './assets/product-rhude-black-washed-logo-tee.png',
    detailImage: './assets/product-rhude-black-washed-logo-tee.png',
    defaultSize: 'M',
    categories: ['new', 'tees'],
    sizes: ['M', 'L', 'XL'],
    brandFilter: 'rhude',
    order: 1,
  },
};

const categoryLabels = {
  new: 'НОВЫЕ ПОСТУПЛЕНИЯ',
  tees: 'ФУТБОЛКИ',
  hoodie: 'ХУДИ',
  zip: 'ЗИП-ХУДИ',
  shorts: 'ШОРТЫ',
  accessories: 'АКСЕССУАРЫ',
  shoes: 'ОБУВЬ',
};

let isDetailsOpen = false;
let isOrdersOpen = true;
let isInfoOpen = false;

let currentProductId = 'mihara';
const selectedSizes = { mihara: 'M', rhude: 'M' };
let cart = [];
const productCardMap = new Map(productCards.map((card) => [card.dataset.productId, card]));
const filterState = { category: 'all', size: null, brand: 'all', sort: 'newest', query: '' };

function getPanel(screen) {
  return panels.find((panel) => panel.dataset.screen === screen);
}

function getNavItem(tab) {
  return navItems.find((item) => item.dataset.tab === tab);
}

function getNavTabForScreen(screen) {
  const directNavItem = getNavItem(screen);
  if (directNavItem) return screen;

  const panel = getPanel(screen);
  return panel?.dataset.parentTab || activeNavTab;
}

function getTransitionDirection(fromScreen, toScreen, fromNavTab, toNavTab) {
  const fromIndex = pageOrder.indexOf(fromNavTab);
  const toIndex = pageOrder.indexOf(toNavTab);

  if (fromIndex !== toIndex && fromIndex !== -1 && toIndex !== -1) {
    return toIndex > fromIndex ? 1 : -1;
  }

  if (fromScreen === toNavTab && toScreen !== toNavTab) return 1;
  if (toScreen === toNavTab && fromScreen !== toNavTab) return -1;

  return 1;
}

function moveIndicator(target) {
  if (!target || !indicator || !nav) return;

  const navRect = nav.getBoundingClientRect();
  const itemRect = target.getBoundingClientRect();
  const width = 31;
  const x = itemRect.left - navRect.left + itemRect.width / 2 - width / 2;

  indicator.style.width = `${width}px`;
  indicator.style.transform = `translateX(${x}px)`;
}

function updateSizeSelector(target = document.querySelector('.size-grid button.is-selected')) {
  if (!sizeGrid || !target) return;

  const width = target.offsetWidth;
  const x = target.offsetLeft;

  if (!width) return;

  sizeGrid.style.setProperty('--size-selector-width', `${width}px`);
  sizeGrid.style.setProperty('--size-selector-x', `${x}px`);
}

function formatRub(value) {
  return `${Number(value || 0).toLocaleString('ru-RU').replace(/\s/g, '.')}₽`;
}

function normalizeSearch(value) {
  return String(value || '').toLowerCase().replace(/ё/g, 'е').trim();
}

function syncSearchInputs() {
  searchInputs.forEach((input) => {
    if (input.value !== filterState.query) input.value = filterState.query;
  });
}

function getCurrentProduct() {
  return products[currentProductId] || products.mihara;
}

function setSelectedSize(size) {
  selectedSizes[currentProductId] = size;
}

function syncSelectedSizeButtons(size) {
  sizeButtons.forEach((button) => {
    const isActive = button.textContent.trim() === size;
    button.classList.toggle('is-selected', isActive);
    button.toggleAttribute('aria-pressed', isActive);
    button.classList.remove('is-tapping');
  });

  requestAnimationFrame(() => {
    updateSizeSelector(document.querySelector('.size-grid button.is-selected'));
  });
}

function getProductCategoryLabel(product) {
  const category = product.categories.find((item) => item !== 'new');
  return categoryLabels[category] || 'КАТАЛОГ';
}

function refreshDetailsPanelHeight() {
  if (!detailsPanel || !isDetailsOpen) return;
  detailsPanel.style.maxHeight = `${detailsPanel.scrollHeight}px`;
}

function renderProductDetails(product) {
  if (!productDetailsList || !product) return;

  productDetailsList.innerHTML = `
    <p><span>БРЕНД</span><strong>${product.brand}</strong></p>
    <p><span>КАТЕГОРИЯ</span><strong>${getProductCategoryLabel(product)}</strong></p>
    <p><span>РАЗМЕРЫ</span><strong>${product.sizes.join(' / ')}</strong></p>
  `;

  requestAnimationFrame(refreshDetailsPanelHeight);
}

function setDetailsOpen(open) {
  if (!detailsToggle || !detailsPanel) return;

  isDetailsOpen = open;
  detailsToggle.classList.toggle('is-open', open);
  detailsToggle.setAttribute('aria-expanded', String(open));
  detailsPanel.classList.toggle('is-open', open);
  detailsPanel.setAttribute('aria-hidden', String(!open));

  if (open) {
    detailsPanel.style.maxHeight = `${detailsPanel.scrollHeight}px`;
  } else {
    detailsPanel.style.maxHeight = `${detailsPanel.scrollHeight}px`;
    requestAnimationFrame(() => {
      detailsPanel.style.maxHeight = '0px';
    });
  }
}

function setCurrentProduct(productId) {
  const product = products[productId] || products.mihara;
  currentProductId = product.id;

  if (productDetailImage) {
    productDetailImage.src = product.detailImage;
    productDetailImage.alt = `${product.brand} ${product.name}`;
  }

  if (productDetailBrand) productDetailBrand.textContent = product.brand;
  if (productDetailName) productDetailName.textContent = product.name;
  if (productDetailPrice) productDetailPrice.textContent = product.priceLabel;

  renderProductDetails(product);
  syncSelectedSizeButtons(selectedSizes[product.id] || product.defaultSize);
}

function updateCartCounter() {
  if (!cartCountBadge) return;

  const count = cart.length;
  cartCountBadge.textContent = String(count);
  cartCountBadge.hidden = count === 0;
  cartCountBadge.setAttribute('aria-label', `${count} товаров в корзине`);
}

function renderCart() {
  if (!cartItemsRoot || !cartEmpty || !cartTotal) return;

  cartItemsRoot.innerHTML = '';
  const hasItems = cart.length > 0;
  cartEmpty.hidden = hasItems;

  if (cartTotalBlock) cartTotalBlock.hidden = !hasItems;
  if (purchaseRequestButton) {
    purchaseRequestButton.hidden = !hasItems;
    purchaseRequestButton.disabled = !hasItems;
    purchaseRequestButton.setAttribute('aria-disabled', String(!hasItems));
  }

  cart.forEach((item) => {
    const product = products[item.productId];
    if (!product) return;

    const article = document.createElement('article');
    article.className = 'cart-item';
    article.setAttribute('aria-label', `${product.brand} ${product.name} в корзине`);
    article.innerHTML = `
      <div class="cart-item-top">
        <div class="cart-item-image">
          <img src="${product.image}" alt="${product.brand} ${product.name}" />
        </div>

        <div class="cart-item-info">
          <p class="cart-item-brand">${product.brand}</p>
          <h2>${product.name}</h2>
          <button class="cart-remove" type="button" data-remove-cart="${product.id}">УДАЛИТЬ</button>
        </div>
      </div>

      <div class="cart-item-bottom">
        <span>SIZE ${item.size}</span>
        <strong>${product.priceLabel}</strong>
      </div>
    `;

    cartItemsRoot.append(article);
  });

  const total = cart.reduce((sum, item) => sum + (products[item.productId]?.price || 0), 0);
  cartTotal.textContent = formatRub(total);
  updateCartCounter();
}

function addCurrentProductToCart() {
  const product = getCurrentProduct();
  const size = selectedSizes[product.id] || product.defaultSize;
  const existing = cart.find((item) => item.productId === product.id);

  if (existing) {
    existing.size = size;
  } else {
    cart.push({ productId: product.id, size });
  }

  renderCart();
  setActive('cart');
}

function removeFromCart(productId) {
  cart = cart.filter((item) => item.productId !== productId);
  renderCart();
}

function updateNavState(tab) {
  navItems.forEach((item) => {
    const isActive = item.dataset.tab === tab;
    item.classList.toggle('is-active', isActive);
    item.toggleAttribute('aria-current', isActive);

    if (isActive) moveIndicator(item);
  });
}

function cleanPanel(panel) {
  panel.classList.remove('is-entering', 'is-exiting');
  panel.style.transition = '';
  panel.style.transform = '';
  panel.style.opacity = '';
}

function finishTransition(fromPanel, toPanel, screen, navTab) {
  if (fromPanel && fromPanel !== toPanel) {
    fromPanel.classList.remove('is-active');
    cleanPanel(fromPanel);
  }

  if (toPanel) {
    toPanel.classList.add('is-active');
    cleanPanel(toPanel);
  }

  activeScreen = screen;
  activeNavTab = navTab;
  isTransitioning = false;
  transitionTimer = null;

  if (screen === 'profile') {
    requestAnimationFrame(refreshOrdersPanelHeight);
    requestAnimationFrame(refreshInfoPanelHeight);
  }
  if (screen === 'product') requestAnimationFrame(refreshDetailsPanelHeight);
}

function setActive(screen) {
  if (!screen || screen === activeScreen || isTransitioning) return;

  const fromPanel = getPanel(activeScreen);
  const toPanel = getPanel(screen);
  const targetNavTab = getNavTabForScreen(screen);
  const targetNavItem = getNavItem(targetNavTab);

  if (!toPanel || !targetNavItem) return;

  const direction = getTransitionDirection(activeScreen, screen, activeNavTab, targetNavTab);
  const enterX = `${direction * 26}px`;
  const exitX = `${direction * -26}px`;

  isTransitioning = true;
  window.clearTimeout(transitionTimer);

  updateNavState(targetNavTab);

  toPanel.classList.add('is-active', 'is-entering');
  toPanel.style.transition = 'none';
  toPanel.style.transform = `translateX(${enterX})`;
  toPanel.style.opacity = '0';

  if (fromPanel && fromPanel !== toPanel) {
    fromPanel.classList.add('is-exiting');
    fromPanel.style.transition = 'none';
    fromPanel.style.transform = 'translateX(0)';
    fromPanel.style.opacity = '1';
  }

  requestAnimationFrame(() => {
    updateSizeSelector();

    requestAnimationFrame(() => {
      toPanel.style.transition = `transform ${transitionDuration}ms ${transitionEasing}, opacity ${transitionDuration}ms ${transitionEasing}`;
      toPanel.style.transform = 'translateX(0)';
      toPanel.style.opacity = '1';

      if (fromPanel && fromPanel !== toPanel) {
        fromPanel.style.transition = `transform ${transitionDuration}ms ${transitionEasing}, opacity ${transitionDuration}ms ${transitionEasing}`;
        fromPanel.style.transform = `translateX(${exitX})`;
        fromPanel.style.opacity = '0';
      }
    });
  });

  transitionTimer = window.setTimeout(() => {
    finishTransition(fromPanel, toPanel, screen, targetNavTab);
  }, transitionDuration + 40);
}

function syncCategory(value) {
  filterState.category = value || 'all';

  categoryButtons.forEach((button) => {
    const isHomeCategory = button.closest('.category-row--home');
    const activeValue = isHomeCategory && filterState.category === 'all' ? 'new' : filterState.category;
    button.classList.toggle('is-active', button.dataset.category === activeValue);
  });

  filterOptions
    .filter((button) => button.dataset.filterGroup === 'category')
    .forEach((button) => {
      button.classList.toggle('is-active', button.dataset.filterValue === filterState.category);
    });
}

function syncFilterOptions() {
  filterOptions.forEach((button) => {
    const group = button.dataset.filterGroup;
    const value = button.dataset.filterValue;
    const activeValue = filterState[group];
    button.classList.toggle('is-active', activeValue === value);
  });

  syncCategory(filterState.category);
}

function getFilteredProductIds() {
  const query = normalizeSearch(filterState.query);

  let list = Object.values(products).filter((product) => {
    const matchesCategory = filterState.category === 'all' || !filterState.category || product.categories.includes(filterState.category);
    const matchesBrand = filterState.brand === 'all' || product.brandFilter === filterState.brand;
    const matchesSize = !filterState.size || product.sizes.map((size) => size.toLowerCase()).includes(filterState.size);
    const productSearchText = normalizeSearch([
      product.brand,
      product.name,
      product.priceLabel,
      getProductCategoryLabel(product),
      product.sizes.join(' '),
    ].join(' '));
    const matchesSearch = !query || productSearchText.includes(query);

    return matchesCategory && matchesBrand && matchesSize && matchesSearch;
  });

  if (filterState.sort === 'price-desc') {
    list = [...list].sort((a, b) => b.price - a.price);
  } else if (filterState.sort === 'price-asc') {
    list = [...list].sort((a, b) => a.price - b.price);
  } else {
    list = [...list].sort((a, b) => a.order - b.order);
  }

  return list.map((product) => product.id);
}

function renderCatalog() {
  if (!productGrid) return;

  syncSearchInputs();
  syncFilterOptions();
  const productIds = getFilteredProductIds();
  const hasProducts = productIds.length > 0;

  productGrid.hidden = !hasProducts;
  if (catalogEmpty) catalogEmpty.hidden = hasProducts;

  const visibleCards = productIds
    .map((productId) => productCardMap.get(productId))
    .filter(Boolean);

  productGrid.replaceChildren(...visibleCards);
}

function resetFilters() {
  filterState.category = 'all';
  filterState.size = null;
  filterState.brand = 'all';
  filterState.sort = 'newest';
  filterState.query = '';
  renderCatalog();
}

function openFilters() {
  if (!filterOverlay) return;
  closeCheckout();
  closeSideMenu();
  filterOverlay.classList.add('is-open');
  filterOverlay.setAttribute('aria-hidden', 'false');
}

function closeFilters() {
  if (!filterOverlay) return;
  filterOverlay.classList.remove('is-open');
  filterOverlay.setAttribute('aria-hidden', 'true');
}

function openCheckout() {
  if (!checkoutOverlay || cart.length === 0) return;
  closeFilters();
  closeSideMenu();
  checkoutOverlay.classList.add('is-open');
  checkoutOverlay.setAttribute('aria-hidden', 'false');
  requestAnimationFrame(refreshActiveDeliveryFormHeight);
}

function closeCheckout() {
  if (!checkoutOverlay) return;
  checkoutOverlay.classList.remove('is-open');
  checkoutOverlay.setAttribute('aria-hidden', 'true');
}

function openSideMenu() {
  if (!sideMenuOverlay) return;
  closeFilters();
  closeCheckout();
  sideMenuOverlay.classList.add('is-open');
  sideMenuOverlay.setAttribute('aria-hidden', 'false');
}

function closeSideMenu() {
  if (!sideMenuOverlay) return;
  sideMenuOverlay.classList.remove('is-open');
  sideMenuOverlay.setAttribute('aria-hidden', 'true');
}

function openFiltersFromSideMenu() {
  closeSideMenu();
  setActive('catalog');
  window.setTimeout(openFilters, transitionDuration + 70);
}

function syncDeliveryFormHeight(card, isActive) {
  const form = card.querySelector('.delivery-form');
  if (!form) return;

  if (isActive) {
    form.style.maxHeight = `${form.scrollHeight}px`;
    return;
  }

  form.style.maxHeight = `${form.scrollHeight}px`;

  requestAnimationFrame(() => {
    form.style.maxHeight = '0px';
  });
}

function refreshActiveDeliveryFormHeight() {
  const activeForm = document.querySelector('.delivery-method.is-active .delivery-form');
  if (!activeForm) return;
  activeForm.style.maxHeight = `${activeForm.scrollHeight}px`;
}

function setDeliveryMethod(method) {
  deliveryCards.forEach((card) => {
    const isActive = card.dataset.deliveryCard === method;
    card.classList.toggle('is-active', isActive);
    syncDeliveryFormHeight(card, isActive);
  });

  deliveryButtons.forEach((button) => {
    const isActive = button.dataset.deliveryMethod === method;
    button.setAttribute('aria-expanded', String(isActive));
  });
}

function getActiveDeliveryMethod() {
  return document.querySelector('.delivery-method.is-active')?.dataset.deliveryCard || 'pickup';
}

function openAdminChat() {
  if (!adminContactUrl) return;

  if (window.Telegram?.WebApp?.openTelegramLink) {
    window.Telegram.WebApp.openTelegramLink(adminContactUrl);
    return;
  }

  window.open(adminContactUrl, '_blank', 'noopener,noreferrer');
}

function submitCheckout() {
  if (getActiveDeliveryMethod() === 'pickup') {
    openAdminChat();
  }
}

function refreshOrdersPanelHeight() {
  if (!ordersPanel || !isOrdersOpen) return;
  ordersPanel.style.maxHeight = `${ordersPanel.scrollHeight}px`;
}

function setOrdersOpen(open) {
  if (!ordersCard || !ordersToggle || !ordersPanel) return;

  isOrdersOpen = open;
  ordersCard.classList.toggle('is-open', open);
  ordersToggle.setAttribute('aria-expanded', String(open));

  if (open) {
    ordersPanel.style.maxHeight = `${ordersPanel.scrollHeight}px`;
  } else {
    ordersPanel.style.maxHeight = `${ordersPanel.scrollHeight}px`;
    requestAnimationFrame(() => {
      ordersPanel.style.maxHeight = '0px';
    });
  }
}

function refreshInfoPanelHeight() {
  if (!infoPanel || !isInfoOpen) return;
  infoPanel.style.maxHeight = `${infoPanel.scrollHeight}px`;
}

function setInfoOpen(open) {
  if (!infoCard || !infoToggle || !infoPanel) return;

  isInfoOpen = open;
  infoCard.classList.toggle('is-open', open);
  infoToggle.setAttribute('aria-expanded', String(open));

  if (open) {
    infoPanel.style.maxHeight = `${infoPanel.scrollHeight}px`;
  } else {
    infoPanel.style.maxHeight = `${infoPanel.scrollHeight}px`;
    requestAnimationFrame(() => {
      infoPanel.style.maxHeight = '0px';
    });
  }
}

navItems.forEach((item) => {
  item.addEventListener('click', () => setActive(item.dataset.tab));
});

if (openMenuButton) {
  openMenuButton.addEventListener('click', openSideMenu);
}

closeMenuButtons.forEach((button) => {
  button.addEventListener('click', closeSideMenu);
});

if (sideMenuFilterButton) {
  sideMenuFilterButton.addEventListener('click', openFiltersFromSideMenu);
}

sideMenuCategoryButtons.forEach((button) => {
  button.addEventListener('click', () => {
    filterState.category = button.dataset.sideCategory || 'new';
    filterState.query = '';
    syncFilters();
    syncSearchInputs();
    renderCatalog();
    closeSideMenu();
    setActive('catalog');
  });
});

if (sideMenuAdminButton) {
  sideMenuAdminButton.addEventListener('click', () => {
    closeSideMenu();
    openAdminChat();
  });
}

routeButtons.forEach((button) => {
  button.addEventListener('click', () => {
    if (button.dataset.productId) setCurrentProduct(button.dataset.productId);
    setActive(button.dataset.route);
    if (button.hasAttribute('data-close-menu')) closeSideMenu();
  });

  button.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (button.dataset.productId) setCurrentProduct(button.dataset.productId);
      setActive(button.dataset.route);
      if (button.hasAttribute('data-close-menu')) closeSideMenu();
    }
  });
});

if (addToCartButton) {
  addToCartButton.addEventListener('click', addCurrentProductToCart);
}

if (cartItemsRoot) {
  cartItemsRoot.addEventListener('click', (event) => {
    const removeButton = event.target.closest('[data-remove-cart]');
    if (!removeButton) return;
    removeFromCart(removeButton.dataset.removeCart);
  });
}

categoryButtons.forEach((button) => {
  button.addEventListener('click', () => {
    filterState.category = button.dataset.category;
    filterState.query = '';
    renderCatalog();

    if (button.closest('.category-row--home')) {
      setActive('catalog');
    }
  });
});

searchInputs.forEach((input) => {
  input.addEventListener('input', () => {
    filterState.query = input.value;
    if (filterState.query.trim()) filterState.category = 'all';
    renderCatalog();

    if (input.dataset.searchScope === 'home' || input.dataset.searchScope === 'profile') {
      setActive('catalog');
      window.setTimeout(() => {
        document.querySelector('[data-search-scope="catalog"]')?.focus({ preventScroll: true });
      }, transitionDuration + 60);
    }
  });
});

if (openFiltersButton) {
  openFiltersButton.addEventListener('click', openFilters);
}

closeFiltersButtons.forEach((button) => {
  button.addEventListener('click', closeFilters);
});

filterOptions.forEach((button) => {
  button.addEventListener('click', () => {
    const group = button.dataset.filterGroup;
    const value = button.dataset.filterValue;

    if (group === 'size') {
      filterState.size = filterState.size === value ? null : value;
    } else if (group === 'category') {
      filterState.category = value;
    } else if (group === 'brand') {
      filterState.brand = value;
    } else if (group === 'sort') {
      filterState.sort = value;
    }

    renderCatalog();
  });
});

if (catalogResetButton) {
  catalogResetButton.addEventListener('click', resetFilters);
}

if (resetFiltersButton) {
  resetFiltersButton.addEventListener('click', resetFilters);
}

if (openCheckoutButton) {
  openCheckoutButton.addEventListener('click', openCheckout);
}

closeCheckoutButtons.forEach((button) => {
  button.addEventListener('click', closeCheckout);
});

deliveryButtons.forEach((button) => {
  button.addEventListener('click', () => setDeliveryMethod(button.dataset.deliveryMethod));
});

if (checkoutSubmitButton) {
  checkoutSubmitButton.addEventListener('click', submitCheckout);
}

if (detailsToggle) {
  detailsToggle.addEventListener('click', () => setDetailsOpen(!isDetailsOpen));
}

if (ordersToggle) {
  ordersToggle.addEventListener('click', () => setOrdersOpen(!isOrdersOpen));
}

if (infoToggle) {
  infoToggle.addEventListener('click', () => setInfoOpen(!isInfoOpen));
}

window.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    closeFilters();
    closeCheckout();
    closeSideMenu();
  }
});

sizeButtons.forEach((button) => {
  button.addEventListener('click', () => {
    setSelectedSize(button.textContent.trim());

    sizeButtons.forEach((item) => {
      const isActive = item === button;
      item.classList.toggle('is-selected', isActive);
      item.toggleAttribute('aria-pressed', isActive);
      item.classList.remove('is-tapping');
    });

    updateSizeSelector(button);

    button.classList.add('is-tapping');
    window.setTimeout(() => {
      button.classList.remove('is-tapping');
    }, 260);
  });
});

window.addEventListener('resize', () => {
  const active = document.querySelector('.nav-item.is-active');
  if (active) moveIndicator(active);
  updateSizeSelector();
  refreshActiveDeliveryFormHeight();
  refreshDetailsPanelHeight();
  refreshOrdersPanelHeight();
});

window.addEventListener('load', () => {
  const active = document.querySelector('.nav-item.is-active');
  if (active) moveIndicator(active);
  setCurrentProduct(currentProductId);
  renderCart();
  renderCatalog();
  updateSizeSelector();
  setDeliveryMethod('pickup');
  setOrdersOpen(true);
  setDetailsOpen(false);
});
