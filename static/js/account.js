document.addEventListener("DOMContentLoaded", function () {
  // Check session and load user data
  checkSession();
  
  if (window.shopShared) {
    window.shopShared.updateCartBadges();
    window.shopShared.updateWishlistBadges();
  }
});

function checkSession() {
  fetch("/api/check_session", {
    credentials: "include"
  })
    .then(function(response) { return response.json(); })
    .then(function(data) {
      if (!data.logged_in) {
        // Not logged in, redirect to signin
        window.location.href = "/signin";
        return;
      }
      // Logged in, load user profile
      loadUserProfile();
    })
    .catch(function(error) {
      console.error("Session check failed:", error);
      window.location.href = "/signin";
    });
}

function loadUserProfile() {
  // Get user name from localStorage (set during login)
  var storedName = localStorage.getItem("userName") || "User";
  
  // Update user info
  var welcomeEl = document.querySelector(".page-head h1");
  if (welcomeEl) {
    welcomeEl.innerHTML = '<i class="fa-solid fa-user-check"></i> Welcome Back, ' + storedName;
  }
  
  // Fetch cart count
  var cartCountEl = document.querySelector(".stats-cart");
  fetch("/api/cart", { credentials: "include" })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      var cartCount = (data.items || []).length;
      if (cartCountEl) cartCountEl.textContent = cartCount;
      
      var navbarCartCountEl = document.querySelector("[data-cart-count]");
      if (navbarCartCountEl) navbarCartCountEl.textContent = cartCount;
    })
    .catch(function() {
      if (cartCountEl) cartCountEl.textContent = "0";
    });
    
  // Fetch wishlist count
  var wishlistCountEl = document.querySelector(".stats-wishlist");
  fetch("/api/wishlist", { credentials: "include" })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      var wishlistCount = (data.items || []).length;
      if (wishlistCountEl) wishlistCountEl.textContent = wishlistCount;
      
      var navbarWishlistCountEl = document.querySelector("[data-wishlist-count]");
      if (navbarWishlistCountEl) navbarWishlistCountEl.textContent = wishlistCount;
    })
    .catch(function() {
      if (wishlistCountEl) wishlistCountEl.textContent = "0";
    });

  // Load actual orders and stats
  loadUserOrders();
  loadAccountRecommendations();
}

function loadUserOrders() {
  var totalOrdersEl = document.querySelector(".stats-orders");
  var inTransitEl = document.querySelector(".stats-transit");
  var deliveredEl = document.querySelector(".stats-delivered");
  var ordersTableBody = document.getElementById("ordersTableBody");
  var ordersTable = document.getElementById("ordersTable");
  var noOrdersMessage = document.getElementById("noOrdersMessage");

  fetch("/api/orders", { credentials: "include" })
    .then(function(res) { return res.json(); })
    .then(function(orders) {
      if (!Array.isArray(orders)) return;

      // Update counters
      if (totalOrdersEl) totalOrdersEl.textContent = orders.length;
      
      var inTransitCount = orders.filter(function(o) { 
        var s = (o.status || "").toLowerCase();
        return s === "shipped" || s === "processing" || s === "placed"; 
      }).length;
      if (inTransitEl) inTransitEl.textContent = inTransitCount;

      var deliveredCount = orders.filter(function(o) { 
        return (o.status || "").toLowerCase() === "delivered"; 
      }).length;
      if (deliveredEl) deliveredEl.textContent = deliveredCount;

      // Update table
      if (orders.length > 0) {
        if (noOrdersMessage) noOrdersMessage.style.display = "none";
        if (ordersTable) ordersTable.style.display = "table";
        
        if (ordersTableBody) {
          ordersTableBody.innerHTML = orders.map(function(o) {
            var shortId = o._id.substring(o._id.length - 8).toUpperCase();
            var itemNames = (o.items || []).map(function(i) { return i.name; }).join(", ");
            if (itemNames.length > 30) itemNames = itemNames.substring(0, 27) + "...";
            
            var statusClass = "badge";
            var status = (o.status || "placed").toLowerCase();
            if (status === "delivered") statusClass += " success";
            else if (status === "cancelled") statusClass += " danger";
            else statusClass += " warn";

            return '<tr>' +
              '<td><strong>#' + shortId + '</strong></td>' +
              '<td>' + (itemNames || "Order Details") + '</td>' +
              '<td><span class="' + statusClass + '">' + (o.status || "Placed") + '</span></td>' +
              '<td>' + (o.created_at || "N/A") + '</td>' +
              '</tr>';
          }).join("");
        }
      } else {
        if (noOrdersMessage) noOrdersMessage.style.display = "block";
        if (ordersTable) ordersTable.style.display = "none";
      }
    })
    .catch(function(err) {
      console.error("Failed to load orders:", err);
    });
}

function loadAccountRecommendations() {
  var grid = document.getElementById("accountRecommendationGrid");
  var label = document.getElementById("accountRecommendationLabel");
  if (!grid || !window.shopShared || !window.shopShared.fetchRecommendations) {
    return;
  }

  if (label) {
    label.textContent = "Loading personalized picks...";
  }

  window.shopShared.fetchRecommendations({ limit: 6 })
    .then(function(recommendations) {
      if (label) {
        label.textContent = recommendations.length
          ? "Based on products you viewed, plus similar shoppers"
          : "No recommendations available yet.";
      }
      window.shopShared.renderRecommendationSection(
        grid,
        recommendations,
        "Recommendations will appear here after you start exploring products."
      );
    })
    .catch(function() {
      if (label) {
        label.textContent = "Unable to load recommendations right now.";
      }
    });
}
