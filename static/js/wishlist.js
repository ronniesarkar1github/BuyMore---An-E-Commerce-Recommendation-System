document.addEventListener("DOMContentLoaded", function () {
  var container = document.getElementById("wishlistContainer");
  if (!container) {
    container = document.querySelector(".card-grid");
  }

  var isLoaded = false;

  function render(items) {
    console.log("Rendering items:", items);
    if (!container) return;

    // Persistence Guard: If we've already successfully rendered items,
    // ignore subsequent empty calls that appear within the same session window.
    if (isLoaded && (!items || items.length === 0) && container.querySelectorAll("article").length > 0) {
      console.warn("Ignoring empty render clobber attempt.");
      return;
    }
    
    container.innerHTML = "";
    isLoaded = true; // Mark as loaded regardless of item count

    if (!items || items.length === 0) {
      container.innerHTML = '<div class="surface empty">Your wishlist is empty. Browse products and save your favorites!</div>';
      return;
    }

    items.forEach(function (item) {
      try {
        if (!item || !item.name) return;
        var node = document.createElement("article");
        node.className = "product-card";
        node.setAttribute("data-product-card", "");
        node.setAttribute("data-name", item.name);
        
        var priceValue = Number(item.price) || 0;
        node.setAttribute("data-price", String(priceValue));
        node.setAttribute("data-category", item.category || "General");
        node.setAttribute("data-rating", String(Number(item.rating || 0)));
        
        node.innerHTML =
          '<div class="product-image">' +
            '<img src="' + (item.image || "/static/images/placeholder.svg") + '" alt="' + item.name + '">' +
          '</div>' +
          '<strong>' + item.name + '</strong>' +
          '<div class="product-meta">' +
            '<span class="price">INR ' + priceValue.toLocaleString() + '</span>' +
            '<span class="muted">' + (item.category || "General") + '</span>' +
          '</div>' +
          '<div class="controls">' +
            '<button class="primary-btn" data-add-cart data-name="' + item.name + '" data-price="' + priceValue + '" data-image="' + item.image + '">Add to Cart</button>' +
            '<button class="secondary-btn" data-remove-wishlist data-name="' + item.name + '">Remove</button>' +
          '</div>';
        container.appendChild(node);
      } catch (e) {
        console.error("Error rendering wishlist item:", e, item);
      }
    });

    // Rebind product cards and cart buttons
    if (window.shopShared) {
      window.shopShared.bindProductCards();
      window.shopShared.bindAddToCartButtons();
    }

    // Bind remove buttons
    container.querySelectorAll("[data-remove-wishlist]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var name = btn.dataset.name;
        if (window.shopShared && window.shopShared.removeFromWishlist) {
          window.shopShared.removeFromWishlist(name);
        }
      });
    });
  }

  function loadWishlist() {
    fetch("/api/wishlist", { credentials: "include" })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success) {
          render(data.items || []);
        }
      })
      .catch(function() {
        render([]);
      });
  }

  // Load wishlist on page load
  loadWishlist();

  // Listen for wishlist updates
  document.addEventListener("wishlistUpdated", function () {
    loadWishlist();
  });
});
