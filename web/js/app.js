// Инициализация Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand(); // Открываем на всю высоту
tg.ready();

// Миграция старой корзины { "1": 2 } в новый формат с вариантами { "1_Color": {product_id: 1, quantity: 2, variant: "Color"} }
let storedCart = JSON.parse(localStorage.getItem('vape_cart') || '{}');
for (let key in storedCart) {
    if (typeof storedCart[key] === 'number') {
        const qty = storedCart[key];
        delete storedCart[key];
        storedCart[key] = { product_id: parseInt(key), quantity: qty, variant: null };
    }
}

// Утилита для строгого форматирования цен (всегда 2 знака после запятой)
const formatPrice = (num) => Number(num || 0).toFixed(2);

// Глобальное состояние
const appState = {
    profile: null,
    allProducts: [], // Храним все товары для мгновенного поиска
    products: [], 
    categories: [],
    activeCategoryId: null,
    cart: storedCart,
    favorites: new Set(JSON.parse(localStorage.getItem('vape_favorites') || '[]')), 
    currentTab: 'catalog',
    activeProduct: null,
    selectedVariant: null,
    promoCode: null
};

// Строгое получение реальных данных авторизации от Telegram (никаких заглушек)
const getInitData = () => window.Telegram.WebApp.initData;

// --- ГЛОБАЛЬНАЯ ОБЕРТКА ДЛЯ API ЗАПРОСОВ ---
async function apiFetch(url, options = {}) {
    const headers = new Headers(options.headers || {});
    // Автоматически прикрепляем данные для авторизации к каждому запросу
    headers.set('X-Telegram-Init-Data', getInitData());
    headers.set('Authorization', `Bearer ${getInitData()}`); // Дублируем для надежности
    
    return fetch(url, { ...options, headers });
}

// --- ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ И АВТОРИЗАЦИЯ ---
async function initializeApp() {
    const initDataStr = window.Telegram.WebApp.initData;
    
    if (!initDataStr) {
        console.error("⚠️ Приложение запущено вне Telegram или произошла ошибка получения данных.");
        tg.showAlert("Ошибка: нет данных авторизации.\nУбедитесь, что открываете магазин по специальной кнопке (WebApp) в боте, а не по обычной ссылке.");
        return; // Останавливаем инициализацию без валидных данных
    }

    try {
        // Обращаемся к новому эндпоинту авторизации
        const response = await apiFetch('/api/auth/login', {
            method: 'POST'
        });

        if (response.ok) {
            const userData = await response.json();
            
            // Сохраняем глобально
            window.currentUser = userData;
            appState.profile = userData;
            
            // Сразу обновляем интерфейс
            renderProfile(userData);
            
            // Если есть лоадер, здесь его можно скрыть: document.getElementById('loader')?.classList.add('hidden');
            switchTab('catalog');
        } else {
            console.error("Ошибка авторизации. Статус:", response.status);
        }
    } catch (error) {
        console.error("Сетевая ошибка при инициализации приложения:", error);
    }
}

// Отдельная функция для обновления данных профиля в фоне
async function loadUserProfile() {
    try {
        const response = await apiFetch('/api/user/profile');
        if (response.ok) {
            const userData = await response.json();
            window.currentUser = userData;
            appState.profile = userData;
            renderProfile(userData);
        }
    } catch (error) { console.error("Ошибка обновления профиля", error); }
}

// Моментальное обновление визуала профиля из клиента Telegram
function renderProfileHeader(dbUser = null) {
    const tgUser = window.Telegram.WebApp.initDataUnsafe?.user;
    const nameEl = document.getElementById('profile-name');
    const usernameEl = document.getElementById('profile-username');
    
    if (tgUser) {
        if (nameEl) nameEl.textContent = tgUser.first_name || tgUser.username || "Пользователь";
    } else if (dbUser) {
        if (nameEl) nameEl.textContent = dbUser.username || "Пользователь";
    }
    
    if (dbUser && dbUser.username && usernameEl) {
        usernameEl.textContent = `@${dbUser.username}`;
    } else if (tgUser && tgUser.username && usernameEl) {
        usernameEl.textContent = `@${tgUser.username}`;
    }
}

