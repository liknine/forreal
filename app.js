const nav = document.querySelector('.bottom-nav');
const indicator = document.querySelector('.nav-indicator');
const navItems = [...document.querySelectorAll('.nav-item')];
const panels = [...document.querySelectorAll('.screen-panel')];
const routeButtons = [...document.querySelectorAll('[data-route]')];
const sizeGrid = document.querySelector('.size-grid');
let sizeButtons = [...document.querySelectorAll('.size-grid button')];
const openFiltersButton = document.querySelector('[data-open-filters]');
const filterOverlay = document.querySelector('[data-filter-overlay]');
const closeFiltersButtons = [...document.querySelectorAll('[data-close-filters]')];
const resetFiltersButton = document.querySelector('[data-reset-filters]');
let filterOptions = [...document.querySelectorAll('.filter-option')];
const categoryButtons = [...document.querySelectorAll('.category-row button[data-category]')];
const openCheckoutButton = document.querySelector('[data-open-checkout]');
const checkoutOverlay = document.querySelector('[data-checkout-overlay]');
const closeCheckoutButtons = [...document.querySelectorAll('[data-close-checkout]')];
const deliveryButtons = [...document.querySelectorAll('[data-delivery-method]')];
const deliveryCards = [...document.querySelectorAll('[data-delivery-card]')];
const checkoutSubmitButton = document.querySelector('.checkout-submit');
const adminContactUrl = document.body?.dataset.adminContactUrl || '';
let productCards = [...document.querySelectorAll('[data-product-id]')];
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
const profileAvatarWrap = document.querySelector('[data-profile-avatar-wrap]');
const profileAvatarImage = document.querySelector('[data-profile-avatar]');
const profileAvatarPlaceholder = document.querySelector('[data-profile-avatar-placeholder]');
const profileUsername = document.querySelector('[data-profile-username]');
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

let products = {};
const PRODUCTS_URL = './data/products.json';
const ADMIN_USERNAME = 'woodyqqqq';
const API_BASE = String(document.body?.dataset.apiBase || window.FORREAL_API_BASE || '').replace(/\/$/, '');
const API_BASE_URL = document.body?.dataset.apiBase || '';
const ORDERS_PUBLIC_URL = document.body?.dataset.ordersPublicUrl || './data/orders_public.json';
const LOCAL_ORDERS_STORAGE_KEY = 'forreal_orders_v1';
let localOrdersMemory = [];

const categoryLabels = {
  new: 'НОВЫЕ ПОСТУПЛЕНИЯ',
  tees: 'ФУТБОЛКИ',
  hoodie: 'ХУДИ',
  hoodies: 'ХУДИ',
  zip: 'ЗИП-ХУДИ',
  zip_hoodies: 'ЗИП-ХУДИ',
  shorts: 'ШОРТЫ',
  accessories: 'АКСЕССУАРЫ',
  shoes: 'ОБУВЬ',
};

let isDetailsOpen = false;
let isOrdersOpen = true;
let isInfoOpen = false;

let currentProductId = null;
const selectedSizes = {};
let cart = loadCart();
let productCardMap = new Map();
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


function loadCart() {
  try {
    const raw = window.localStorage?.getItem('forreal_cart_v1');
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    return [];
  }
}

function saveCart() {
  try {
    window.localStorage?.setItem('forreal_cart_v1', JSON.stringify(cart));
  } catch (error) {
    // localStorage can be blocked in some Telegram contexts; cart still works in memory.
  }
}

function normalizeCategory(value) {
  const normalized = normalizeSearch(value).replace(/\s+/g, ' ');
  const map = {
    'футболки': 'tees',
    'худи': 'hoodie',
    'зип-худи': 'zip',
    'зип худи': 'zip',
    'шорты': 'shorts',
    'аксессуары': 'accessories',
    'обувь': 'shoes',
    'tees': 'tees',
    'tee': 'tees',
    'hoodie': 'hoodie',
    'hoodies': 'hoodie',
    'zip': 'zip',
    'zip_hoodies': 'zip',
    'shorts': 'shorts',
    'accessories': 'accessories',
    'shoes': 'shoes',
  };
  return map[normalized] || value || 'catalog';
}

function resolveAssetUrl(path) {
  const value = String(path || '').trim();
  if (!value) return './assets/product-mihara-black-logo-tee.png';
  if (/^(https?:|data:|blob:|\/\/)/i.test(value)) return value;
  if (value.startsWith('./') || value.startsWith('../')) return value;
  return `./${value.replace(/^\/+/, '')}`;
}

