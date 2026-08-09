document.addEventListener("DOMContentLoaded", function () {
  var products = [];
  var catalog = [];
  var productGrid = document.getElementById("productGrid");
  var price = document.getElementById("maxPrice");
  var rating = document.getElementById("minRating");
  var category = document.getElementById("categoryFilter");
  var sort = document.getElementById("sortBy");
  var value = document.getElementById("maxPriceValue");
  var recommendationGrid = document.getElementById("recommendationGrid");
  var recommendationLabel = document.getElementById("recommendationLabel");
  var featuredLabel = document.getElementById("featuredLabel");
  var dealsGrid = document.getElementById("dealsGrid");
  var dealsLabel = document.getElementById("dealsLabel");
  var homeImageSlider = document.getElementById("homeImageSlider");
  var homeSliderTrack = document.getElementById("homeSliderTrack");
  var homeSliderDots = document.getElementById("homeSliderDots");
  var sliderItems = [];
  var sliderIndex = 0;
  var sliderTimer = null;
  var sliderAutoIntervalMs = 2600;
  var sliderBound = false;

  function stopSliderAutoplay() {
    if (sliderTimer) {
      clearInterval(sliderTimer);
      sliderTimer = null;
    }
  }

  function startSliderAutoplay() {
    stopSliderAutoplay();
    if (!homeSliderTrack || sliderItems.length < 2) {
      return;
    }
    sliderTimer = setInterval(function () {
      setSliderIndex(sliderIndex + 1);
    }, sliderAutoIntervalMs);
  }

  function setSliderIndex(nextIndex) {
    if (!homeSliderTrack || !sliderItems.length) {
      return;
    }

    var total = sliderItems.length;
    sliderIndex = ((nextIndex % total) + total) % total;
    homeSliderTrack.style.transform = "translateX(" + String(-sliderIndex * 100) + "%)";

    if (homeSliderDots) {
      homeSliderDots.querySelectorAll("[data-slide-dot]").forEach(function (dot) {
        var isActive = Number(dot.getAttribute("data-slide-dot")) === sliderIndex;
        dot.classList.toggle("active", isActive);
        dot.setAttribute("aria-current", isActive ? "true" : "false");
      });
    }
  }

  function formatCategoryLabel(value) {
    var key = String(value || "").trim().toLowerCase();
    if (!key) {
      return "Featured";
    }
    if (key === "homeappliances") {
      return "Home Appliances";
    }
    return key.replace(/\b\w/g, function (ch) { return ch.toUpperCase(); });
  }

  function buildSliderItems(items) {
    var seen = {};
    return (items || [])
      .filter(function (item) {
        var name = item && item.name ? String(item.name) : "";
        if (!name || seen[name] || !item.image) {
          return false;
        }
        seen[name] = true;
        return true;
      })
      .sort(function (a, b) {
        return Number(b.rating || 0) - Number(a.rating || 0);
      })
      .slice(0, 8);
  }

  function bindSliderInteractions() {
    if (sliderBound || !homeImageSlider) {
      return;
    }
    sliderBound = true;
  }

  function renderHomeImageSlider(items) {
    if (!homeSliderTrack || !homeSliderDots || !homeImageSlider) {
      return;
    }

    sliderItems = buildSliderItems(items);
    sliderIndex = 0;
    stopSliderAutoplay();

    if (!sliderItems.length) {
      homeSliderTrack.innerHTML = '<article class="home-slide home-slide-empty"><p>No product images available right now.</p></article>';
      homeSliderDots.innerHTML = "";
      return;
    }

    homeSliderTrack.innerHTML = sliderItems.map(function (item, index) {
      var priceLabel = "INR " + Number(item.price || 0).toLocaleString();
      var ratingValue = Number(item.rating || 0);
      var ratingLabel = (Number(item.review_count || 0) === 0 || ratingValue === 0) ? "0 stars" : ratingValue.toFixed(1) + " stars";
      return (
        '<article class="home-slide" data-slide-index="' + index + '" data-slide-product="' + item.name + '">' +
          '<img src="' + item.image + '" alt="' + item.name + '">' +
          '<div class="home-slide-caption">' +
            '<p class="home-slide-kicker">' + formatCategoryLabel(item.category) + '</p>' +
            '<h3>' + item.name + '</h3>' +
            '<p class="home-slide-meta">' + priceLabel + ' | ' + ratingLabel + '</p>' +
          '</div>' +
        '</article>'
      );
    }).join("");

    homeSliderDots.innerHTML = sliderItems.map(function (_item, index) {
      return '<span class="home-slider-dot" data-slide-dot="' + index + '" aria-current="false"></span>';
    }).join("");

    homeSliderTrack.querySelectorAll(".home-slide").forEach(function (slide) {
      slide.addEventListener("click", function () {
        var productName = slide.getAttribute("data-slide-product") || "";
        if (!productName) {
          return;
        }
        if (window.shopShared && window.shopShared.trackProductClick) {
          window.shopShared.trackProductClick(productName, "home_slider_click");
        }
        if (window.shopShared && window.shopShared.goToSearch) {
          window.shopShared.goToSearch(productName);
        }
      });
    });

    setSliderIndex(0);
    startSliderAutoplay();
  }

  function updateStoreStats(items) {
    var statProducts = document.getElementById("statProducts");
    var statCategories = document.getElementById("statCategories");
    var statTopRating = document.getElementById("statTopRating");
    var statAvgPrice = document.getElementById("statAvgPrice");
    var list = items || [];

    if (statProducts) {
      statProducts.textContent = String(list.length);
    }
    if (statCategories) {
      statCategories.textContent = String(new Set(list.map(function (item) { return item.category; })).size);
    }
    if (statTopRating) {
      var topRating = list.reduce(function (max, item) {
        return Math.max(max, Number(item.rating || 0));
      }, 0);
      statTopRating.textContent = topRating.toFixed(1);
    }
    if (statAvgPrice) {
      var avg = list.length
        ? list.reduce(function (sum, item) { return sum + Number(item.price || 0); }, 0) / list.length
        : 0;
      statAvgPrice.textContent = "INR " + Math.round(avg).toLocaleString();
    }
  }

  function fetchProducts() {
    var url = "/api/products";
    var params = [];
    
    if (category && category.value !== "all") {
      params.push("category=" + category.value);
    }
    if (rating && rating.value > 0) {
      params.push("min_rating=" + rating.value);
    }
    if (price && price.value < 40000) {
      params.push("max_price=" + price.value);
    }
    
    if (params.length > 0) {
      url += "?" + params.join("&");
    }
    
    fetch(url)
      .then(function(res) { 
        if (!res.ok) {
          throw new Error("HTTP error! status: " + res.status);
        }
        return res.json(); 
      })
      .then(function(data) {
        if (data && data.success) {
          products = data.products || [];
          if (category && category.value === "all") {
            catalog = products.slice();
            renderHomeImageSlider(catalog);
          }
          applySort();
          renderProducts();
          updateStoreStats(products); // Dynamically update stats based on current view
          if (featuredLabel) {
            featuredLabel.textContent = products.length
              ? "Showing " + products.length + " products from the live catalog."
              : "No products matched the current filters.";
          }
        } else {
          console.error("API returned failure:", data && data.message);
          if (productGrid) productGrid.innerHTML = '<div class="surface empty">Error loading products catalog.</div>';
        }
      })
      .catch(function(err) {
        console.error("Failed to fetch products:", err);
        if (productGrid) productGrid.innerHTML = '<div class="surface empty">Server is temporarily unavailable.</div>';
      });
  }

  function renderProducts() {
    if (!productGrid) return;
    productGrid.innerHTML = "";
    
    if (!products.length) {
      productGrid.innerHTML = '<div class="surface empty">No products found.</div>';
      return;
    }

    products.forEach(function (p) {
      if (window.shopShared && window.shopShared.buildProductCardMarkup) {
        productGrid.insertAdjacentHTML("beforeend", window.shopShared.buildProductCardMarkup(p));
      } else {
        var node = document.createElement("article");
        node.className = "product-card";
        node.textContent = p.name;
        productGrid.appendChild(node);
      }
    });

    // Rebind cart and wishlist buttons
    if (window.shopShared) {
      window.shopShared.bindAddToCartButtons();
      window.shopShared.bindAddToWishlistButtons();
      window.shopShared.bindProductCards();
    }
  }

  function buildDealCardMarkup(entry) {
    var item = entry && entry.product ? entry.product : null;
    if (!item) {
      return "";
    }

    var safeName = String(item.name || "Product");
    var safeCategory = String(item.category || "general");
    var safeDealPrice = Number(item.deal_price || item.price || 0);
    var safeOriginalPrice = Number(item.original_price || item.price || 0);
    var safeDiscount = Number(item.discount_percent || 0);
    var safeSavings = Number(item.savings || Math.max(safeOriginalPrice - safeDealPrice, 0));
    var safeRating = Number(item.rating || 0);
    var safeImage = String(item.image || "");
    var safeStock = (item.stock !== undefined && item.stock !== null) ? Number(item.stock) : -1;
    var isOOS = safeStock === 0;
    var oosClass = isOOS ? " out-of-stock" : "";
    var oosBadge = isOOS ? '<span class="out-of-stock-badge">Out of Stock</span>' : "";
    var reasonText = String((entry && entry.reason) || "");

    return (
      '<article class="product-card deal-card' + oosClass + '" data-product-card data-name="' + safeName + '" data-price="' + safeDealPrice + '" data-category="' + safeCategory + '" data-rating="' + safeRating + '" data-stock="' + safeStock + '">' +
        '<div class="product-image">' +
          oosBadge +
          '<span class="deal-badge">' + safeDiscount + '% OFF</span>' +
          '<img src="' + safeImage + '" alt="' + safeName + '">' +
        '</div>' +
        '<strong>' + safeName + '</strong>' +
        '<div class="product-meta deal-meta">' +
          '<span class="price">INR ' + safeDealPrice.toLocaleString() + '</span>' +
          '<span class="deal-original-price">INR ' + safeOriginalPrice.toLocaleString() + '</span>' +
        '</div>' +
        '<p class="deal-savings">Save INR ' + safeSavings.toLocaleString() + ' today</p>' +
        '<p class="deal-reason">' + reasonText + '</p>' +
        '<div class="controls">' +
          '<button class="primary-btn" data-add-cart data-name="' + safeName + '" data-price="' + safeDealPrice + '" data-image="' + safeImage + '">Add to Cart</button>' +
          '<button class="secondary-btn" data-add-wishlist data-name="' + safeName + '" data-price="' + safeDealPrice + '" data-image="' + safeImage + '">Save</button>' +
        '</div>' +
      '</article>'
    );
  }

  function loadTodaysDeals() {
    if (!dealsGrid) {
      return;
    }

    var url = "/api/deals/today?limit=8";
    if (category && category.value && category.value !== "all") {
      url += "&category=" + encodeURIComponent(category.value);
    }

    if (dealsLabel) {
      dealsLabel.textContent = "Loading today's offers...";
    }

    var hasDealsLoaded = false;
    fetch(url, { credentials: "include" })
      .then(function (res) { 
        if (!res.ok) {
          throw new Error("HTTP " + res.status + " while loading deals");
        }
        return res.json(); 
      })
      .then(function (data) {
        var deals = (data && data.success && Array.isArray(data.deals)) ? data.deals : [];

        if (!deals.length) {
          dealsGrid.innerHTML = '<div class="surface empty">No deals are available right now.</div>';
          if (dealsLabel) {
            dealsLabel.textContent = "No active deals at the moment. Check back soon.";
          }
          return;
        }

        dealsGrid.innerHTML = deals.map(function (entry) {
          return buildDealCardMarkup(entry);
        }).join("");

        if (dealsLabel) {
          dealsLabel.textContent = category && category.value !== "all"
            ? "Daily deals curated for " + formatCategoryLabel(category.value) + "."
            : "Limited-time discounted picks selected for today.";
        }

        if (window.shopShared) {
          window.shopShared.bindAddToCartButtons();
          window.shopShared.bindAddToWishlistButtons();
          window.shopShared.bindProductCards();
        }
        hasDealsLoaded = true;
      })
      .catch(function (err) {
        console.error("Deals fetch error:", err);
        dealsGrid.innerHTML = '<div class="surface empty">Unable to load today\'s deals right now.</div>';
        if (dealsLabel) {
          dealsLabel.textContent = "Deals are temporarily unavailable.";
        }
      });
  }

  function loadRecommendations() {
    if (!recommendationGrid || !window.shopShared || !window.shopShared.fetchRecommendations) {
      return;
    }
    if (recommendationLabel) {
      recommendationLabel.textContent = "Loading tailored picks...";
    }
    recommendationGrid.innerHTML = "";
    window.shopShared.fetchRecommendations({ limit: 6 }).then(function(recommendations) {
      if (recommendationLabel) {
        recommendationLabel.textContent = window.shopShared.isLoggedIn()
          ? "Tailored picks based on what you browse and add"
          : "Popular choices shoppers are loving";
      }
      window.shopShared.renderRecommendationSection(
        recommendationGrid,
        recommendations,
        "Recommendations will appear here once products are available."
      );
    });
  }

  function applyFilters() {
    var allCards = document.querySelectorAll("#productGrid .product-card");
    allCards.forEach(function (card) {
      var okPrice = Number(card.dataset.price) <= Number(price.value);
      var okRating = Number(card.dataset.rating) >= Number(rating.value);
      var okCategory = category.value === "all" || card.dataset.category === category.value;
      card.style.display = okPrice && okRating && okCategory ? "block" : "none";
    });
  }

  function applySort() {
    if (sort.value === "price-low") {
      products.sort(function (a, b) { return Number(a.price || 0) - Number(b.price || 0); });
    } else if (sort.value === "price-high") {
      products.sort(function (a, b) { return Number(b.price || 0) - Number(a.price || 0); });
    } else if (sort.value === "rating") {
      products.sort(function (a, b) {
        return (Number(b.rating || 0) - Number(a.rating || 0)) ||
          (Number(b.review_count || 0) - Number(a.review_count || 0));
      });
    } else {
      products.sort(function (a, b) {
        var categoryCompare = String(a.category || "").localeCompare(String(b.category || ""));
        if (categoryCompare !== 0) {
          return categoryCompare;
        }
        return (Number(b.rating || 0) - Number(a.rating || 0)) ||
          (Number(b.review_count || 0) - Number(a.review_count || 0));
      });
    }
    renderProducts();
  }

  function bootstrapStorefront() {
    fetch("/api/products", { credentials: "include" })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        catalog = (data && data.success && Array.isArray(data.products)) ? data.products : [];
        bindSliderInteractions();
        renderHomeImageSlider(catalog);
        updateStoreStats(catalog);
      })
      .catch(function () {
        bindSliderInteractions();
        renderHomeImageSlider([]);
      });
  }

  // Event listeners
  if (price) {
    price.addEventListener("input", function () {
      value.textContent = "INR " + Number(price.value).toLocaleString();
      fetchProducts();
    });
  }
  
  if (rating) {
    rating.addEventListener("change", function () {
      fetchProducts();
    });
  }
  
  if (category) {
    category.addEventListener("change", function () {
      fetchProducts();
      loadTodaysDeals();
    });
  }
  
  if (sort) {
    sort.addEventListener("change", function () {
      applySort();
    });
  }

  // Initial load
  if (value && price) {
    value.textContent = "INR " + Number(price.value).toLocaleString();
  }
  bindSliderInteractions();
  bootstrapStorefront();
  fetchProducts();
  loadTodaysDeals();
  loadRecommendations();

  // Deals Modal Logic
  var openDealsBtn = document.getElementById("openDealsBtn");
  var closeDealsBtn = document.getElementById("closeDealsBtn");
  var dealsModal = document.getElementById("dealsModal");

  if (openDealsBtn && dealsModal) {
    openDealsBtn.addEventListener("click", function() {
      dealsModal.classList.add("active");
      // Always attempt to reload deals when opening the modal to ensure fresh data
      loadTodaysDeals();
    });
  }

  if (closeDealsBtn && dealsModal) {
    closeDealsBtn.addEventListener("click", function() {
      dealsModal.classList.remove("active");
    });
  }

  if (dealsModal) {
    dealsModal.addEventListener("click", function(e) {
      if (e.target === dealsModal) {
        dealsModal.classList.remove("active");
      }
    });
  }

  document.addEventListener("shoppingActivityChanged", function () {
    loadTodaysDeals();
    loadRecommendations();
  });
});

// Auth UI handled by shared.js toggleAuthUI()