// Функция переключения вкладок
function switchTab(tabName) {
    appState.currentTab = tabName;

    // Закрываем детальный вид, если переключаемся через нижнее меню
    if(tabName !== 'product-details') closeProductDetails();

    // 1. Скрываем все экраны
    document.querySelectorAll('.tab-screen').forEach(el => el.classList.add('hidden'));
    
    // 2. Показываем нужный экран
    document.getElementById(`tab-${tabName}`).classList.remove('hidden');

    // Специфичная логика при открытии вкладок
    if (tabName === 'cart') {
        renderCart();
    }
    
    if (tabName === 'profile') {
        if (window.currentUser) renderProfile(window.currentUser); // Показываем сразу из кэша
        loadUserProfile(); // Параллельно тянем свежие данные (баланс)
    }

    // 3. Обновляем цвета кнопок в навигации
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('text-app-accent');
        btn.classList.add('text-app-muted');
    });
    const activeBtn = document.getElementById(`nav-${tabName}`);
    if (activeBtn) {
        activeBtn.classList.remove('text-app-muted');
        activeBtn.classList.add('text-app-accent');
    }
    
    // Telegram Haptic Feedback при переключении вкладки
    tg.HapticFeedback.selectionChanged();
}

// --- ЛОГИКА КАТАЛОГА И ТОВАРОВ ---

async function fetchCategories() {
    try {
        const response = await apiFetch('/api/catalog/categories');
        if (response.ok) {
            appState.categories = await response.json();
            renderCategories();
        }
    } catch (error) {
        console.error("Ошибка загрузки категорий:", error);
    }
}

function renderCategories() {
    const container = document.getElementById('categories-container');
    if (!container) return;
    
    // Кнопка "Все"
    let html = `<button onclick="selectCategory(null)" class="px-4 py-1.5 rounded-full whitespace-nowrap transition-colors ${appState.activeCategoryId === null ? 'bg-app-accent text-white font-medium shadow-md shadow-blue-500/20' : 'bg-app-card text-app-muted border border-white/5 hover:text-white'}">Все</button>`;
    
    // Кнопки категорий из БД
    appState.categories.forEach(c => {
        const isActive = appState.activeCategoryId === c.id;
        html += `<button onclick="selectCategory(${c.id})" class="px-4 py-1.5 rounded-full whitespace-nowrap transition-colors ${isActive ? 'bg-app-accent text-white font-medium shadow-md shadow-blue-500/20' : 'bg-app-card text-app-muted border border-white/5 hover:text-white'}">${c.name}</button>`;
    });
    
    container.innerHTML = html;
}

function selectCategory(id) {
    appState.activeCategoryId = id;
    tg.HapticFeedback.selectionChanged();
    renderCategories();
    filterAndRenderProducts(); // Мгновенная фильтрация на клиенте
}

async function fetchProducts() {
    try {
        const response = await apiFetch('/api/catalog/products');
        
        if (response.ok) {
            appState.allProducts = await response.json();
        } else {
            appState.allProducts = [];
        }
        filterAndRenderProducts();
        updateCartBadges(); // Обновляем бейджи после загрузки, т.к. корзина тянется из localStorage
    } catch (error) {
        console.error("Ошибка загрузки товаров:", error);
    }
}

function filterAndRenderProducts() {
    let filtered = appState.allProducts;
    
    // Фильтр по категории
    if (appState.activeCategoryId !== null) {
        filtered = filtered.filter(p => p.category_id === appState.activeCategoryId);
    }
    
    // Фильтр по поиску
    const query = document.getElementById('catalog-search').value.trim().toLowerCase();
    if (query) {
        filtered = filtered.filter(p => p.name.toLowerCase().includes(query) || (p.description && p.description.toLowerCase().includes(query)));
    }
    
    appState.products = filtered;
    renderProducts(filtered);
}