function normalizeProduct(raw, index = 0) {
  if (!raw || typeof raw !== 'object') return null;
  if (raw.isActive === false) return null;

  const id = String(raw.id || `product-${index + 1}`).trim();
  const brand = String(raw.brand || '').trim();
  const name = String(raw.name || '').trim();
  if (!id || !name) return null;

  const imageList = Array.isArray(raw.images) ? raw.images.filter(Boolean) : [];
  const primaryImage = raw.image || raw.detailImage || imageList[0] || '';
  const detailImage = raw.detailImage || imageList[0] || raw.image || primaryImage;
  const stock = raw.sizeStock && typeof raw.sizeStock === 'object' ? raw.sizeStock : {};
  const sizes = Array.isArray(raw.sizes)
    ? raw.sizes.map((size) => String(size).trim()).filter(Boolean)
    : Object.keys(stock);
  const categoryKey = normalizeCategory(raw.category);
  const createdTime = Date.parse(raw.createdAt || '') || 0;
  const hasStock = sizes.some((size) => Number(stock?.[size] ?? 0) > 0);
  if (!hasStock) return null;

  const originalPrice = Number(raw.price || 0);
  const rawDiscountPrice = Number(raw.discountPrice || raw.salePrice || 0);
  const hasDiscount = rawDiscountPrice > 0 && originalPrice > 0 && rawDiscountPrice < originalPrice;
  const effectivePrice = hasDiscount ? rawDiscountPrice : originalPrice;

  return {
    id,
    brand,
    name,
    price: effectivePrice,
    originalPrice,
    discountPrice: hasDiscount ? rawDiscountPrice : null,
    hasDiscount,
    priceLabel: formatRub(effectivePrice),
    oldPriceLabel: hasDiscount ? formatRub(originalPrice) : '',
    image: resolveAssetUrl(primaryImage),
    detailImage: resolveAssetUrl(detailImage || primaryImage),
    images: imageList.map(resolveAssetUrl),
    defaultSize: firstAvailableSize({ sizes, sizeStock: stock }) || sizes[0] || '',
    categories: [categoryKey],
    categoryKey,
    sizes,
    sizeStock: stock,
    brandFilter: normalizeSearch(brand).replace(/[^a-zа-я0-9]+/gi, '-').replace(/^-+|-+$/g, '') || 'brand',
    order: createdTime ? -createdTime : index,
    createdAt: raw.createdAt || '',
    createdTime,
    details: raw.details || raw.description || '',
    raw,
  };
}

function renderProductPrice(product) {
  if (!product) return '';
  const current = product.priceLabel || formatRub(product.price || 0);
  if (product.hasDiscount && product.oldPriceLabel) {
    return `<span class="price-current">${current}</span><span class="price-old">${product.oldPriceLabel}</span>`;
  }
  return `<span class="price-current">${current}</span>`;
}

function getProductPriceText(product) {
  return product?.priceLabel || formatRub(product?.price || 0);
}

