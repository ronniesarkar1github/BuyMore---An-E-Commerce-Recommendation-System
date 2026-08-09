document.addEventListener("DOMContentLoaded", function () {
  if (localStorage.getItem("isLoggedIn") !== "true") {
    window.location.href = "/signin?next=/checkout";
    return;
  }

  var list = document.getElementById("checkoutItems");
  var subtotalEl = document.getElementById("checkoutSubtotal");
  var totalEl = document.getElementById("checkoutTotal");
  var placeOrderBtn = document.getElementById("placeOrderBtn");
  var recommendationGrid = document.getElementById("checkoutRecommendationGrid");
  var recommendationLabel = document.getElementById("checkoutRecommendationLabel");
  
  var cartItems = [];

  function renderSummary() {
    list.innerHTML = "";

    if (!cartItems.length) {
      list.innerHTML = '<div class="empty surface">Your cart is empty.</div>';
      subtotalEl.textContent = "INR 0";
      totalEl.textContent = "INR 0";
      placeOrderBtn.disabled = true;
      placeOrderBtn.classList.add("secondary-btn");
      return;
    }

    var sum = 0;
    cartItems.forEach(function (item) {
      var qty = Number(item.quantity || 1);
      var lineTotal = Number(item.price) * qty;
      sum += lineTotal;

      var row = document.createElement("div");
      row.className = "payment-option";
      row.innerHTML =
        '<span style="flex:1;">' + item.name + ' x' + qty + "</span>" +
        '<strong>INR ' + lineTotal.toLocaleString() + "</strong>";
      list.appendChild(row);
    });

    subtotalEl.textContent = "INR " + sum.toLocaleString();
    totalEl.textContent = "INR " + sum.toLocaleString();
    placeOrderBtn.disabled = false;
    placeOrderBtn.classList.remove("secondary-btn");
  }

  function getFormData() {
    return {
      fullName: document.getElementById("fullName").value.trim(),
      phone: document.getElementById("phone").value.trim(),
      address: document.getElementById("address").value.trim(),
      city: document.getElementById("city").value.trim(),
      state: document.getElementById("state").value.trim(),
      pincode: document.getElementById("pincode").value.trim(),
      email: document.getElementById("userEmailDisplay") ? document.getElementById("userEmailDisplay").textContent.trim() : "",
      payment: document.querySelector('input[name="payment"]:checked').value
    };
  }

  function validate(data) {
    if (!data.fullName || !data.address || !data.city || !data.state) {
      return "Please fill all address fields.";
    }
    if (!/^[0-9]{10}$/.test(data.phone)) {
      return "Please enter a valid 10-digit phone number.";
    }
    if (!/^[0-9]{6}$/.test(data.pincode)) {
      return "Please enter a valid 6-digit pincode.";
    }
    return "";
  }

  function loadCheckoutRecommendations() {
    if (!recommendationGrid || !window.shopShared || !window.shopShared.fetchRecommendations) {
      return;
    }

    if (!cartItems.length) {
      if (recommendationLabel) {
        recommendationLabel.textContent = "Add products to unlock hybrid recommendations.";
      }
      window.shopShared.renderRecommendationSection(
        recommendationGrid,
        [],
        "Recommendations will appear here after you add products to the cart."
      );
      return;
    }

    var topRatedItem = cartItems.slice().sort(function (a, b) {
      return Number(b.rating || 0) - Number(a.rating || 0);
    })[0];

    if (recommendationLabel) {
      recommendationLabel.textContent = topRatedItem && topRatedItem.name
        ? 'Inspired by "' + topRatedItem.name + '" based on item similarity and shopper behavior'
        : "Loading personalized product picks...";
    }

    window.shopShared.fetchRecommendations({
      productName: topRatedItem && topRatedItem.name ? topRatedItem.name : "",
      limit: 4
    })
      .then(function (recommendations) {
        if (recommendationLabel) {
          recommendationLabel.textContent = recommendations.length
            ? "Chosen using item similarity and shopper behavior"
            : "No recommendations available right now.";
        }
        window.shopShared.renderRecommendationSection(
          recommendationGrid,
          recommendations,
          "No similar products found for the items in your cart."
        );
      })
      .catch(function () {
        if (recommendationLabel) {
          recommendationLabel.textContent = "Unable to load recommendations right now.";
        }
      });
  }

  placeOrderBtn.addEventListener("click", function () {
    if (!cartItems.length) {
      window.shopShared.showPopup({
        type: "warn",
        title: "Cart Empty",
        message: "Add products before placing an order.",
        primaryText: "Go to Home",
        onPrimary: function () {
          window.location.href = "/home";
        }
      });
      return;
    }

    var data = getFormData();
    var error = validate(data);
    if (error) {
      window.shopShared.showPopup({
        type: "error",
        title: "Incomplete Checkout",
        message: error
      });
      return;
    }
    placeOrderBtn.disabled = true;
    fetch("/api/orders/place", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        shipping: data,
        payment: data.payment
      })
    })
      .then(function (res) { return res.json(); })
      .then(function (payload) {
        if (!payload || !payload.success) {
          throw new Error((payload && payload.message) || "Failed to place order");
        }
        cartItems = [];
        renderSummary();
        if (window.shopShared && window.shopShared.updateCartBadges) {
          window.shopShared.updateCartBadges();
        }
        if (recommendationGrid && window.shopShared && window.shopShared.renderRecommendationSection) {
          var mergedRecommendations = []
            .concat(payload.recommendations || [])
            .concat(payload.frequently_bought_together || []);
          var seenNames = {};
          var uniqueRecommendations = mergedRecommendations.filter(function(entry) {
            var product = entry && entry.product ? entry.product : null;
            var name = product && product.name ? product.name : "";
            if (!name || seenNames[name]) {
              return false;
            }
            seenNames[name] = true;
            return true;
          }).slice(0, 6);

          window.shopShared.renderRecommendationSection(
            recommendationGrid,
            uniqueRecommendations,
            "No follow-up recommendations available yet."
          );
          if (recommendationLabel) {
            recommendationLabel.textContent = payload.recommendation_anchor
              ? 'Recommended next after "' + payload.recommendation_anchor + '" (including frequently bought together)'
              : "Recommended next products";
          }
        }
        window.shopShared.showPopup({
          type: "success",
          title: "Order Placed Successfully",
          message: "Order ID: " + payload.order_id + ". Payment method: " + data.payment + ".",
          primaryText: "Go to Account",
          onPrimary: function () {
            window.location.href = "/account";
          }
        });
      })
      .catch(function (err) {
        window.shopShared.showPopup({
          type: "error",
          title: "Order Failed",
          message: err && err.message ? err.message : "Unable to place order right now."
        });
      })
      .finally(function () {
        placeOrderBtn.disabled = false;
      });
  });

  // Fetch cart from server
  fetch("/api/cart", { credentials: "include" })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (data.success) {
        cartItems = data.items || [];
      }
      renderSummary();
      loadCheckoutRecommendations();
    })
    .catch(function() {
      cartItems = [];
      renderSummary();
      loadCheckoutRecommendations();
    });
});
