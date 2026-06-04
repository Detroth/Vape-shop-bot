// Инициализация Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand(); // Открываем на всю высоту
tg.ready();

// Глобальное состояние
const appState = {
    profile: null,
    products: [], 
    categories: [],
    activeCategoryId: null,
    cart: JSON.parse(localStorage.getItem('vape_cart') || '{}'),
    favorites: new Set(JSON.parse(localStorage.getItem('vape_favorites') || '[]')), 
    currentTab: 'catalog',
    activeProduct: null,
    promoCode: null
};

// Динамическое получение данных (на случай если Telegram загрузится с задержкой)
const getInitData = () => window.Telegram.WebApp.initData || "test";

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
        console.warn("⚠️ Приложение запущено вне Telegram! Используется тестовая моковая строка initData.");
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

// Моментальное обновление визуала профиля из клиента Telegram
function renderProfileHeader(dbUser = null) {
    const tgUser = window.Telegram.WebApp.initDataUnsafe?.user;
    const nameEl = document.getElementById('profile-name');
    const usernameEl = document.getElementById('profile-username');
    
    if (tgUser) {
        if (nameEl) nameEl.textContent = tgUser.first_name || tgUser.username || "Пользователь";
    } else {
        if (nameEl) nameEl.textContent = "Гость";
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
    
    if (tabName === 'profile' && window.currentUser) {
        renderProfile(window.currentUser);
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
    handleSearch(); // Запускаем поиск (уже с учетом выбранной категории)
}

async function fetchProducts(categoryId = null, search = '') {
    try {
        const params = new URLSearchParams();
        if (categoryId !== null) params.append('category_id', categoryId);
        if (search) params.append('search', search);
        
        const url = '/api/catalog/products' + (params.toString() ? `?${params.toString()}` : '');
        const response = await apiFetch(url);
        
        if (response.ok) {
            appState.products = await response.json();
        } else {
            appState.products = [];
        }
        renderProducts(appState.products);
        updateCartBadges(); // Обновляем бейджи после загрузки, т.к. корзина тянется из localStorage
    } catch (error) {
        console.error("Ошибка загрузки товаров:", error);
    }
}

function renderProducts(productsToRender) {
    const grid = document.getElementById('products-grid');
    grid.innerHTML = '';

    if (productsToRender.length === 0) {
        grid.innerHTML = '<div class="col-span-2 text-center text-app-muted mt-10">Товары не найдены</div>';
        return;
    }

    productsToRender.forEach(p => {
        const isFav = appState.favorites.has(p.id);
        
        const card = document.createElement('div');
        card.className = 'bg-app-card rounded-2xl p-2 flex flex-col relative cursor-pointer active:scale-95 transition-transform';
        card.onclick = () => showProductDetails(p.id);
        
        card.innerHTML = `
            <!-- Область картинки -->
            <div class="h-36 bg-white rounded-xl mb-3 flex items-center justify-center overflow-hidden">
                <img src="${p.image_url || ''}" class="object-contain h-full w-full" alt="Фото">
            </div>
            <!-- Название -->
            <h2 class="text-[13px] font-medium mb-3 line-clamp-2 leading-snug">${p.name}</h2>
            
            <!-- Подвал карточки -->
            <div class="mt-auto flex justify-between items-end">
                <div class="flex gap-1.5">
                    <button onclick="event.stopPropagation(); toggleFavorite(${p.id})" class="bg-app-bg w-[34px] h-[34px] rounded-[10px] flex items-center justify-center text-${isFav ? 'app-accent' : 'app-muted'} hover:text-app-accent border border-white/5">
                        <svg fill="${isFav ? 'currentColor' : 'none'}" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4"><path stroke-linecap="round" stroke-linejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" /></svg>
                    </button>
                    <button onclick="event.stopPropagation(); addToCart(${p.id})" class="bg-app-bg w-[34px] h-[34px] rounded-[10px] flex items-center justify-center text-app-muted hover:text-app-accent border border-white/5">
                        <svg fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 10.5V6a3.75 3.75 0 10-7.5 0v4.5m11.356-1.993l1.263 12c.07.665-.45 1.243-1.119 1.243H4.25a1.125 1.125 0 01-1.12-1.243l1.264-12A1.125 1.125 0 015.513 7.5h12.974c.576 0 1.059.435 1.119 1.007z" /></svg>
                    </button>
                </div>
                <span class="font-bold text-[15px] text-app-accent leading-none">${p.price} Br</span>
            </div>
        `;
        grid.appendChild(card);
    });
}

let searchTimeout;
function handleSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        const query = document.getElementById('catalog-search').value.trim();
        fetchProducts(appState.activeCategoryId, query);
    }, 300); // 300мс задержка после последнего нажатия
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

function closeProductDetails() {
    document.getElementById('tab-product-details').classList.add('hidden');
    tg.BackButton.hide();
    appState.activeProduct = null;
}

// --- ЛОГИКА ПРОФИЛЯ ---
function renderProfile(userData) {
    if (!userData) return;
    
    const balEl = document.getElementById('profile-balance');
    if (balEl) balEl.textContent = `${userData.balance} Br`;
    
    const bonEl = document.getElementById('profile-bonuses');
    if (bonEl) bonEl.textContent = `${userData.bonus_points} pts`;
    
    const discEl = document.getElementById('profile-discount');
    if (discEl) discEl.textContent = `${userData.personal_discount}%`;
    
    // Обновляем шапку, подтянув данные из базы
    renderProfileHeader(userData);
}