function renderProducts(productsToRender) {
    const grid = document.getElementById('products-grid');

    if (productsToRender.length === 0) {
        grid.innerHTML = '<div class="col-span-2 text-center text-app-muted mt-10">Товары не найдены</div>';
        return;
    }

    let html = '';
    productsToRender.forEach(p => {
        const isFav = appState.favorites.has(p.id);
        
        html += `
        <div class="bg-app-card rounded-2xl p-2 flex flex-col relative cursor-pointer active:scale-95 transition-transform border border-white/5" onclick="showProductDetails(${p.id})">
            <div class="h-36 bg-white rounded-xl mb-3 flex items-center justify-center overflow-hidden relative">
                <img src="${p.image_url || ''}" class="object-contain h-full w-full p-2" alt="Фото" loading="lazy">
                <button onclick="event.stopPropagation(); toggleFavorite(${p.id})" class="absolute top-2 right-2 bg-black/20 backdrop-blur-md w-8 h-8 rounded-full flex items-center justify-center text-${isFav ? 'app-accent' : 'white'} hover:scale-110 transition-transform border border-white/10">
                    <svg fill="${isFav ? 'currentColor' : 'none'}" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4"><path stroke-linecap="round" stroke-linejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" /></svg>
                </button>
            </div>
            <h2 class="text-[13px] font-medium mb-2 line-clamp-2 leading-snug flex-1">${p.name}</h2>
            <div class="mt-auto">
                <span class="font-bold text-[15px] text-app-accent leading-none">${formatPrice(p.price)} Br</span>
            </div>
        </div>`;
    });
    grid.innerHTML = html;
}

let searchTimeout;
function handleSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        filterAndRenderProducts();
    }, 150); // Снизили задержку: фильтрация мгновенная
}

// --- ЛОГИКА ДЕТАЛЬНОГО ЭКРАНА ТОВАРА ---

function showProductDetails(productId) {
    const product = appState.products.find(p => p.id === productId);
    if (!product) return;
    
    appState.activeProduct = product;
    
    // Заполняем данные
    document.getElementById('detail-img').src = product.image_url || '';
    document.getElementById('detail-title').textContent = product.name;
    document.getElementById('detail-desc').textContent = product.description || 'Описание отсутствует.';
    
    const btn = document.getElementById('detail-add-btn');
    btn.textContent = `В корзину / ${product.price} Br`;
    btn.onclick = () => {
        addToCart(product.id);
        tg.HapticFeedback.impactOccurred('medium');
    };

    // Рендерим варианты (если есть в characteristics)
    const variantsContainer = document.getElementById('detail-variants');
    variantsContainer.innerHTML = '';
    
    const colors = product.characteristics?.colors || ["Стандартный"];
    colors.forEach((color, idx) => {
        const isSelected = idx === 0; // По умолчанию выбран первый
        const vBtn = document.createElement('button');
        vBtn.className = `px-5 py-2.5 rounded-[12px] bg-app-card whitespace-nowrap text-[13px] font-medium transition-colors border ${isSelected ? 'border-app-accent text-white' : 'border-white/5 text-app-muted'}`;
        vBtn.textContent = color;
        variantsContainer.appendChild(vBtn);
    });

    // Показываем окно
    document.getElementById('tab-product-details').classList.remove('hidden');
    tg.BackButton.show();
    tg.BackButton.onClick(closeProductDetails);
}