async function loadProducts() {
  try {
    const response = await fetch(`${PRODUCTS_URL}?v=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`products.json ${response.status}`);
    const payload = await response.json();
    const source = Array.isArray(payload) ? payload : Array.isArray(payload.products) ? payload.products : [];
    const normalized = source.map(normalizeProduct).filter(Boolean);
    products = Object.fromEntries(normalized.map((product) => [product.id, product]));
  } catch (error) {
    console.warn('ForReal: products.json not loaded', error);
    products = {};
  }

  productCards = [];
  productCardMap = new Map();
  rebuildBrandFilters();
  syncCartWithProducts();
  ensureCurrentProduct();
}

function firstAvailableSize(product) {
  if (!product) return '';
  return (product.sizes || []).find((size) => Number(product.sizeStock?.[size] ?? 0) > 0) || '';
}

function isSizeAvailable(product, size) {
  if (!product || !size) return false;
  return Number(product.sizeStock?.[size] ?? 0) > 0;
}

function hasAnyStock(product) {
  return Boolean(firstAvailableSize(product));
}

function getNewestProductIds(limit = 6) {
  return Object.values(products)
    .filter(hasAnyStock)
    .sort((a, b) => (b.createdTime || 0) - (a.createdTime || 0))
    .slice(0, limit)
    .map((product) => product.id);
}

function rebuildBrandFilters() {
  const container = document.querySelector('.filter-options--brands');
  if (!container) return;
  const brands = [...new Map(Object.values(products)
    .filter((product) => product.brand)
    .map((product) => [product.brandFilter, product.brand])).entries()]
    .sort((a, b) => a[1].localeCompare(b[1]));

  container.innerHTML = '<button class="filter-option" type="button" data-filter-group="brand" data-filter-value="all">ALL</button>' +
    brands.map(([value, label]) => `<button class="filter-option" type="button" data-filter-group="brand" data-filter-value="${value}">${label}</button>`).join('');

  filterOptions = [...document.querySelectorAll('.filter-option')];
  bindFilterOptions();
}

function syncCartWithProducts() {
  cart = cart.filter((item) => products[item.productId]);
  saveCart();
}

function syncSearchInputs() {
  searchInputs.forEach((input) => {
    if (input.value !== filterState.query) input.value = filterState.query;
  });
}

function getCurrentProduct() {
  return products[currentProductId] || Object.values(products)[0] || null;
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
  const category = product?.categoryKey || product?.categories?.[0];
  return categoryLabels[category] || 'КАТАЛОГ';
}

function refreshDetailsPanelHeight() {
  if (!detailsPanel || !isDetailsOpen) return;
  detailsPanel.style.maxHeight = `${detailsPanel.scrollHeight}px`;
}

function renderProductDetails(product) {
  if (!productDetailsList || !product) return;

  const stockText = (product.sizes || [])
    .map((size) => `${size}: ${Number(product.sizeStock?.[size] ?? 0)}`)
    .join(' / ');

  productDetailsList.innerHTML = `
    <p><span>БРЕНД</span><strong>${product.brand}</strong></p>
    <p><span>КАТЕГОРИЯ</span><strong>${getProductCategoryLabel(product)}</strong></p>
    <p><span>РАЗМЕРЫ</span><strong>${product.sizes.join(' / ')}</strong></p>
    ${stockText ? `<p><span>ОСТАТОК</span><strong>${stockText}</strong></p>` : ''}
    ${product.details ? `<p><span>ОПИСАНИЕ</span><strong>${product.details}</strong></p>` : ''}
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

function renderSizeButtons(product) {
  if (!sizeGrid) return;

  const sizes = product?.sizes?.length ? product.sizes : [];
  const selected = selectedSizes[product?.id] || firstAvailableSize(product) || sizes[0] || '';

  sizeGrid.innerHTML = '<span class="size-selector" aria-hidden="true"></span>' + sizes.map((size) => {
    const available = isSizeAvailable(product, size);
    const isSelected = size === selected;
    return `<button type="button" ${isSelected ? 'class="is-selected" aria-pressed="true"' : 'aria-pressed="false"'} ${available ? '' : 'disabled aria-disabled="true"'}>${size}</button>`;
  }).join('');

  sizeButtons = [...sizeGrid.querySelectorAll('button')];
  bindSizeButtons();
  requestAnimationFrame(() => updateSizeSelector(sizeGrid.querySelector('button.is-selected')));
}

function ensureCurrentProduct() {
  if (currentProductId && products[currentProductId]) return;
  currentProductId = Object.values(products)[0]?.id || null;
}

function setCurrentProduct(productId) {
  const product = products[productId] || products[currentProductId] || Object.values(products)[0] || null;

  if (!product) {
    currentProductId = null;
    if (productDetailBrand) productDetailBrand.textContent = '';
    if (productDetailName) productDetailName.textContent = 'ТОВАРЫ НЕ ДОБАВЛЕНЫ';
    if (productDetailPrice) productDetailPrice.textContent = '';
    if (addToCartButton) {
      addToCartButton.disabled = true;
      addToCartButton.textContent = 'НЕТ В НАЛИЧИИ';
    }
    renderSizeButtons(null);
    return;
  }

  currentProductId = product.id;
  const availableSize = firstAvailableSize(product);
  if (!selectedSizes[product.id] || !isSizeAvailable(product, selectedSizes[product.id])) {
    selectedSizes[product.id] = availableSize || product.sizes[0] || '';
  }

  if (productDetailImage) {
    productDetailImage.src = product.detailImage || product.image;
    productDetailImage.alt = `${product.brand} ${product.name}`;
  }

  if (productDetailBrand) productDetailBrand.textContent = product.brand;
  if (productDetailName) productDetailName.textContent = product.name;
  if (productDetailPrice) {
    productDetailPrice.innerHTML = renderProductPrice(product);
    productDetailPrice.classList.toggle('has-discount', Boolean(product.hasDiscount));
  }

  if (addToCartButton) {
    const available = Boolean(availableSize);
    addToCartButton.disabled = !available;
    addToCartButton.setAttribute('aria-disabled', String(!available));
    addToCartButton.textContent = available ? 'В КОРЗИНУ' : 'НЕТ В НАЛИЧИИ';
  }

  renderProductDetails(product);
  renderSizeButtons(product);
}

function updateCartCounter() {
  if (!cartCountBadge) return;

  const count = cart.length;
  cartCountBadge.textContent = String(count);
  cartCountBadge.hidden = count === 0;
  cartCountBadge.setAttribute('aria-label', `${count} товаров в корзине`);
}

function isCartItemAvailable(item) {
  const product = products[item.productId];
  return Boolean(product && isSizeAvailable(product, item.size));
}

function renderCart() {
  if (!cartItemsRoot || !cartEmpty || !cartTotal) return;

  cartItemsRoot.innerHTML = '';
  const hasItems = cart.length > 0;
  const hasUnavailable = cart.some((item) => !isCartItemAvailable(item));
  cartEmpty.hidden = hasItems;

  if (cartTotalBlock) cartTotalBlock.hidden = !hasItems;
  if (purchaseRequestButton) {
    purchaseRequestButton.hidden = !hasItems;
    purchaseRequestButton.disabled = !hasItems || hasUnavailable;
    purchaseRequestButton.setAttribute('aria-disabled', String(!hasItems || hasUnavailable));
  }

  cart.forEach((item) => {
    const product = products[item.productId];
    if (!product) return;

    const available = isSizeAvailable(product, item.size);
    const article = document.createElement('article');
    article.className = `cart-item${available ? '' : ' is-unavailable'}`;
    article.setAttribute('aria-label', `${product.brand} ${product.name} в корзине`);
    article.innerHTML = `
      <div class="cart-item-top">
        <div class="cart-item-image">
          <img src="${product.image}" alt="${product.brand} ${product.name}" />
        </div>

        <div class="cart-item-info">
          <p class="cart-item-brand">${product.brand}</p>
          <h2>${product.name}</h2>
          ${available ? '' : '<p class="cart-unavailable-note">Товар уже не в наличии</p>'}
          <button class="cart-remove" type="button" data-remove-cart="${product.id}">УДАЛИТЬ</button>
        </div>
      </div>

      <div class="cart-item-bottom">
        <span>SIZE ${item.size}</span>
        <strong class="cart-price">${renderProductPrice(product)}</strong>
      </div>
    `;

    cartItemsRoot.append(article);
  });

  const total = cart.reduce((sum, item) => {
    if (!isCartItemAvailable(item)) return sum;
    return sum + (products[item.productId]?.price || 0) * (Number(item.quantity) || 1);
  }, 0);
  cartTotal.textContent = formatRub(total);
  updateCartCounter();
  saveCart();
}

function addCurrentProductToCart() {
  const product = getCurrentProduct();
  if (!product) return;

  const size = selectedSizes[product.id] || firstAvailableSize(product);
  if (!isSizeAvailable(product, size)) return;

  const existing = cart.find((item) => item.productId === product.id && item.size === size);

  if (existing) {
    existing.quantity = 1;
  } else {
    cart.push({ productId: product.id, size, quantity: 1 });
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
    startTelegramProfileSync();
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
  const newestIds = new Set(getNewestProductIds(6));

  let list = Object.values(products).filter((product) => {
    const matchesCategory = filterState.category === 'all' || !filterState.category
      || (filterState.category === 'new' ? newestIds.has(product.id) : product.categories.includes(filterState.category));
    const matchesBrand = filterState.brand === 'all' || product.brandFilter === filterState.brand;
    const matchesSize = !filterState.size || isSizeAvailable(product, filterState.size.toUpperCase()) || product.sizes.map((size) => size.toLowerCase()).includes(filterState.size);
    const productSearchText = normalizeSearch([
      product.brand,
      product.name,
      product.priceLabel,
      product.oldPriceLabel,
      getProductCategoryLabel(product),
      product.sizes.join(' '),
      product.details,
    ].join(' '));
    const matchesSearch = !query || productSearchText.includes(query);

    return matchesCategory && matchesBrand && matchesSize && matchesSearch;
  });

  if (filterState.sort === 'price-desc') {
    list = [...list].sort((a, b) => b.price - a.price);
  } else if (filterState.sort === 'price-asc') {
    list = [...list].sort((a, b) => a.price - b.price);
  } else {
    list = [...list].sort((a, b) => (b.createdTime || 0) - (a.createdTime || 0));
  }

  return list.map((product) => product.id);
}

function createProductCard(product) {
  const article = document.createElement('article');
  article.className = 'product-card';
  article.dataset.route = 'product';
  article.dataset.productId = product.id;
  article.tabIndex = 0;
  article.setAttribute('role', 'button');
  article.setAttribute('aria-label', `Open ${product.brand} ${product.name}`);
  article.innerHTML = `
    <div class="product-image-wrap">
      <img src="${product.image}" alt="${product.brand} ${product.name}" />
    </div>
    <div class="product-info">
      <p class="product-brand">${product.brand}</p>
      <h2>${product.name}</h2>
      <p class="product-price">${renderProductPrice(product)}</p>
    </div>
  `;
  return article;
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
    .map((productId) => products[productId])
    .filter(Boolean)
    .map(createProductCard);

  productGrid.replaceChildren(...visibleCards);
  productCards = [...productGrid.querySelectorAll('[data-product-id]')];
  productCardMap = new Map(productCards.map((card) => [card.dataset.productId, card]));
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


const TELEGRAM_PROFILE_CACHE_KEY = 'forreal_telegram_profile_v2';
let telegramProfileRetryTimer = null;
let telegramProfileLastPhotoUrl = '';

function getTelegramWebApp() {
  return window.Telegram?.WebApp || null;
}

function setupTelegramWebApp() {
  const tg = getTelegramWebApp();
  if (!tg) return;
  try { tg.ready(); } catch (error) {}
  try { tg.expand(); } catch (error) {}
}

function getTelegramInitData() {
  const tgInitData = getTelegramWebApp()?.initData || '';
  if (tgInitData) return tgInitData;

  const sources = [window.location.search, window.location.hash.replace(/^#/, '')];
  for (const source of sources) {
    if (!source) continue;
    try {
      const params = new URLSearchParams(source);
      const tgData = params.get('tgWebAppData') || params.get('tg_web_app_data') || '';
      if (tgData) return tgData;
    } catch (error) {}
  }

  return '';
}

function getUrlParamValue(key) {
  const sources = [window.location.search, window.location.hash.replace(/^#/, '')];
  for (const source of sources) {
    if (!source) continue;
    try {
      const params = new URLSearchParams(source);
      const value = params.get(key);
      if (value) return value;
    } catch (error) {}
  }
  return '';
}

function getUrlTelegramUserCandidate() {
  const uid = getUrlParamValue('fr_uid');
  const firstName = getUrlParamValue('fr_first');
  const lastName = getUrlParamValue('fr_last');
  const username = getUrlParamValue('fr_username');
  const photoUrl = getUrlParamValue('fr_photo');

  if (!uid && !firstName && !lastName && !username && !photoUrl) return null;

  return {
    id: uid,
    first_name: firstName,
    last_name: lastName,
    username,
    photo_url: photoUrl,
  };
}

function resolveProfilePhotoUrl(photoUrl) {
  const value = String(photoUrl || '').trim();
  if (!value) return '';
  try {
    return new URL(value, window.location.href).href;
  } catch (error) {
    return value;
  }
}

function parseTelegramUserCandidate(candidate) {
  if (!candidate) return null;

  if (typeof candidate === 'object') {
    return candidate;
  }

  if (typeof candidate !== 'string') return null;

  const value = candidate.trim();
  if (!value) return null;

  try {
    return JSON.parse(value);
  } catch (error) {
    try {
      return JSON.parse(decodeURIComponent(value));
    } catch (decodeError) {
      return null;
    }
  }
}

function normalizeTelegramUser(user) {
  if (!user || typeof user !== 'object') return null;

  const normalized = {
    id: user.id ? Number(user.id) : null,
    first_name: String(user.first_name || '').trim(),
    last_name: String(user.last_name || '').trim(),
    username: String(user.username || '').replace(/^@+/, '').trim(),
    photo_url: resolveProfilePhotoUrl(user.photo_url || ''),
  };

  if (!normalized.id && !normalized.first_name && !normalized.last_name && !normalized.username && !normalized.photo_url) {
    return null;
  }

  return normalized;
}

function getStoredTelegramUser() {
  try {
    return normalizeTelegramUser(JSON.parse(window.localStorage?.getItem(TELEGRAM_PROFILE_CACHE_KEY) || 'null'));
  } catch (error) {
    return null;
  }
}

function storeTelegramUser(user) {
  const normalized = normalizeTelegramUser(user);
  if (!normalized) return;
  try {
    window.localStorage?.setItem(TELEGRAM_PROFILE_CACHE_KEY, JSON.stringify(normalized));
  } catch (error) {}
}

function mergeTelegramUserCandidates(candidates) {
  const normalizedCandidates = candidates
    .map((candidate) => normalizeTelegramUser(parseTelegramUserCandidate(candidate)))
    .filter(Boolean);

  if (!normalizedCandidates.length) return null;

  const merged = {
    id: null,
    first_name: '',
    last_name: '',
    username: '',
    photo_url: '',
  };

  normalizedCandidates.forEach((user) => {
    // Берем данные не из первого попавшегося источника, а склеиваем их.
    // Частый кейс: URL от бота дает username, а Telegram WebApp/initData дает photo_url.
    if (!merged.id && user.id) merged.id = user.id;
    if (!merged.first_name && user.first_name) merged.first_name = user.first_name;
    if (!merged.last_name && user.last_name) merged.last_name = user.last_name;
    if (!merged.username && user.username) merged.username = user.username;
    if (!merged.photo_url && user.photo_url) merged.photo_url = user.photo_url;
  });

  return normalizeTelegramUser(merged);
}

function getTelegramUser(options = {}) {
  const allowStored = options.allowStored !== false;
  const tg = getTelegramWebApp();
  const candidates = [];

  // Сначала URL-параметры от персональной кнопки бота.
  candidates.push(getUrlTelegramUserCandidate());

  // Потом реальные Telegram WebApp данные. Они могут содержать photo_url,
  // даже если URL уже дал username. Поэтому нельзя останавливаться на первом кандидате.
  candidates.push(tg?.initDataUnsafe?.user);

  const initData = getTelegramInitData();
  if (initData) {
    try {
      const params = new URLSearchParams(initData);
      candidates.push(params.get('user'));
    } catch (error) {}
  }

  if (allowStored) {
    candidates.push(getStoredTelegramUser());
  }

  const merged = mergeTelegramUserCandidates(candidates);
  if (merged) {
    storeTelegramUser(merged);
    return merged;
  }

  return null;
}

function getCurrentTelegramId() {
  const userId = getTelegramUser()?.id;
  return userId ? Number(userId) : null;
}

function getCleanTelegramUsername(user) {
  return String(user?.username || '').replace(/^@+/, '').trim();
}

function getTelegramDisplayName(user) {
  const username = getCleanTelegramUsername(user);
  if (username) return username;

  const firstName = String(user?.first_name || '').trim();
  const lastName = String(user?.last_name || '').trim();
  const fullName = [firstName, lastName].filter(Boolean).join(' ').trim();
  return fullName || 'Пользователь';
}

function getProfileInitials(user) {
  const firstName = String(user?.first_name || '').trim();
  const lastName = String(user?.last_name || '').trim();
  const username = getCleanTelegramUsername(user);

  const fromName = [firstName, lastName]
    .filter(Boolean)
    .map((part) => Array.from(part)[0])
    .join('');

  const fallback = fromName || Array.from(username).slice(0, 2).join('') || 'FR';
  return fallback.toUpperCase();
}

function resetProfileAvatar(user = null) {
  if (profileAvatarImage) {
    profileAvatarImage.onload = null;
    profileAvatarImage.onerror = null;
    profileAvatarImage.removeAttribute('src');
  }

  if (profileAvatarPlaceholder) {
    profileAvatarPlaceholder.textContent = getProfileInitials(user);
  }

  if (profileAvatarWrap) {
    profileAvatarWrap.classList.remove('has-photo', 'is-loading-photo');
  }

  telegramProfileLastPhotoUrl = '';
}

function setProfileAvatar(photoUrl, user) {
  if (!profileAvatarImage || !profileAvatarWrap) return;
  if (!photoUrl) return;
  if (telegramProfileLastPhotoUrl === photoUrl && profileAvatarWrap.classList.contains('has-photo')) return;

  telegramProfileLastPhotoUrl = photoUrl;
  profileAvatarWrap.classList.add('is-loading-photo');
  profileAvatarWrap.classList.remove('has-photo');

  profileAvatarImage.onload = () => {
    profileAvatarWrap.classList.remove('is-loading-photo');
    profileAvatarWrap.classList.add('has-photo');
  };

  profileAvatarImage.onerror = () => {
    resetProfileAvatar(user);
  };

  profileAvatarImage.src = photoUrl;
}

function renderTelegramProfile(options = {}) {
  const user = getTelegramUser(options);

  if (profileUsername) {
    profileUsername.textContent = getTelegramDisplayName(user);
  }

  if (profileAvatarPlaceholder) {
    profileAvatarPlaceholder.textContent = getProfileInitials(user);
  }

  const photoUrl = String(user?.photo_url || '').trim();
  if (photoUrl) {
    setProfileAvatar(photoUrl, user);
  } else if (!profileAvatarWrap?.classList.contains('has-photo')) {
    resetProfileAvatar(user);
  }

  return user;
}

function startTelegramProfileSync() {
  setupTelegramWebApp();
  window.clearTimeout(telegramProfileRetryTimer);

  let attempt = 0;
  const maxAttempts = 30;

  const tick = () => {
    const freshUser = renderTelegramProfile({ allowStored: false });
    const hasDisplayProfile = Boolean(freshUser?.username || freshUser?.first_name || freshUser?.last_name || freshUser?.photo_url);
    if (hasDisplayProfile || attempt >= maxAttempts) {
      if (!hasDisplayProfile) renderTelegramProfile({ allowStored: true });
      return;
    }

    attempt += 1;
    telegramProfileRetryTimer = window.setTimeout(tick, 150);
  };

  tick();
}

function ensureCheckoutStatusElement() {
  let node = document.querySelector('[data-checkout-status]');
  if (node) return node;
  const actions = document.querySelector('.checkout-actions');
  if (!actions) return null;
  node = document.createElement('p');
  node.className = 'checkout-status';
  node.dataset.checkoutStatus = 'true';
  node.hidden = true;
  actions.prepend(node);
  return node;
}

function setCheckoutStatus(message = '', type = 'info') {
  const node = ensureCheckoutStatusElement();
  if (!node) return;
  node.textContent = message;
  node.dataset.statusType = type;
  node.hidden = !message;
  requestAnimationFrame(refreshActiveDeliveryFormHeight);
}

function getCheckoutInput(name) {
  return document.querySelector(`[name="${name}"]`);
}

function getCheckoutValue(name) {
  return String(getCheckoutInput(name)?.value || '').trim();
}

function setCheckoutLoading(isLoading) {
  if (!checkoutSubmitButton) return;
  checkoutSubmitButton.disabled = isLoading;
  checkoutSubmitButton.setAttribute('aria-disabled', String(isLoading));
  checkoutSubmitButton.textContent = isLoading ? 'ОФОРМЛЯЕМ...' : 'ОФОРМИТЬ ЗАКАЗ';
}

function collectDeliveryData(method) {
  return {
    fullName: getCheckoutValue(`${method}-name`),
    phone: getCheckoutValue(`${method}-phone`),
    city: getCheckoutValue(`${method}-city`),
    address: getCheckoutValue(`${method}-address`),
  };
}

function validateDeliveryData(data) {
  return Boolean(data.fullName && data.phone && data.city && data.address);
}

function buildOrderPayload(method) {
  return {
    type: 'order',
    clientOrderId: `forreal-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    items: cart
      .filter(isCartItemAvailable)
      .map((item) => ({
        productId: item.productId,
        size: item.size,
        quantity: Number(item.quantity) || 1,
      })),
    deliveryMethod: method,
    deliveryData: collectDeliveryData(method),
    comment: getCheckoutValue('order-comment'),
  };
}

function clearCartAfterOrder() {
  cart = [];
  saveCart();
  renderCart();
}

async function postOrderToApi(payload) {
  if (!API_BASE) throw new Error('API_NOT_CONFIGURED');
  const initData = getTelegramInitData();
  if (!initData) throw new Error('INIT_DATA_MISSING');

  const response = await fetch(`${API_BASE}/api/orders`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Telegram-Init-Data': initData,
    },
    body: JSON.stringify(payload),
  });

  let data = null;
  try { data = await response.json(); } catch (error) { data = null; }

  if (!response.ok) {
    const detail = data?.detail || 'Не удалось оформить заказ';
    throw new Error(Array.isArray(detail) ? detail.map((item) => item.msg).join(', ') : detail);
  }

  return data;
}

function sendOrderViaTelegram(payload) {
  if (!window.Telegram?.WebApp?.sendData) return false;
  window.Telegram.WebApp.sendData(JSON.stringify(payload));
  return true;
}

function loadLocalOrders() {
  try {
    const raw = window.localStorage?.getItem(LOCAL_ORDERS_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : localOrdersMemory;
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    console.warn('ForReal: local orders not loaded', error);
    return Array.isArray(localOrdersMemory) ? localOrdersMemory : [];
  }
}

function saveLocalOrders(orders) {
  const safeOrders = Array.isArray(orders) ? orders : [];
  localOrdersMemory = safeOrders;
  try {
    window.localStorage?.setItem(LOCAL_ORDERS_STORAGE_KEY, JSON.stringify(safeOrders));
  } catch (error) {
    console.warn('ForReal: local orders not saved', error);
  }
}

function buildLocalOrderFromPayload(payload) {
  const now = new Date().toISOString();
  const items = cart
    .filter(isCartItemAvailable)
    .map((item) => {
      const product = products[item.productId];
      const quantity = Number(item.quantity) || 1;
      const price = Number(product?.price) || 0;
      return {
        productId: item.productId,
        productSnapshot: product?.raw || product || {},
        brand: product?.brand || '',
        name: product?.name || '',
        size: item.size,
        quantity,
        price,
      };
    });

  return {
    id: payload.clientOrderId,
    orderNumber: null,
    clientOrderId: payload.clientOrderId,
    items,
    totalPrice: items.reduce((sum, item) => sum + item.price * item.quantity, 0),
    currency: 'RUB',
    deliveryMethod: payload.deliveryMethod,
    deliveryData: payload.deliveryData || {},
    comment: payload.comment || '',
    status: 'awaiting_payment',
    createdAt: now,
    updatedAt: now,
    isLocal: true,
  };
}

function saveLocalOrder(order) {
  if (!order?.clientOrderId && !order?.id) return;
  const key = order.clientOrderId || order.id;
  const orders = loadLocalOrders();
  const withoutDuplicate = orders.filter((item) => (item.clientOrderId || item.id) !== key);
  withoutDuplicate.unshift(order);
  saveLocalOrders(withoutDuplicate.slice(0, 50));
}

function mergeOrders(apiOrders = [], localOrders = []) {
  const seen = new Set();
  const result = [];
  [...apiOrders, ...localOrders].forEach((order) => {
    const key = order?.clientOrderId || order?.id || String(order?.orderNumber || '');
    if (!key || seen.has(key)) return;
    seen.add(key);
    result.push(order);
  });
  return result;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function buildOrderCard(order) {
  const statusMap = {
    awaiting_payment: 'Ожидает оплаты',
    paid: 'Оплачено',
    in_delivery: 'В доставке',
    awaiting_pickup: 'Ожидает получения',
    closed: 'Закрыт',
    canceled: 'Отменен',
  };
  const deliveryMap = { cdek: 'CDEK', yandex: 'Яндекс Доставка', pickup: 'Самовывоз' };
  const items = Array.isArray(order.items) ? order.items : [];
  const itemsText = items
    .map((item) => `${item.brand || ''} ${item.name || ''} / ${item.size || ''}`.trim())
    .filter(Boolean)
    .join(' · ');
  const date = order.createdAt ? new Date(order.createdAt).toLocaleDateString('ru-RU') : '';
  const title = order.orderNumber ? `#${order.orderNumber}` : 'ЗАКАЗ';
  const article = document.createElement('article');
  article.className = 'profile-order-item';
  article.innerHTML = `
    <div class="profile-order-row">
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(statusMap[order.status] || order.status || '—')}</span>
    </div>
    <p>${escapeHtml(itemsText || 'Товары')}</p>
    <div class="profile-order-meta">
      <span>${escapeHtml(formatRub(order.totalPrice || 0))}</span>
      <span>${escapeHtml(deliveryMap[order.deliveryMethod] || order.deliveryMethod || '')}</span>
      <span>${escapeHtml(date)}</span>
    </div>
  `;
  return article;
}

function renderOrdersList(orders = []) {
  if (!ordersPanel) return;
  ordersPanel.innerHTML = '';
  if (!orders.length) {
    const empty = document.createElement('div');
    empty.className = 'profile-info-empty';
    empty.textContent = 'ЗАКАЗОВ ПОКА НЕТ';
    ordersPanel.append(empty);
  } else {
    orders.forEach((order) => ordersPanel.append(buildOrderCard(order)));
  }
  requestAnimationFrame(refreshOrdersPanelHeight);
}

async function loadPublicOrders() {
  const telegramId = getCurrentTelegramId();
  if (!telegramId || !ORDERS_PUBLIC_URL) return [];

  const separator = ORDERS_PUBLIC_URL.includes('?') ? '&' : '?';
  const response = await fetch(`${ORDERS_PUBLIC_URL}${separator}v=${Date.now()}`, { cache: 'no-store' });
  if (!response.ok) throw new Error('public orders fetch failed');

  const orders = await response.json();
  if (!Array.isArray(orders)) return [];

  return orders.filter((order) => Number(order?.telegramId) === Number(telegramId));
}

async function loadMyOrders() {
  if (!ordersPanel) return;
  const localOrders = loadLocalOrders();

  try {
    const publicOrders = await loadPublicOrders();
    if (publicOrders.length || !API_BASE) {
      renderOrdersList(mergeOrders(publicOrders, localOrders));
      return;
    }
  } catch (error) {
    console.warn('ForReal: public orders not loaded', error);
  }

  if (!API_BASE || !getTelegramInitData()) {
    renderOrdersList(localOrders);
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/api/orders/my`, {
      headers: { 'X-Telegram-Init-Data': getTelegramInitData() },
      cache: 'no-store',
    });
    if (!response.ok) throw new Error('orders fetch failed');
    const orders = await response.json();
    renderOrdersList(mergeOrders(Array.isArray(orders) ? orders : [], localOrders));
  } catch (error) {
    console.warn('ForReal: orders not loaded', error);
    renderOrdersList(localOrders);
  }
}

function buildPickupMessage() {
  const lines = ['Привет, хочу заказать:', ''];
  const validItems = cart.filter(isCartItemAvailable);
  validItems.forEach((item, index) => {
    const product = products[item.productId];
    lines.push(`${index + 1}. ${product.brand} — ${product.name}`);
    lines.push(`Размер: ${item.size}`);
    lines.push(`Цена: ${getProductPriceText(product)}`);
    lines.push(`Фото: ${new URL((product.images?.[0] || product.image).replace(/^\.\//, ''), window.location.href).href}`);
    lines.push('');
  });
  const total = validItems.reduce((sum, item) => sum + (products[item.productId]?.price || 0), 0);
  lines.push(`Итого: ${formatRub(total)}`);
  lines.push('Способ получения: Самовывоз');
  return lines.join('\n');
}

function openAdminChat() {
  const message = cart.length ? buildPickupMessage() : '';
  const url = `https://t.me/${ADMIN_USERNAME}${message ? `?text=${encodeURIComponent(message)}` : ''}`;

  if (window.Telegram?.WebApp?.openTelegramLink) {
    window.Telegram.WebApp.openTelegramLink(url);
    return;
  }

  window.open(url, '_blank', 'noopener,noreferrer');
}

async function submitCheckout() {
  if (cart.length === 0) return;
  if (cart.some((item) => !isCartItemAvailable(item))) {
    setCheckoutStatus('В корзине есть товар, который уже не в наличии.', 'error');
    return;
  }

  const method = getActiveDeliveryMethod();
  if (method === 'pickup') {
    openAdminChat();
    return;
  }

  const payload = buildOrderPayload(method);
  if (!payload.items.length) {
    setCheckoutStatus('Корзина пустая.', 'error');
    return;
  }
  if (!validateDeliveryData(payload.deliveryData)) {
    setCheckoutStatus('Заполните все данные доставки.', 'error');
    return;
  }

  const localOrder = buildLocalOrderFromPayload(payload);

  setCheckoutLoading(true);
  setCheckoutStatus('', 'info');

  try {
    if (API_BASE) {
      const order = await postOrderToApi(payload);
      saveLocalOrder(order || localOrder);
      clearCartAfterOrder();
      closeCheckout();
      setActive('profile');
      await loadMyOrders();
      setCheckoutStatus('', 'info');
      return order;
    }

    if (sendOrderViaTelegram(payload)) {
      saveLocalOrder(localOrder);
      clearCartAfterOrder();
      closeCheckout();
      setActive('profile');
      renderOrdersList(loadLocalOrders());
      setCheckoutStatus('', 'info');
      return null;
    }

    throw new Error('API_NOT_CONFIGURED');
  } catch (error) {
    console.error('ForReal order error', error);
    const fallbackAllowed = !API_BASE && sendOrderViaTelegram(payload);
    if (fallbackAllowed) {
      saveLocalOrder(localOrder);
      clearCartAfterOrder();
      closeCheckout();
      setActive('profile');
      renderOrdersList(loadLocalOrders());
      setCheckoutStatus('', 'info');
      return null;
    }

    const message = error.message === 'INIT_DATA_MISSING'
      ? 'Откройте каталог через Telegram и попробуйте еще раз.'
      : error.message === 'API_NOT_CONFIGURED'
        ? 'API для заказов пока не настроен.'
        : error.message || 'Не удалось оформить заказ.';
    setCheckoutStatus(message, 'error');
    return null;
  } finally {
    setCheckoutLoading(false);
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
  item.addEventListener('click', () => {
    setActive(item.dataset.tab);
    if (item.dataset.tab === 'profile') {
      loadMyOrders();
    }
  });
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
    if (button.dataset.route === 'profile') loadMyOrders();
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


if (productGrid) {
  productGrid.addEventListener('click', (event) => {
    const card = event.target.closest('[data-product-id]');
    if (!card) return;
    setCurrentProduct(card.dataset.productId);
    setActive('product');
  });

  productGrid.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    const card = event.target.closest('[data-product-id]');
    if (!card) return;
    event.preventDefault();
    setCurrentProduct(card.dataset.productId);
    setActive('product');
  });
}

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

function bindFilterOptions() {
  filterOptions.forEach((button) => {
    if (button.dataset.boundFilter === 'true') return;
    button.dataset.boundFilter = 'true';
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
}

bindFilterOptions();

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
  checkoutSubmitButton.addEventListener('click', () => { submitCheckout(); });
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

function bindSizeButtons() {
  sizeButtons.forEach((button) => {
    if (button.dataset.boundSize === 'true') return;
    button.dataset.boundSize = 'true';
    button.addEventListener('click', () => {
      if (button.disabled) return;
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
}

bindSizeButtons();

window.addEventListener('resize', () => {
  const active = document.querySelector('.nav-item.is-active');
  if (active) moveIndicator(active);
  updateSizeSelector();
  refreshActiveDeliveryFormHeight();
  refreshDetailsPanelHeight();
  refreshOrdersPanelHeight();
});

async function initApp() {
  startTelegramProfileSync();
  await loadProducts();
  const active = document.querySelector('.nav-item.is-active');
  if (active) moveIndicator(active);
  setCurrentProduct(currentProductId);
  renderCart();
  renderCatalog();
  updateSizeSelector();
  setDeliveryMethod('pickup');
  setOrdersOpen(true);
  await loadMyOrders();
  setDetailsOpen(false);
}

window.addEventListener('load', initApp);