async function fetchOrders() {
    tg.showAlert("Загрузка истории заказов...");
}

// --- ЛОГИКА КОРЗИНЫ ---

function saveCart() {
    localStorage.setItem('vape_cart', JSON.stringify(appState.cart));
    updateCartBadges();
}

function addToCart(productId) {
    appState.cart[productId] = (appState.cart[productId] || 0) + 1;
    saveCart();
    tg.HapticFeedback.impactOccurred('light');
}

function updateCartQuantity(productId, delta) {
    if (!appState.cart[productId]) return;
    appState.cart[productId] += delta;
    if (appState.cart[productId] <= 0) delete appState.cart[productId];
    saveCart();
    tg.HapticFeedback.selectionChanged();
    renderCart();
}

function removeFromCart(productId) {
    delete appState.cart[productId];
    saveCart();
    tg.HapticFeedback.impactOccurred('medium');
    renderCart();
}

async function renderCart() {
    const itemsContainer = document.getElementById('cart-items');
    const emptyState = document.getElementById('cart-empty');
    const receipt = document.getElementById('cart-receipt');
    
    itemsContainer.innerHTML = '';
    const productIds = Object.keys(appState.cart);
    
    if (productIds.length === 0) {
        emptyState.classList.remove('hidden');
        receipt.classList.add('hidden');
        return;
    }
    
    emptyState.classList.add('hidden');
    receipt.classList.remove('hidden');
    
    let localSubtotal = 0;

    productIds.forEach(id => {
        const qty = appState.cart[id];
        // Ищем товар в кэше (в реальности, если товара нет в кэше, его нужно подтянуть)
        const product = appState.products.find(p => p.id == id) || { id, name: "Неизвестный товар", price: 0, image_url: "" };
        localSubtotal += product.price * qty;

        const itemEl = document.createElement('div');
        itemEl.className = 'bg-app-card rounded-2xl p-3 flex gap-3 border border-white/5 items-center';
        itemEl.innerHTML = `
            <div class="w-16 h-16 bg-white rounded-xl flex items-center justify-center shrink-0 p-1">
                <img src="${product.image_url}" class="max-h-full max-w-full object-contain mix-blend-multiply">
            </div>
            <div class="flex-1 min-w-0">
                <div class="font-medium text-sm truncate mb-1">${product.name}</div>
                <div class="text-xs text-app-muted mb-2">Цена/шт ${product.price} Br</div>
                <div class="flex justify-between items-center">
                    <div class="flex items-center gap-3 bg-app-bg px-2 py-1 rounded-lg border border-white/5">
                        <button onclick="updateCartQuantity(${id}, -1)" class="text-app-muted hover:text-white px-1 font-bold">-</button>
                        <span class="text-xs font-semibold w-5 text-center">${qty}</span>
                        <button onclick="updateCartQuantity(${id}, 1)" class="text-app-muted hover:text-white px-1 font-bold">+</button>
                    </div>
                    <div class="text-sm font-bold text-app-accent">${product.price * qty} Br</div>
                </div>
            </div>
            <button onclick="removeFromCart(${id})" class="shrink-0 w-10 h-10 bg-red-500/10 text-red-400 rounded-xl flex items-center justify-center hover:bg-red-500/20 transition-colors">
                <svg fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" /></svg>
            </button>
        `;
        itemsContainer.appendChild(itemEl);
    });

    document.getElementById('cart-subtotal').textContent = `${localSubtotal} Br`;
    document.getElementById('cart-total').textContent = `${localSubtotal} Br`;
    
    // Запрашиваем валидацию с сервера асинхронно
    validateCartOnBackend();
}

async function validateCartOnBackend() {
    const items = Object.entries(appState.cart).map(([id, qty]) => ({ product_id: parseInt(id), quantity: qty }));
    if (items.length === 0) return;

    try {
        const res = await apiFetch('/api/cart/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items, promo_code: appState.promoCode })
        });
        if (res.ok) {
            const data = await res.json();
            document.getElementById('cart-total').textContent = `${data.final_total} Br`;
            
            const discRow = document.getElementById('cart-discount-row');
            if (data.discount_amount > 0) {
                discRow.classList.remove('hidden');
                document.getElementById('cart-discount-val').textContent = `-${data.discount_amount} Br`;
                document.getElementById('cart-discount-label').textContent = data.promo_status === 'valid' ? 'Скидка (промо)' : 'Скидка';
            } else {
                discRow.classList.add('hidden');
            }
        }
    } catch (e) { console.error("Validation error", e); }
}

function updateCartBadges() {
    const totalItems = Object.values(appState.cart).reduce((a, b) => a + b, 0);
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

// --- ОФОРМЛЕНИЕ ЗАКАЗА ---
async function checkout() {
    const btn = document.getElementById('checkout-btn');
    btn.disabled = true;
    btn.innerHTML = '<svg class="animate-spin h-5 w-5 text-white mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>';
    
    const items = Object.entries(appState.cart).map(([id, qty]) => ({ product_id: parseInt(id), quantity: qty }));
    try {
        const res = await apiFetch('/api/orders/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items, promo_code: appState.promoCode, address: "Самовывоз" })
        });
        if (res.ok) {
            tg.showPopup({ title: "Успешно!", message: "Ваш заказ оформлен. Менеджер свяжется с вами.", buttons: [{text: "OK"}]});
            appState.cart = {};
            appState.promoCode = null;
            saveCart();
            // Заново логинимся/обновляемся, чтобы подтянуть с бэка списанный баланс/бонусы
            initializeApp(); 
            switchTab('catalog');
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