function selectVariant(variant, allVariants) {
    appState.selectedVariant = variant;
    tg.HapticFeedback.selectionChanged();
    
    const variantsContainer = document.getElementById('detail-variants');
    variantsContainer.innerHTML = '';
    allVariants.forEach((v) => {
        const isSelected = v === appState.selectedVariant;
        const vBtn = document.createElement('button');
        vBtn.className = `px-5 py-2.5 rounded-[12px] bg-app-card whitespace-nowrap text-[13px] font-medium transition-colors border ${isSelected ? 'border-app-accent text-white' : 'border-white/5 text-app-muted'} active:scale-95`;
        vBtn.textContent = v;
        vBtn.onclick = () => selectVariant(v, allVariants);
        variantsContainer.appendChild(vBtn);
    });
}

function closeProductDetails() {
    document.getElementById('tab-product-details').classList.add('hidden');
    tg.BackButton.hide();
    appState.activeProduct = null;
}

// --- ЛОГИКА ПРОФИЛЯ ---
function renderProfile(userData) {
    if (!userData) return;
    
    const balEl = document.getElementById('profile-balance');
    if (balEl) balEl.textContent = `${formatPrice(userData.balance)} Br`;
    
    const bonEl = document.getElementById('profile-bonuses');
    if (bonEl) bonEl.textContent = `${userData.bonus_points} pts`;
    
    const discEl = document.getElementById('profile-discount');
    if (discEl) discEl.textContent = `${userData.personal_discount}%`;
    
    // Обновляем шапку, подтянув данные из базы
    renderProfileHeader(userData);
}

async function fetchOrders() {
    // Показываем экран и лоадер
    document.getElementById('orders-history-screen').classList.remove('hidden');
    tg.BackButton.show();
    tg.BackButton.onClick(closeOrdersHistory);
    
    const list = document.getElementById('orders-list');
    list.innerHTML = '<div class="text-center text-app-muted mt-10">Загрузка...</div>';
    
    try {
        const res = await apiFetch('/api/orders/my');
        if (res.ok) {
            const orders = await res.json();
            renderOrdersList(orders);
        } else {
            list.innerHTML = '<div class="text-center text-red-400 mt-10">Ошибка при загрузке данных</div>';
        }
    } catch (error) {
        list.innerHTML = '<div class="text-center text-red-400 mt-10">Ошибка сети</div>';
    }
}

