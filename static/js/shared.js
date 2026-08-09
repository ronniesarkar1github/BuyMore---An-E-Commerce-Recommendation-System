(function () {
  var cartCache = [];
  var isLoggedIn = false;
  var currentUserName = "";

  function getStoredUser() {
    if (localStorage.getItem("isLoggedIn") === "true") {
      var name = localStorage.getItem("userName") || "User";
      var email = localStorage.getItem("userEmail") || "";
      return { user: { name: name, email: email } };
    }
    return null;
  }

function checkLoginStatus() {
    return fetch("/api/check_session", { credentials: "include" })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        isLoggedIn = data.logged_in || false;
        if (!isLoggedIn) {
          // Server session expired — clear stale localStorage
          localStorage.removeItem("isLoggedIn");
          localStorage.removeItem("userName");
          localStorage.removeItem("userEmail");
        } else {
          // Keep localStorage in sync with server session
          localStorage.setItem("isLoggedIn", "true");
          if (data.user) {
            localStorage.setItem("userName", data.user.name || "");
            localStorage.setItem("userEmail", data.user.email || "");
          }
        }
        toggleAuthUI(isLoggedIn, data);
        return isLoggedIn;
      })
      .catch(function() {
        // Network error — trust localStorage as fallback
        var stored = getStoredUser();
        if (stored) {
          isLoggedIn = true;
          toggleAuthUI(true, stored);
          return true;
        }
        isLoggedIn = false;
        toggleAuthUI(false, null);
        return false;
      });
  }

  function toggleAuthUI(loggedIn, userData) {
    // Toggle auth UI elements
    var guestElements = document.querySelectorAll(".auth-guest");
    var loggedElements = document.querySelectorAll(".auth-logged");

    // Find wishlist & cart buttons by their badge attributes
    var wishlistBtns = document.querySelectorAll(".top-actions [data-wishlist-count]");
    var cartBtns = document.querySelectorAll(".top-actions [data-cart-count]");
    
    if (loggedIn && userData && userData.user) {
      currentUserName = userData.user.name || "";
      // Hide guest, show logged
      guestElements.forEach(function(el) { el.style.display = "none"; });
      loggedElements.forEach(function(el) { el.style.display = "block"; });

      // Show wishlist & cart buttons
      wishlistBtns.forEach(function(span) {
        if (span.closest(".icon-btn")) span.closest(".icon-btn").style.removeProperty("display");
      });
      cartBtns.forEach(function(span) {
        if (span.closest(".icon-btn")) span.closest(".icon-btn").style.removeProperty("display");
      });
      
      // Update user info
      var userNameDisplay = document.getElementById("userNameDisplay");
      var userEmailDisplay = document.getElementById("userEmailDisplay");
      var userAvatarLetter = document.getElementById("userAvatarLetter");
      
      if (userNameDisplay) userNameDisplay.textContent = userData.user.name;
      if (userEmailDisplay) userEmailDisplay.textContent = userData.user.email;
      if (userAvatarLetter) {
        userAvatarLetter.textContent = userData.user.name.charAt(0).toUpperCase();
      }
      
      // Bind user menu interactions
      var userAvatarBtn = document.getElementById("userAvatarBtn");
      var userDropdown = document.getElementById("userDropdown");
      var logoutBtn = document.getElementById("logoutBtn");
      
      if (userAvatarBtn && userDropdown && !userAvatarBtn.dataset.bound) {
        userAvatarBtn.dataset.bound = "true";
        userAvatarBtn.addEventListener("click", function(e) {
          e.stopPropagation();
          userDropdown.classList.toggle("show");
        });
        
        document.addEventListener("click", function() {
          userDropdown.classList.remove("show");
        });
        
        userDropdown.addEventListener("click", function(e) {
          e.stopPropagation();
        });
        
        if (logoutBtn) {
          logoutBtn.addEventListener("click", function() {
            fetch("/api/logout", {
              method: "POST",
              credentials: "include"
            })
            .then(function(res) { return res.json(); })
            .then(function(data) {
              localStorage.removeItem("isLoggedIn");
              localStorage.removeItem("userName");
              localStorage.removeItem("userEmail");
              window.location.reload();
            })
            .catch(function() {
              localStorage.removeItem("isLoggedIn");
              localStorage.removeItem("userName");
              localStorage.removeItem("userEmail");
              window.location.href = "/";
            });
          });
        }
      }
    } else {
      currentUserName = "";
      // Show guest, hide logged
      guestElements.forEach(function(el) { el.style.removeProperty("display"); });
      loggedElements.forEach(function(el) { el.style.display = "none"; });

      // Hide wishlist & cart buttons
      wishlistBtns.forEach(function(span) {
        if (span.closest(".icon-btn")) span.closest(".icon-btn").style.display = "none";
      });
      cartBtns.forEach(function(span) {
        if (span.closest(".icon-btn")) span.closest(".icon-btn").style.display = "none";
      });
    }
  }

  function getCart() {
    if (isLoggedIn) {
      return cartCache;
    }
    return JSON.parse(localStorage.getItem("cartItems")) || [];
  }

  function setCart(items) {
    if (isLoggedIn) {
      cartCache = items;
    } else {
      localStorage.setItem("cartItems", JSON.stringify(items));
    }
  }

  function fetchCartFromServer() {
    return fetch("/api/cart", { credentials: "include" })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success && data.items) {
          cartCache = data.items;
          updateCartBadges();
          refreshProductAvailability();
          return data.items;
        }
        refreshProductAvailability();
        return [];
      })
      .catch(function() {
        refreshProductAvailability();
        return [];
      });
  }

  function updateCartBadges() {
    var count = 0;
    if (isLoggedIn) {
      count = cartCache.length;
    } else {
      // When not logged in, show 0 (don't use localStorage for display)
      count = 0;
    }
    document.querySelectorAll("[data-cart-count]").forEach(function (el) {
      el.textContent = count;
    });
  }

  function updateWishlistBadges() {
    if (!isLoggedIn) {
      document.querySelectorAll("[data-wishlist-count]").forEach(function (el) {
        el.textContent = "0";
      });
      return;
    }
    fetch("/api/wishlist", { credentials: "include" })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success && data.items) {
          document.querySelectorAll("[data-wishlist-count]").forEach(function (el) {
            el.textContent = data.items.length;
          });
        }
      })
      .catch(function() {});
  }

  function showToast(msg) {
    var toast = document.getElementById("toast");
    if (!toast) {
      return;
    }
    toast.textContent = msg;
    toast.classList.add("show");
    setTimeout(function () {
      toast.classList.remove("show");
    }, 2200);
  }

  function ensurePopup() {
    var root = document.getElementById("shopPopup");
    if (root) {
      return root;
    }

    root = document.createElement("div");
    root.id = "shopPopup";
    root.className = "popup-backdrop";
    root.innerHTML =
      '<div class="popup-card" role="dialog" aria-modal="true">' +
        '<div class="popup-icon" id="popupIcon">i</div>' +
        '<h3 id="popupTitle">Notice</h3>' +
        '<p id="popupMessage"></p>' +
        '<div class="popup-actions">' +
          '<button id="popupSecondary" class="secondary-btn hidden" type="button">Cancel</button>' +
          '<button id="popupPrimary" class="primary-btn" type="button">OK</button>' +
        '</div>' +
      '</div>';

    document.body.appendChild(root);
    return root;
  }

  function showPopup(options) {
    var config = options || {};
    var root = ensurePopup();
    var card = root.querySelector(".popup-card");
    var icon = document.getElementById("popupIcon");
    var title = document.getElementById("popupTitle");
    var message = document.getElementById("popupMessage");
    var primary = document.getElementById("popupPrimary");
    var secondary = document.getElementById("popupSecondary");

    var type = config.type || "info";
    card.classList.remove("popup-info", "popup-success", "popup-error", "popup-warn");
    card.classList.add("popup-" + type);

    if (type === "success") {
      icon.textContent = "OK";
    } else if (type === "error") {
      icon.textContent = "X";
    } else if (type === "warn") {
      icon.textContent = "!";
    } else {
      icon.textContent = "i";
    }

    title.textContent = config.title || "Notice";
    message.textContent = config.message || "";

    primary.textContent = config.primaryText || "OK";
    primary.onclick = function () {
      root.classList.remove("show");
      if (typeof config.onPrimary === "function") {
        config.onPrimary();
      }
    };

    if (config.secondaryText) {
      secondary.classList.remove("hidden");
      secondary.textContent = config.secondaryText;
      secondary.onclick = function () {
        root.classList.remove("show");
        if (typeof config.onSecondary === "function") {
          config.onSecondary();
        }
      };
    } else {
      secondary.classList.add("hidden");
      secondary.onclick = null;
    }

    root.onclick = function (event) {
      if (event.target === root) {
        root.classList.remove("show");
      }
    };

    root.classList.add("show");
  }

  var sentimentCache = {};

  function normalizeSentimentLabel(label) {
    if (!label) return "unknown";
    var raw = String(label).toLowerCase();
    if (raw.indexOf("pos") !== -1 || raw.indexOf("label_2") !== -1 || raw.indexOf("5") !== -1 || raw.indexOf("4") !== -1) {
      return "positive";
    }
    if (raw.indexOf("neg") !== -1 || raw.indexOf("label_0") !== -1) {
      return "negative";
    }
    if (raw.indexOf("neu") !== -1 || raw.indexOf("label_1") !== -1 || raw.indexOf("3") !== -1) {
      return "neutral";
    }
    return "unknown";
  }

  function createSentimentBadge(payload) {
    var badge = document.createElement("span");
    badge.className = "sentiment-badge";
    if (!payload || !payload.label) {
      badge.classList.add("sentiment-unknown");
      badge.textContent = "Unknown";
      return badge;
    }
    var normalized = normalizeSentimentLabel(payload.label);
    badge.classList.add("sentiment-" + normalized);
    badge.textContent = normalized.charAt(0).toUpperCase() + normalized.slice(1);
    return badge;
  }

  function analyzeSentiment(text) {
    if (!text) {
      return Promise.resolve(null);
    }
    if (sentimentCache[text]) {
      return Promise.resolve(sentimentCache[text]);
    }
    return fetch("/api/sentiment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ text: text })
    })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data && data.success) {
          var payload = { label: data.label, score: data.score };
          sentimentCache[text] = payload;
          return payload;
        }
        return null;
      })
      .catch(function() { return null; });
  }

  function isProductOutOfStock(name) {
    var card = document.querySelector('[data-product-card][data-name="' + name + '"]');
    if (card && card.dataset.stock !== undefined) {
      return getRemainingStock(name, Number(card.dataset.stock)) <= 0;
    }
    return false;
  }

  function getCartQuantity(name) {
    return getCart().reduce(function(total, item) {
      if (item && item.name === name) {
        return total + Number(item.quantity || 0);
      }
      return total;
    }, 0);
  }

  function getRemainingStock(name, stock) {
    if (stock === undefined || stock === null || Number(stock) < 0) {
      return Infinity;
    }
    return Number(stock) - getCartQuantity(name);
  }

  function refreshProductAvailability() {
    document.querySelectorAll("[data-product-card]").forEach(function(card) {
      var name = card.dataset.name || "";
      var stock = Number(card.dataset.stock);
      var isTracked = !Number.isNaN(stock) && stock >= 0;
      var remaining = getRemainingStock(name, stock);
      var soldOut = isTracked && remaining <= 0;
      var imageWrap = card.querySelector(".product-image");
      var badge = imageWrap ? imageWrap.querySelector(".out-of-stock-badge") : null;
      var button = card.querySelector("[data-add-cart]");

      card.classList.toggle("out-of-stock", soldOut);

      if (imageWrap) {
        if (soldOut && !badge) {
          badge = document.createElement("span");
          badge.className = "out-of-stock-badge";
          badge.textContent = "Out of Stock";
          imageWrap.insertBefore(badge, imageWrap.firstChild);
        } else if (!soldOut && badge) {
          badge.remove();
        }
      }

      if (button) {
        button.disabled = soldOut;
        button.textContent = soldOut ? "Out of Stock" : "Add to Cart";
      }
    });
  }

  function showOutOfStockPopup(name, customMessage) {
    showPopup({
      type: "error",
      title: "Out of Stock",
      message: customMessage || ('"' + name + '" is currently out of stock. Please check back later or browse similar products.'),
      primaryText: "OK"
    });
  }

  function addToCart(name, price, image) {
    if (isLoggedIn) {
      fetch("/api/cart/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ 
          product: { name: name, price: price, image: image },
          quantity: 1
        })
      })
        .then(function(res) { return res.json().then(function(data) { return { ok: res.ok, data: data }; }); })
        .then(function(result) {
          if (result.data.success) {
            fetchCartFromServer();
            document.dispatchEvent(new Event("shoppingActivityChanged"));
            showToast(name + " added to cart");
          } else if (result.data.out_of_stock) {
            showOutOfStockPopup(name, result.data.message);
          } else {
            showToast(result.data.message || "Failed to add to cart");
          }
        })
        .catch(function() {
          showToast("Error adding to cart");
        });
    } else {
      showPopup({
        type: "warn",
        title: "Sign In Required",
        message: "Please sign in to add items to your cart.",
        primaryText: "Sign In",
        onPrimary: function() { window.location.href = "/signin"; }
      });
    }
  }

  function addToWishlist(name, price, image) {
    if (isLoggedIn) {
      fetch("/api/wishlist/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ 
          product: { name: name, price: price, image: image }
        })
      })
        .then(function(res) { return res.json(); })
        .then(function(data) {
          if (data.success) {
            updateWishlistBadges();
            document.dispatchEvent(new Event("shoppingActivityChanged"));
            showToast(name + " added to wishlist");
          } else {
            showToast(data.message || "Failed to add to wishlist");
          }
        })
        .catch(function() {
          showToast("Error adding to wishlist");
        });
    } else {
      showPopup({
        type: "warn",
        title: "Sign In Required",
        message: "Please sign in to save items to your wishlist.",
        primaryText: "Sign In",
        onPrimary: function() { window.location.href = "/signin"; }
      });
    }
  }

  function removeFromWishlist(name) {
    if (isLoggedIn) {
      fetch("/api/wishlist/remove", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ productName: name })
      })
        .then(function(res) { return res.json(); })
        .then(function(data) {
          if (data.success) {
            updateWishlistBadges();
            showToast("Removed from wishlist");
            document.dispatchEvent(new Event("wishlistUpdated"));
            document.dispatchEvent(new Event("shoppingActivityChanged"));
          }
        })
        .catch(function() {
          showToast("Error removing from wishlist");
        });
    }
  }

  function fetchProductReviews(productName) {
    return fetch("/api/reviews?product=" + encodeURIComponent(productName), { credentials: "include" })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data && data.success && Array.isArray(data.reviews)) {
          return data.reviews;
        }
        return [];
      })
      .catch(function() {
        return [];
      });
  }

  function renderStars(rating) {
    var rounded = Math.round(Number(rating || 0));
    var full = "★★★★★".slice(0, rounded);
    var empty = "☆☆☆☆☆".slice(0, 5 - rounded);
    return full + empty;
  }

  function hasZeroReviews(product) {
    return !product || product.review_count === undefined || product.review_count === null || Number(product.review_count) === 0;
  }

  function formatRatingText(rating, product) {
    if (hasZeroReviews(product) || Number(rating || 0) === 0) {
      return "0 stars";
    }
    return Number(rating).toFixed(1) + " stars";
  }

  function buildProductCardMarkup(product) {
    if (!product) {
      return "";
    }
    var safeName = String(product.name || "Product");
    var safeCategory = String(product.category || "general");
    var safePrice = Number(product.price || 0);
    var safeRating = 0.0;
    if (hasZeroReviews(product)) {
      safeRating = 0.0;
    } else if (product && product.rating !== undefined && product.rating !== null) {
      safeRating = Number(product.rating);
    } else {
      safeRating = 0.0;
    }
    var safeImage = String(product.image || "");
    var safeStock = (product.stock !== undefined && product.stock !== null) ? Number(product.stock) : -1;
    var isOOS = safeStock === 0;
    var oosClass = isOOS ? ' out-of-stock' : '';
    var oosBadge = isOOS ? '<span class="out-of-stock-badge">Out of Stock</span>' : '';

    return (
      '<article class="product-card' + oosClass + '" data-product-card data-name="' + safeName + '" data-price="' + safePrice + '" data-category="' + safeCategory + '" data-rating="' + safeRating + '" data-stock="' + safeStock + '">' +
        '<div class="product-image">' +
          oosBadge +
          '<img src="' + safeImage + '" alt="' + safeName + '">' +
        '</div>' +
        '<strong>' + safeName + '</strong>' +
        '<div class="product-meta">' +
          '<span class="price">INR ' + safePrice.toLocaleString() + '</span>' +
          '<span class="muted">' + formatRatingText(safeRating, product) + '</span>' +
        '</div>' +
        '<div class="controls">' +
          '<button class="primary-btn" data-add-cart data-name="' + safeName + '" data-price="' + safePrice + '" data-image="' + safeImage + '">Add to Cart</button>' +
          '<button class="secondary-btn" data-add-wishlist data-name="' + safeName + '" data-price="' + safePrice + '" data-image="' + safeImage + '">Save</button>' +
        '</div>' +
      '</article>'
    );
  }

  function fetchRecommendations(options) {
    var config = options || {};
    var params = [];
    if (config.productName) {
      params.push("product_name=" + encodeURIComponent(config.productName));
    }
    if (config.limit) {
      params.push("limit=" + encodeURIComponent(config.limit));
    }
    var url = "/api/recommendations";
    if (params.length) {
      url += "?" + params.join("&");
    }
    return fetch(url, { credentials: "include" })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data && data.success) {
          var primary = Array.isArray(data.recommendations) ? data.recommendations : [];
          var fbt = Array.isArray(data.frequently_bought_together) ? data.frequently_bought_together : [];
          var seen = {};
          return primary.concat(fbt).filter(function(entry) {
            var product = entry && entry.product ? entry.product : null;
            var name = product && product.name ? product.name : "";
            if (!name || seen[name]) {
              return false;
            }
            seen[name] = true;
            return true;
          });
        }
        return [];
      })
      .catch(function() {
        return [];
      });
  }

  function trackProductClick(productName, source) {
    if (!productName || !isLoggedIn) {
      return Promise.resolve(false);
    }
    return fetch("/api/interactions/click", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        productName: productName,
        source: source || "product_modal"
      })
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        return !!(data && data.success && data.tracked);
      })
      .catch(function () {
        return false;
      });
  }

  function trackProductView(productName, source) {
    if (!productName || !isLoggedIn) {
      return Promise.resolve(false);
    }
    return fetch("/api/interactions/view", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        productName: productName,
        source: source || "product_view"
      })
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        return !!(data && data.success && data.tracked);
      })
      .catch(function () {
        return false;
      });
  }

  function goToSearch(query) {
    var value = String(query || "").trim();
    var url = "/search";
    if (value) {
      url += "?q=" + encodeURIComponent(value);
    }
    window.location.href = url;
  }

  function bindExistingSearchBoxes() {
    document.querySelectorAll("#searchBox").forEach(function(input) {
      if (input.dataset.globalSearchBound === "true") {
        return;
      }
      input.dataset.globalSearchBound = "true";
      input.setAttribute("title", "Press Enter to search the full catalog");
      input.addEventListener("keydown", function(event) {
        if (event.key === "Enter") {
          event.preventDefault();
          goToSearch(input.value);
        }
      });
    });
  }

  function injectNavbarSearch() {
    if (document.querySelector(".nav-search-form")) {
      return;
    }
    if (document.querySelector("#searchBox")) {
      bindExistingSearchBoxes();
      return;
    }

    var topbar = document.querySelector(".topbar");
    if (!topbar) {
      return;
    }

    var host = topbar.querySelector(".top-actions") || topbar;
    var searchForm = document.createElement("form");
    searchForm.className = "nav-search-form";
    searchForm.innerHTML =
      '<input class="nav-search-input" type="search" placeholder="Search products">' +
      '<button class="nav-search-btn" type="submit" aria-label="Search products"><i class="fa-solid fa-magnifying-glass"></i></button>';

    searchForm.addEventListener("submit", function(event) {
      event.preventDefault();
      var input = searchForm.querySelector("input");
      goToSearch(input ? input.value : "");
    });

    if (window.location.pathname === "/search") {
      var params = new URLSearchParams(window.location.search);
      var q = params.get("q") || "";
      var navInput = searchForm.querySelector("input");
      if (navInput) {
        navInput.value = q;
      }
    }

    if (host.classList.contains("top-actions")) {
      host.insertBefore(searchForm, host.firstChild);
    } else {
      var brand = topbar.querySelector(".brand");
      if (brand && brand.nextSibling) {
        topbar.insertBefore(searchForm, brand.nextSibling);
      } else {
        topbar.appendChild(searchForm);
      }
    }
  }

  function renderRecommendationSection(container, recommendations, emptyMessage) {
    if (!container) {
      return;
    }
    if (!Array.isArray(recommendations) || !recommendations.length) {
      container.innerHTML = '<div class="surface empty">' + (emptyMessage || "No recommendations available right now.") + '</div>';
      return;
    }

    function escapeHtml(value) {
      return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }

    function buildTagBadgesMarkup(tags) {
      if (!Array.isArray(tags) || !tags.length) {
        return "";
      }
      var safe = tags
        .map(function(t) { return String(t || "").trim(); })
        .filter(Boolean)
        .slice(0, 5);
      if (!safe.length) {
        return "";
      }
      return '<div class="tag-badges">' + safe.map(function(t) {
        return '<span class="tag-badge">' + escapeHtml(t) + '</span>';
      }).join("") + '</div>';
    }

    container.innerHTML = recommendations.map(function(entry) {
      var product = entry && entry.product ? entry.product : null;
      if (!product) {
        return "";
      }
      var tags = buildTagBadgesMarkup(entry.matched_tags);
      var reason = (!tags && entry.reason) ? '<p class="recommendation-reason">' + escapeHtml(entry.reason) + '</p>' : "";
      return '<div class="recommendation-item">' + buildProductCardMarkup(product) + tags + reason + '</div>';
    }).join("");

    bindAddToCartButtons();
    bindAddToWishlistButtons();
    bindProductCards();
  }

  function ensureProductModal() {
    var root = document.getElementById("productModal");
    if (root) {
      return root;
    }

    root = document.createElement("div");
    root.id = "productModal";
    root.className = "product-modal-backdrop";
    root.innerHTML =
      '<div class="product-modal-card" role="dialog" aria-modal="true">' +
        '<button class="product-modal-close" id="productModalClose" type="button">&times;</button>' +
        '<div class="product-modal-media"><img id="modalProductImage" src="" alt="Product"></div>' +
        '<div class="product-modal-body">' +
          '<h2 id="modalProductName"></h2>' +
          '<p id="modalProductMeta" class="muted"></p>' +
          '<p id="modalProductDesc"></p>' +
          '<div class="modal-review-head">' +
            '<h3>User Reviews</h3>' +
            '<p id="modalRatingSummary"></p>' +
          '</div>' +
          '<div id="modalReviewList" class="review-list"></div>' +
          '<section class="recommendation-panel">' +
            '<div class="recommendation-head">' +
              '<h3>You May Also Like</h3>' +
              '<p id="modalRecommendationHint" class="muted">Loading recommendations...</p>' +
            '</div>' +
            '<div id="modalRecommendationList" class="recommendation-grid compact"></div>' +
          '</section>' +
          '<form id="modalReviewForm" class="review-form">' +
            '<h4 class="mt-0">Give Review</h4>' +
            '<div class="field-grid">' +
              '<div class="field">' +
                '<label for="reviewUser">Name</label>' +
                '<input id="reviewUser" class="input" type="text" placeholder="Your name" required>' +
              '</div>' +
              '<div class="field">' +
                '<label for="reviewRating">Rating</label>' +
                '<select id="reviewRating" class="input" required>' +
                  '<option value="5">5 - Excellent</option>' +
                  '<option value="4">4 - Very Good</option>' +
                  '<option value="3">3 - Good</option>' +
                  '<option value="2">2 - Fair</option>' +
                  '<option value="1">1 - Poor</option>' +
                '</select>' +
              '</div>' +
            '</div>' +
            '<div class="field">' +
              '<label for="reviewComment">Review</label>' +
              '<textarea id="reviewComment" class="input" rows="3" placeholder="Share your experience" required></textarea>' +
            '</div>' +
            '<button class="primary-btn" type="submit">Submit Review</button>' +
          '</form>' +
        '</div>' +
      '</div>';

    document.body.appendChild(root);

    root.addEventListener("click", function (event) {
      if (event.target === root) {
        root.classList.remove("show");
      }
    });

    document.getElementById("productModalClose").addEventListener("click", function () {
      root.classList.remove("show");
    });

    return root;
  }

  function renderReviewList(productName) {
    var summary = document.getElementById("modalRatingSummary");
    var list = document.getElementById("modalReviewList");
    summary.textContent = "Loading reviews...";
    list.innerHTML = "";

    fetchProductReviews(productName).then(function (reviews) {
      var safeReviews = Array.isArray(reviews) ? reviews : [];
      var total = safeReviews.reduce(function (sum, item) { return sum + Number(item.rating || 0); }, 0);
      var overall = safeReviews.length ? (total / safeReviews.length) : 0;
      summary.textContent = safeReviews.length ? renderStars(overall) + "  " + overall.toFixed(1) + "/5 (" + safeReviews.length + " reviews)" : "0 stars (0 reviews)";
      list.innerHTML = "";

      safeReviews.slice(0, 6).forEach(function (review) {
        var item = document.createElement("article");
        item.className = "review-item";
        var head = document.createElement("div");
        head.className = "review-item-head";
        var name = document.createElement("strong");
        name.textContent = review.user_name || review.user || "User";
        var rating = document.createElement("span");
        rating.className = "review-stars";
        rating.textContent = renderStars(review.rating) + " " + Number(review.rating).toFixed(1);
        head.appendChild(name);
        head.appendChild(rating);
        var comment = document.createElement("p");
        comment.textContent = review.comment;
        var sentimentWrap = document.createElement("div");
        sentimentWrap.className = "review-sentiment";
        if (review.sentiment && review.sentiment.label) {
          sentimentWrap.appendChild(createSentimentBadge(review.sentiment));
        } else {
          var pending = document.createElement("span");
          pending.className = "muted";
          pending.textContent = "Analyzing sentiment...";
          sentimentWrap.appendChild(pending);
          analyzeSentiment(review.comment).then(function(payload) {
            sentimentWrap.innerHTML = "";
            if (!payload) {
              var unknown = document.createElement("span");
              unknown.className = "muted";
              unknown.textContent = "Sentiment unavailable";
              sentimentWrap.appendChild(unknown);
              return;
            }
            sentimentWrap.appendChild(createSentimentBadge(payload));
          });
        }
        item.appendChild(head);
        item.appendChild(comment);
        item.appendChild(sentimentWrap);
        list.appendChild(item);
      });
    });
  }

  function openProductModal(card) {
    var root = ensureProductModal();
    var name = card.dataset.name || "Product";
    var imageEl = card.querySelector(".product-image img");
    var image = imageEl ? imageEl.getAttribute("src") : "";
    var priceAttr = card.dataset.price || (card.querySelector("[data-add-cart]") && card.querySelector("[data-add-cart]").dataset.price) || "0";
    var price = Number(priceAttr || 0);
    var category = card.dataset.category || (card.querySelector(".product-meta .muted") ? card.querySelector(".product-meta .muted").textContent.trim() : "Featured");
    document.getElementById("modalProductImage").setAttribute("src", image);
    document.getElementById("modalProductImage").setAttribute("alt", name);
    document.getElementById("modalProductName").textContent = name;
    document.getElementById("modalProductMeta").textContent = category + " | INR " + price.toLocaleString();
    document.getElementById("modalProductDesc").textContent = "Designed for everyday reliability with business-grade quality, verified sellers, and secure delivery support.";

    renderReviewList(name);
    trackProductView(name, "product_modal_view");
    var modalRecommendationHint = document.getElementById("modalRecommendationHint");
    var modalRecommendationList = document.getElementById("modalRecommendationList");
    if (modalRecommendationHint) {
      modalRecommendationHint.textContent = "Finding similar products...";
    }
    if (modalRecommendationList) {
      modalRecommendationList.innerHTML = "";
    }
    fetchRecommendations({ productName: name, limit: 4 }).then(function(recommendations) {
      if (modalRecommendationHint) {
        modalRecommendationHint.textContent = recommendations.length ? "Similar products based on item details and shopper behavior" : "No similar products found yet";
      }
      renderRecommendationSection(modalRecommendationList, recommendations, "No similar products available right now.");
    });

    var form = document.getElementById("modalReviewForm");
    form.reset();
    var userInput = document.getElementById("reviewUser");
    if (userInput) {
      if (isLoggedIn && currentUserName) {
        userInput.value = currentUserName;
        userInput.readOnly = true;
        userInput.classList.add("input-locked");
      } else {
        userInput.value = "";
        userInput.readOnly = false;
        userInput.classList.remove("input-locked");
      }
    }
    form.onsubmit = function (event) {
      event.preventDefault();
      if (!isLoggedIn) {
        showPopup({
          type: "warn",
          title: "Sign In Required",
          message: "Please sign in to submit a review.",
          primaryText: "Sign In",
          onPrimary: function() { window.location.href = "/signin?next=" + encodeURIComponent(window.location.pathname); }
        });
        return;
      }
      var user = document.getElementById("reviewUser").value.trim();
      var rating = Number(document.getElementById("reviewRating").value);
      var comment = document.getElementById("reviewComment").value.trim();
      if (!user || !comment) {
        showPopup({
          type: "warn",
          title: "Review Incomplete",
          message: "Please enter your name and review text."
        });
        return;
      }
      fetch("/api/reviews", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          product_name: name,
          user_name: user,
          rating: rating,
          comment: comment
        })
      })
        .then(function(res) { return res.json(); })
        .then(function(data) {
          if (data && data.success) {
            renderReviewList(name);
            form.reset();
            showToast("Review submitted");
          } else {
            showPopup({
              type: "error",
              title: "Review Failed",
              message: (data && data.message) ? data.message : "Unable to submit review."
            });
          }
        })
        .catch(function() {
          showPopup({
            type: "error",
            title: "Review Failed",
            message: "Network error while submitting review."
          });
        });
    };

    root.classList.add("show");
  }

  function bindProductCards() {
    document.querySelectorAll("[data-product-card]").forEach(function (card) {
      if (card.dataset.modalBound === "true") {
        return;
      }
      card.dataset.modalBound = "true";
      card.setAttribute("tabindex", "0");
      card.classList.add("clickable-card");

      card.addEventListener("click", function (event) {
        if (event.target.closest("button, a, input, select, textarea, label, .controls")) {
          return;
        }
        trackProductClick(card.dataset.name || "", "product_card_click");
        openProductModal(card);
      });

      card.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          trackProductClick(card.dataset.name || "", "product_card_click");
          openProductModal(card);
        }
      });
    });
  }

  function bindAddToCartButtons() {
    document.querySelectorAll("[data-add-cart]").forEach(function (btn) {
      if (btn.dataset.cartBound === "true") {
        return;
      }
      btn.dataset.cartBound = "true";
      btn.addEventListener("click", function (event) {
        event.stopPropagation();
        addToCart(btn.dataset.name, Number(btn.dataset.price), btn.dataset.image || "");
      });
    });
    refreshProductAvailability();
  }

  function bindAddToWishlistButtons() {
    document.querySelectorAll("[data-add-wishlist]").forEach(function (btn) {
      if (btn.dataset.wishlistBound === "true") {
        return;
      }
      btn.dataset.wishlistBound = "true";
      btn.addEventListener("click", function (event) {
        event.stopPropagation();
        addToWishlist(btn.dataset.name, Number(btn.dataset.price), btn.dataset.image || "");
      });
    });
  }

  function syncProductRatings() {
    var cards = document.querySelectorAll("[data-product-card]");
    if (!cards.length) {
      return;
    }
    fetch("/api/products", { credentials: "include" })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (!data || !data.success || !Array.isArray(data.products)) {
          return;
        }
        var map = {};
        data.products.forEach(function(p) {
          if (p && p.name) {
            map[p.name] = p;
          }
        });
        cards.forEach(function(card) {
          var name = card.dataset.name;
          var product = map[name];
          if (!product) {
            return;
          }
          var rating = 0;
          if (hasZeroReviews(product)) {
            rating = 0;
          } else if (product && product.rating !== undefined && product.rating !== null) {
            rating = Number(product.rating);
          } else if (card.dataset.rating) {
            rating = Number(card.dataset.rating);
          } else {
            rating = 0;
          }
          card.dataset.rating = String(rating);
          var muted = card.querySelector(".product-meta .muted");
          if (muted) {
            muted.textContent = formatRatingText(rating, product);
          }
        });
      })
      .catch(function() {});
  }

  window.shopShared = {
    getCart: getCart,
    setCart: setCart,
    fetchCartFromServer: fetchCartFromServer,
    updateCartBadges: updateCartBadges,
    updateWishlistBadges: updateWishlistBadges,
    showToast: showToast,
    showPopup: showPopup,
    addToCart: addToCart,
    addToWishlist: addToWishlist,
    removeFromWishlist: removeFromWishlist,
    bindAddToCartButtons: bindAddToCartButtons,
    bindAddToWishlistButtons: bindAddToWishlistButtons,
    bindProductCards: bindProductCards,
    bindNavbarCartWishlistLinks: bindNavbarCartWishlistLinks,
    bindNavDropdowns: bindNavDropdowns,
    isLoggedIn: function() { return isLoggedIn; },
    buildProductCardMarkup: buildProductCardMarkup,
    fetchRecommendations: fetchRecommendations,
    renderRecommendationSection: renderRecommendationSection,
    refreshProductAvailability: refreshProductAvailability,
    goToSearch: goToSearch,
    trackProductClick: trackProductClick,
    trackProductView: trackProductView
  };

  // Bind cart/wishlist/account navbar links to redirect to login when not logged in
  function bindNavbarCartWishlistLinks() {
    // Cart links
    document.querySelectorAll('a[href*="addtocart"]').forEach(function(link) {
      if (link.dataset.navBound === "true") return;
      link.dataset.navBound = "true";
      
      link.addEventListener("click", function(e) {
        if (link.hostname === window.location.hostname) {
          if (!isLoggedIn) {
            e.preventDefault();
            var targetUrl = link.getAttribute("href");
            window.location.href = "/signin?next=" + encodeURIComponent(targetUrl);
          }
        }
      });
    });
    
    // Wishlist links
    document.querySelectorAll('a[href*="wishlist"]').forEach(function(link) {
      if (link.dataset.navBound === "true") return;
      link.dataset.navBound = "true";
      
      link.addEventListener("click", function(e) {
        if (link.hostname === window.location.hostname) {
          if (!isLoggedIn) {
            e.preventDefault();
            var targetUrl = link.getAttribute("href");
            window.location.href = "/signin?next=" + encodeURIComponent(targetUrl);
          }
        }
      });
    });
    
    // Account links (only for sidebar, not top nav when logged in)
    document.querySelectorAll('.sidebar a[href*="account"]').forEach(function(link) {
      if (link.dataset.navBound === "true") return;
      link.dataset.navBound = "true";
      
      link.addEventListener("click", function(e) {
        if (link.hostname === window.location.hostname) {
          if (!isLoggedIn) {
            e.preventDefault();
            var targetUrl = link.getAttribute("href");
            window.location.href = "/signin?next=" + encodeURIComponent(targetUrl);
          }
        }
      });
    });
  }

  // Bind nav dropdowns to toggle on click
  function bindNavDropdowns() {
    var dropdowns = document.querySelectorAll('.nav-dropdown');
    
    dropdowns.forEach(function(dropdown) {
      if (dropdown.dataset.navBound === "true") return;
      dropdown.dataset.navBound = "true";
      
      var btn = dropdown.querySelector('.nav-drop-btn');
      if (!btn) return;
      
      btn.addEventListener("click", function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        // Toggle the current dropdown
        var isShowing = dropdown.classList.contains("show");
        
        // Close all dropdowns first
        dropdowns.forEach(function(d) {
          d.classList.remove("show");
        });
        
        // Toggle the clicked one back if it wasn't showing
        if (!isShowing) {
          dropdown.classList.add("show");
        }
      });
    });
    
    // Close dropdowns if clicking outside
    document.addEventListener("click", function(e) {
      if (!e.target.closest('.nav-dropdown')) {
        document.querySelectorAll('.nav-dropdown.show').forEach(function(d) {
          d.classList.remove("show");
        });
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    // Check login status first, then fetch cart if logged in
    checkLoginStatus().then(function(loggedIn) {
      if (loggedIn) {
        fetchCartFromServer();
        updateWishlistBadges();
      } else {
        updateCartBadges();
      }
    });
    bindAddToCartButtons();
    bindAddToWishlistButtons();
    bindProductCards();
    bindNavbarCartWishlistLinks();
    bindNavDropdowns();
    syncProductRatings();
    bindExistingSearchBoxes();
    injectNavbarSearch();
    refreshProductAvailability();
  });
})();
