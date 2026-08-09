document.addEventListener("DOMContentLoaded", function () {
  // Check if user is logged in
  fetch("/api/check_session", { credentials: "include" })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (!data.logged_in) {
        // Not logged in, redirect to signin
        window.location.href = "/signin?next=/addtocart";
        return;
      }
      // User is logged in, initialize cart page
      initializeCartPage();
    })
    .catch(function() {
      window.location.href = "/signin?next=/addtocart";
    });
});

function initializeCartPage() {
  var container = document.getElementById("cartItems");
  var subtotal = document.getElementById("subtotal");
  var total = document.getElementById("total");
  var checkoutLinks = document.querySelectorAll("[data-checkout-link]");

  function updateCheckoutLinks() {
    checkoutLinks.forEach(function (link) {
      link.setAttribute("href", "/checkout");
    });
  }

  function render(items) {
    container.innerHTML = "";

    if (!items || !items.length) {
      container.innerHTML = '<div class="surface empty">Your cart is empty. Continue shopping from the catalog.</div>';
      subtotal.textContent = "INR 0";
      total.textContent = "INR 0";
      return;
    }

    var sum = 0;
    items.forEach(function (item, index) {
      var qty = Number(item.quantity || 1);
      sum += Number(item.price) * qty;

      var node = document.createElement("article");
      node.className = "product-card";
      node.setAttribute("data-product-card", "");
      node.setAttribute("data-name", item.name);
      node.setAttribute("data-price", String(Number(item.price)));
      node.setAttribute("data-category", "cart");
      node.setAttribute("data-rating", String(Number(item.rating || 0)));
      node.innerHTML =
        '<div style="display:flex;gap:12px;align-items:center;">' +
          '<div class="product-image" style="width:110px;height:95px;margin:0;flex-shrink:0;">' +
            '<img src="' + item.image + '" alt="' + item.name + '">' +
          '</div>' +
          '<div style="flex:1;">' +
            '<strong>' + item.name + '</strong>' +
            '<div class="muted" style="margin-top:4px;">INR ' + Number(item.price).toLocaleString() + '</div>' +
            '<div class="controls" style="margin-top:10px;max-width:210px;">' +
              '<button class="secondary-btn" data-minus="' + index + '">-</button>' +
              '<button class="secondary-btn" style="pointer-events:none;">Qty ' + qty + '</button>' +
              '<button class="secondary-btn" data-plus="' + index + '">+</button>' +
            '</div>' +
          '</div>' +
          '<button class="secondary-btn" data-remove="' + index + '"><i class="fa-solid fa-trash"></i>Remove</button>' +
        '</div>';
      container.appendChild(node);
    });

    if (window.shopShared && window.shopShared.bindProductCards) {
      window.shopShared.bindProductCards();
    }

    subtotal.textContent = "INR " + sum.toLocaleString();
    total.textContent = "INR " + sum.toLocaleString();

    container.querySelectorAll("[data-plus]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var idx = Number(btn.dataset.plus);
        var currentQty = Number(items[idx].quantity || 1);
        fetch("/api/cart/update_quantity", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ index: idx, quantity: currentQty + 1 })
        })
          .then(function(res) { return res.json(); })
          .then(function(data) {
            if (data.success) {
              loadCart();
            } else if (data.out_of_stock && window.shopShared) {
              window.shopShared.showPopup({
                type: "error",
                title: "Out of Stock",
                message: data.message || "You cannot add more of this product."
              });
            }
          });
      });
    });

    container.querySelectorAll("[data-minus]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var idx = Number(btn.dataset.minus);
        var currentQty = Number(items[idx].quantity || 1);
        if (currentQty > 1) {
          fetch("/api/cart/update_quantity", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ index: idx, quantity: currentQty - 1 })
          })
            .then(function(res) { return res.json(); })
            .then(function(data) {
              if (data.success) {
                loadCart();
              }
            });
        } else {
          fetch("/api/cart/remove", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ index: idx })
          })
            .then(function(res) { return res.json(); })
            .then(function(data) {
              if (data.success) {
                if (window.shopShared) {
                  window.shopShared.updateCartBadges();
                }
                window.shopShared.showToast("Item removed");
                loadCart();
              }
            });
        }
      });
    });

    container.querySelectorAll("[data-remove]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var idx = Number(btn.dataset.remove);
        fetch("/api/cart/remove", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ index: idx })
        })
          .then(function(res) { return res.json(); })
          .then(function(data) {
            if (data.success) {
              if (window.shopShared) {
                window.shopShared.updateCartBadges();
              }
              window.shopShared.showToast("Item removed");
              loadCart(); // Reload cart
            }
          });
      });
    });
  }

  function loadCart() {
    fetch("/api/cart", { credentials: "include" })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success) {
          render(data.items || []);
          // Update navbar badge
          var cartCountEl = document.querySelector("[data-cart-count]");
          if (cartCountEl) {
            cartCountEl.textContent = (data.items || []).length;
          }
        }
      })
      .catch(function() {
        render([]);
      });
  }

  updateCheckoutLinks();
  loadCart();
}