function renderOrdersList(orders) {
    const list = document.getElementById('orders-list');
    
    if (orders.length === 0) {
        list.innerHTML = '<div class="text-center text-app-muted mt-10">У вас еще нет оформленных заказов 😔</div>';
        return;
    }
    
    let html = '';
    orders.forEach(o => {
        // Форматируем дату
        const date = new Date(o.created_at).toLocaleDateString('ru-RU', { day: '2-digit', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' });
        
        // Красивые бейджи для статусов
        let statusHtml = '';
        switch(o.status) {
            case 'pending': statusHtml = '<span class="text-yellow-400 bg-yellow-400/10 px-2 py-1 rounded-md text-xs font-bold">Ожидает</span>'; break;
            case 'paid': statusHtml = '<span class="text-blue-400 bg-blue-400/10 px-2 py-1 rounded-md text-xs font-bold">Оплачен</span>'; break;
            case 'delivered': statusHtml = '<span class="text-green-400 bg-green-400/10 px-2 py-1 rounded-md text-xs font-bold">Доставлен</span>'; break;
            case 'canceled': statusHtml = '<span class="text-red-400 bg-red-400/10 px-2 py-1 rounded-md text-xs font-bold">Отменен</span>'; break;
            default: statusHtml = `<span class="text-gray-400 bg-gray-400/10 px-2 py-1 rounded-md text-xs font-bold">${o.status}</span>`;
        }
        
        // Формируем список купленных товаров, подтягивая имена из кэша appState.products
        const itemsHtml = o.items.map(i => {
            const product = appState.products.find(p => p.id === i.product_id) || { name: `Товар ID: ${i.product_id}` };
            const variantText = i.variant ? ` <span class="text-app-accent text-[10px]">(${i.variant})</span>` : '';
            return `<div class="text-[13px] text-gray-300 flex justify-between mb-1 items-center">
                        <span class="flex-1">- ${product.name}${variantText} <span class="text-white font-bold ml-1">x${i.quantity}</span></span>
                        <span>${formatPrice(i.price_at_purchase * i.quantity)} Br</span>
                    </div>`;
        }).join('');
        
        html += `
            <div class="bg-app-card rounded-2xl p-4 border border-white/5 mb-3">
                <div class="flex justify-between items-start mb-3">
                    <div>
                        <div class="font-bold">Заказ #${o.id}</div>
                        <div class="text-xs text-app-muted">${date}</div>
                    </div>
                    ${statusHtml}
                </div>
                <div class="my-3 pt-2 border-t border-white/5">
                    ${itemsHtml}
                </div>
                ${o.promo_code_used ? `<div class="text-xs text-app-accent mb-2">Применен промокод: ${o.promo_code_used}</div>` : ''}
                <div class="flex justify-between items-center mt-3 pt-3 border-t border-white/5">
                    <span class="text-sm text-app-muted">Итоговая сумма:</span>
                    <span class="font-bold text-app-accent text-lg">${formatPrice(o.total_price)} Br</span>
                </div>
            </div>
        `;
    });
    list.innerHTML = html;
}

function closeOrdersHistory() {
    document.getElementById('orders-history-screen').classList.add('hidden');
    // Возвращаем обработчик кнопки "Назад" если мы были внутри деталей товара
    if (appState.activeProduct) {
        tg.BackButton.onClick(closeProductDetails);
    } else {
        tg.BackButton.hide();
    }
}


// --- ЛОГИКА КОРЗИНЫ ---

function saveCart() {
    localStorage.setItem('vape_cart', JSON.stringify(appState.cart));
    updateCartBadges();
}

function addToCart(productId, variant = null) {
    // Уникальный ключ для корзины, чтобы разные цвета лежали отдельно
    const cartItemId = variant ? `${productId}_${variant}` : `${productId}`;
    
    if (appState.cart[cartItemId]) {
        appState.cart[cartItemId].quantity += 1;
    } else {
        appState.cart[cartItemId] = { product_id: productId, quantity: 1, variant: variant };
    }
    
    saveCart();
    tg.HapticFeedback.impactOccurred('light');
}

function updateCartQuantity(cartItemId, delta) {
    if (!appState.cart[cartItemId]) return;
    appState.cart[cartItemId].quantity += delta;
    if (appState.cart[cartItemId].quantity <= 0) delete appState.cart[cartItemId];
    saveCart();
    tg.HapticFeedback.selectionChanged();
    renderCart();
}

function removeFromCart(cartItemId) {
    delete appState.cart[cartItemId];
    saveCart();
    tg.HapticFeedback.impactOccurred('medium');
    renderCart();
}

async function renderCart() {
    const itemsContainer = document.getElementById('cart-items');
    const emptyState = document.getElementById('cart-empty');
    const receipt = document.getElementById('cart-receipt');
    
    itemsContainer.innerHTML = '';
    const cartKeys = Object.keys(appState.cart);
    
    if (cartKeys.length === 0) {
        emptyState.classList.remove('hidden');
        receipt.classList.add('hidden');
        return;
    }
    
    emptyState.classList.add('hidden');
    receipt.classList.remove('hidden');
    
    let localSubtotal = 0;
    let html = '';

    cartKeys.forEach(key => {
        const item = appState.cart[key];
        // Ищем товар в кэше (в реальности, если товара нет в кэше, его нужно подтянуть)
        const product = appState.products.find(p => p.id == item.product_id) || { id: item.product_id, name: "Неизвестный товар", price: 0, image_url: "" };
        localSubtotal += product.price * item.quantity;
        
        const variantHtml = item.variant ? `<div class="text-[11px] text-app-accent mb-1 font-medium">${item.variant}</div>` : '';

        html += `
            <div class="bg-app-card rounded-2xl p-3 flex gap-3 border border-white/5 items-center">
            <div class="w-16 h-16 bg-white rounded-xl flex items-center justify-center shrink-0 p-1">
                    <img src="${product.image_url}" class="max-h-full max-w-full object-contain mix-blend-multiply" loading="lazy">
            </div>
            <div class="flex-1 min-w-0">
                <div class="font-medium text-sm truncate mb-1">${product.name}</div>
                ${variantHtml}
                    <div class="text-xs text-app-muted mb-2">Цена/шт ${formatPrice(product.price)} Br</div>
                <div class="flex justify-between items-center">
                    <div class="flex items-center gap-3 bg-app-bg px-2 py-1 rounded-lg border border-white/5">
                        <button onclick='updateCartQuantity("${key}", -1)' class="text-app-muted hover:text-white px-1 font-bold">-</button>
                        <span class="text-xs font-semibold w-5 text-center">${item.quantity}</span>
                        <button onclick='updateCartQuantity("${key}", 1)' class="text-app-muted hover:text-white px-1 font-bold">+</button>
                    </div>
                        <div class="text-sm font-bold text-app-accent">${formatPrice(product.price * item.quantity)} Br</div>
                </div>
            </div>
            <button onclick='removeFromCart("${key}")' class="shrink-0 w-10 h-10 bg-red-500/10 text-red-400 rounded-xl flex items-center justify-center hover:bg-red-500/20 transition-colors">
                <svg fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" /></svg>
            </button>
            </div>`;
    });
    
    itemsContainer.innerHTML = html;

    document.getElementById('cart-subtotal').textContent = `${formatPrice(localSubtotal)} Br`;
    document.getElementById('cart-total').textContent = `${formatPrice(localSubtotal)} Br`;
    
    // Запрашиваем валидацию с сервера асинхронно
    validateCartOnBackend();
}

async function validateCartOnBackend() {
    const items = Object.values(appState.cart).map(i => ({ product_id: i.product_id, quantity: i.quantity, variant: i.variant }));
    if (items.length === 0) return;

    try {
        const res = await apiFetch('/api/cart/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items, promo_code: appState.promoCode })
        });
        if (res.ok) {
            const data = await res.json();
            document.getElementById('cart-total').textContent = `${formatPrice(data.final_total)} Br`;
            
            const discRow = document.getElementById('cart-discount-row');
            if (data.discount_amount > 0) {
                discRow.classList.remove('hidden');
                document.getElementById('cart-discount-val').textContent = `-${formatPrice(data.discount_amount)} Br`;
                document.getElementById('cart-discount-label').textContent = data.promo_status === 'valid' ? 'Скидка (промо)' : 'Скидка';
            } else {
                discRow.classList.add('hidden');
            }
        }
    } catch (e) { console.error("Validation error", e); }
}

function updateCartBadges() {
    const totalItems = Object.values(appState.cart).reduce((sum, item) => sum + item.quantity, 0);
    const badges = [document.getElementById('badge-cart'), document.getElementById('detail-badge-cart')];
    
    badges.forEach(badge => {
        if (totalItems > 0) {
            badge.textContent = totalItems;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    });
}

// --- ЛОГИКА ПРОМОКОДОВ ---
function openPromoModal() {
    const modal = document.getElementById('promo-modal');
    const content = document.getElementById('promo-modal-content');
    modal.classList.remove('hidden');
    setTimeout(() => {
        modal.classList.remove('opacity-0');
        content.classList.remove('scale-95');
    }, 10);
}

function closePromoModal() {
    const modal = document.getElementById('promo-modal');
    const content = document.getElementById('promo-modal-content');
    modal.classList.add('opacity-0');
    content.classList.add('scale-95');
    setTimeout(() => modal.classList.add('hidden'), 200);
}

function applyPromo() {
    const val = document.getElementById('promo-input').value.trim().toUpperCase();
    if (!val) return;
    appState.promoCode = val;
    tg.HapticFeedback.impactOccurred('medium');
    closePromoModal();
    renderCart(); // Перерендерит и вызовет валидацию
}

// --- ЛОГИКА ДЕПОЗИТОВ (MOCK) ---
function openDepositModal() {
    const modal = document.getElementById('deposit-modal');
    const content = document.getElementById('deposit-modal-content');
    document.getElementById('deposit-input').value = '';
    modal.classList.remove('hidden');
    setTimeout(() => {
        modal.classList.remove('opacity-0');
        content.classList.remove('scale-95');
    }, 10);
}

function closeDepositModal() {
    const modal = document.getElementById('deposit-modal');
    const content = document.getElementById('deposit-modal-content');
    modal.classList.add('opacity-0');
    content.classList.add('scale-95');
    setTimeout(() => modal.classList.add('hidden'), 200);
}

async function submitDeposit() {
    const amount = parseFloat(document.getElementById('deposit-input').value);
    if (isNaN(amount) || amount <= 0) {
        tg.showAlert("Пожалуйста, введите корректную сумму");
        return;
    }
    
    try {
        const res = await apiFetch('/api/user/deposit-mock', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ amount })
        });
        
        if (res.ok) {
            tg.showPopup({ title: "Успех!", message: `Счет успешно пополнен на ${amount} Br`, buttons: [{text: "OK"}]});
            closeDepositModal();
            loadUserProfile(); // Легкое обновление профиля без моргания экрана!
        } else {
            tg.showAlert("Ошибка при попытке пополнения");
        }
    } catch (e) {
        tg.showAlert("Сетевая ошибка");
    }
}

