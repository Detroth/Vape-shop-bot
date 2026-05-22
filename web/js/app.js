// Инициализация Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand(); // Открываем на всю высоту
tg.ready();

// Глобальное состояние
const appState = {
    profile: null,
    products: [], 
    cart: JSON.parse(localStorage.getItem('vape_cart') || '{}'),
    favorites: new Set(), 
    currentTab: 'catalog',
    activeProduct: null,
    promoCode: null
};

// Динамическое получение данных (на случай если Telegram загрузится с задержкой)
const getInitData = () => window.Telegram.WebApp.initData || "test";

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
    
    if (tabName === 'profile') {
        loadUserProfile();
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

async function fetchProducts() {
    try {
        const response = await fetch('/api/catalog/products', {
            headers: { 'X-Telegram-Init-Data': getInitData() }
        });
        if (response.ok) {
            appState.products = await response.json();
        } else {
            appState.products = [
                { id: 1, name: "GeekVape Aegis Q 0.8 Om", price: 13, image_url: "https://placehold.co/200x200/ffffff/000000?text=Aegis", characteristics: { colors: ["Black", "Red"] }, description: "Сменный картридж для подсистемы." },
                { id: 2, name: "Vaporesso Xros 3mini", price: 60, image_url: "https://placehold.co/200x200/ffffff/000000?text=XROS+3", characteristics: { colors: ["Lemon Yellow (желтый)", "Space Grey", "Phantom Green"] }, description: "Компактная и мощная подсистема с емким аккумулятором." }
            ];
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

function handleSearch() {
    const query = document.getElementById('catalog-search').value.toLowerCase();
    const filtered = appState.products.filter(p => p.name.toLowerCase().includes(query));
    renderProducts(filtered);
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
async function loadUserProfile() {
    try {
        tg.ready(); // Синхронизация с клиентом Telegram
        const url = `/api/user/profile?t=${Date.now()}`; // Очистка кэша браузера
        const res = await fetch(url, { headers: { 'X-Telegram-Init-Data': getInitData() } });
        if(res.ok) {
            appState.profile = await res.json();
            
            const balEl = document.getElementById('profile-balance');
            if (balEl) balEl.textContent = `${appState.profile.balance} Br`;
            
            const bonEl = document.getElementById('profile-bonuses');
            if (bonEl) bonEl.textContent = `${appState.profile.bonus_points} pts`;
            
            const discEl = document.getElementById('profile-discount');
            if (discEl) discEl.textContent = `${appState.profile.personal_discount}%`;
            
            // Обновляем шапку, подтянув данные из базы
            renderProfileHeader(appState.profile);
        }
    } catch (e) { console.error("Ошибка загрузки профиля", e); }
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
        const res = await fetch('/api/cart/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Telegram-Init-Data': getInitData() },
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
        const res = await fetch('/api/orders/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Telegram-Init-Data': getInitData() },
            body: JSON.stringify({ items, promo_code: appState.promoCode, address: "Самовывоз" })
        });
        if (res.ok) {
            tg.showPopup({ title: "Успешно!", message: "Ваш заказ оформлен. Менеджер свяжется с вами.", buttons: [{text: "OK"}]});
            appState.cart = {};
            appState.promoCode = null;
            saveCart();
            loadUserProfile(); // Обновляем профиль (баланс, скидки и др.)
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
    // Перерисовываем каталог для обновления иконки сердечка
    handleSearch(); 
}

// Запуск
document.addEventListener('DOMContentLoaded', () => {
    renderProfileHeader(); // Моментально показываем имя из Telegram
    switchTab('catalog');
    fetchProducts();
    loadUserProfile(); // Сразу при входе грузим профиль
});