// --- ОФОРМЛЕНИЕ ЗАКАЗА ---
async function checkout() {
    // Запрашиваем у пользователя адрес доставки
    const address = prompt("📍 Введите адрес доставки (или оставьте 'Самовывоз'):", "Самовывоз");
    if (address === null) return; // Пользователь нажал "Отмена"

    const btn = document.getElementById('checkout-btn');
    btn.disabled = true;
    btn.innerHTML = '<svg class="animate-spin h-5 w-5 text-white mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>';
    
    const items = Object.values(appState.cart).map(i => ({ product_id: i.product_id, quantity: i.quantity, variant: i.variant }));
    try {
        const res = await apiFetch('/api/orders/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items, promo_code: appState.promoCode, address: address.trim() || "Самовывоз" })
        });
        if (res.ok) {
            tg.showPopup({ title: "Успешно!", message: "Ваш заказ оформлен. Менеджер свяжется с вами.", buttons: [{text: "OK"}]});
            appState.cart = {};
            appState.promoCode = null;
            saveCart();
            
            await loadUserProfile(); // Легкое обновление профиля, чтобы подтянуть списанный баланс
            
            // Перекидываем пользователя на экран Профиля и сразу открываем Историю заказов
            switchTab('profile');
            fetchOrders();
        } else { tg.showAlert("Ошибка при оформлении заказа"); }
    } catch (e) { tg.showAlert("Ошибка сети"); }
    finally { btn.disabled = false; btn.textContent = "Оформить заказ"; }
}

function toggleFavorite(productId) {
    if (appState.favorites.has(productId)) {
        appState.favorites.delete(productId);
    } else {
        appState.favorites.add(productId);
    }
    
    // Сохраняем в память телефона
    localStorage.setItem('vape_favorites', JSON.stringify([...appState.favorites]));
    
    tg.HapticFeedback.impactOccurred('light');
    renderProducts(appState.products); // Перерисовываем карточки для обновления заливки сердечка
}

// Запуск
document.addEventListener('DOMContentLoaded', () => {
    renderProfileHeader(); // Моментально показываем имя из Telegram
    initializeApp(); // Авторизация и загрузка профиля
    fetchCategories();
    fetchProducts();
});