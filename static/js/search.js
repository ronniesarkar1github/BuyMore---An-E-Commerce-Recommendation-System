document.addEventListener("DOMContentLoaded", function () {
  var params = new URLSearchParams(window.location.search);
  var query = (params.get("q") || "").trim();
  var category = (params.get("category") || "all").trim().toLowerCase();
  var minRating = (params.get("min_rating") || "").trim();
  var minReviews = (params.get("min_reviews") || "").trim();
  var maxPrice = (params.get("max_price") || "").trim();
  var sort = (params.get("sort") || "relevance").trim().toLowerCase();

  var form = document.getElementById("searchPageForm");
  var input = document.getElementById("searchPageInput");
  var filterForm = document.getElementById("searchFilterForm");
  var categoryFilter = document.getElementById("searchCategoryFilter");
  var minRatingFilter = document.getElementById("searchMinRatingFilter");
  var minReviewsFilter = document.getElementById("searchMinReviewsFilter");
  var maxPriceFilter = document.getElementById("searchMaxPriceFilter");
  var sortFilter = document.getElementById("searchSortFilter");
  var summary = document.getElementById("searchSummary");
  var countLabel = document.getElementById("searchCountLabel");
  var resultsGrid = document.getElementById("searchResultsGrid");
  var recommendationLabel = document.getElementById("searchRecommendationLabel");
  var recommendationGrid = document.getElementById("searchRecommendationGrid");

  function safeSetValue(node, value) {
    if (node) {
      node.value = value;
    }
  }

  safeSetValue(input, query);
  safeSetValue(categoryFilter, category || "all");
  safeSetValue(minRatingFilter, minRating);
  safeSetValue(minReviewsFilter, minReviews);
  safeSetValue(maxPriceFilter, maxPrice);
  safeSetValue(sortFilter, sort || "relevance");

  function getStateFromInputs() {
    return {
      q: (input ? input.value : "").trim(),
      category: (categoryFilter ? categoryFilter.value : "all").trim().toLowerCase(),
      minRating: (minRatingFilter ? minRatingFilter.value : "").trim(),
      minReviews: (minReviewsFilter ? minReviewsFilter.value : "").trim(),
      maxPrice: (maxPriceFilter ? maxPriceFilter.value : "").trim(),
      sort: (sortFilter ? sortFilter.value : "relevance").trim().toLowerCase()
    };
  }

  function buildProductApiUrl(state) {
    var apiParams = new URLSearchParams();
    if (state.q) {
      apiParams.set("q", state.q);
    }
    if (state.category && state.category !== "all") {
      apiParams.set("category", state.category);
    }
    if (state.minRating) {
      apiParams.set("min_rating", state.minRating);
    }
    if (state.minReviews) {
      apiParams.set("min_reviews", state.minReviews);
    }
    if (state.maxPrice) {
      apiParams.set("max_price", state.maxPrice);
    }
    if (state.sort) {
      apiParams.set("sort", state.sort);
    }
    return "/api/products" + (apiParams.toString() ? "?" + apiParams.toString() : "");
  }

  function updateBrowserUrl(state) {
    var pageParams = new URLSearchParams();
    if (state.q) {
      pageParams.set("q", state.q);
    }
    if (state.category && state.category !== "all") {
      pageParams.set("category", state.category);
    }
    if (state.minRating) {
      pageParams.set("min_rating", state.minRating);
    }
    if (state.minReviews) {
      pageParams.set("min_reviews", state.minReviews);
    }
    if (state.maxPrice) {
      pageParams.set("max_price", state.maxPrice);
    }
    if (state.sort && state.sort !== "relevance") {
      pageParams.set("sort", state.sort);
    }
    var nextUrl = "/search" + (pageParams.toString() ? "?" + pageParams.toString() : "");
    window.history.replaceState({}, "", nextUrl);
  }

  function renderResults(products) {
    if (!resultsGrid) {
      return;
    }
    resultsGrid.innerHTML = "";

    if (!products.length) {
      resultsGrid.innerHTML = '<div class="surface empty">No products matched your filters. Try changing your keyword or range.</div>';
      return;
    }

    products.forEach(function (product) {
      resultsGrid.insertAdjacentHTML("beforeend", window.shopShared.buildProductCardMarkup(product));
    });

    window.shopShared.bindAddToCartButtons();
    window.shopShared.bindAddToWishlistButtons();
    window.shopShared.bindProductCards();
  }

  function loadResults(state) {
    var url = buildProductApiUrl(state);

    fetch(url, { credentials: "include" })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        var products = (data && data.success && Array.isArray(data.products)) ? data.products : [];
        var rankingMode = data && data.ranking ? data.ranking.mode : null;

        if (summary) {
          if (state.q) {
            summary.textContent = 'Showing ranked results for "' + state.q + '" using hybrid relevance, popularity, and ratings.';
          } else {
            summary.textContent = "Browse the catalog with keyword search, filters, and hybrid ranking.";
          }
        }
        if (countLabel) {
          countLabel.textContent = products.length
            ? products.length + " product(s) found" + (rankingMode ? " | sort: " + rankingMode : "")
            : "No matching products found";
        }
        renderResults(products);
      })
      .catch(function () {
        if (countLabel) {
          countLabel.textContent = "Unable to load results right now.";
        }
        if (resultsGrid) {
          resultsGrid.innerHTML = '<div class="surface empty">Search is temporarily unavailable.</div>';
        }
      });
  }

  function loadRecommendations(state) {
    if (!recommendationGrid || !window.shopShared || !window.shopShared.fetchRecommendations) {
      return;
    }

    recommendationGrid.innerHTML = "";
    if (recommendationLabel) {
      recommendationLabel.textContent = "Loading hybrid recommendations...";
    }

    var config = { limit: 6 };
    if (state.q) {
      config.productName = state.q;
    }

    window.shopShared.fetchRecommendations(config)
      .then(function (recommendations) {
        if (recommendationLabel) {
          recommendationLabel.textContent = recommendations.length
            ? "Recommended based on what matches your search and what similar shoppers liked"
            : "No related recommendations found.";
        }
        window.shopShared.renderRecommendationSection(
          recommendationGrid,
          recommendations,
          "Recommendations will appear here once the catalog has matching products."
        );
      })
      .catch(function () {
        if (recommendationLabel) {
          recommendationLabel.textContent = "Unable to load recommendations right now.";
        }
      });
  }

  function applySearchState() {
    var state = getStateFromInputs();
    updateBrowserUrl(state);
    loadResults(state);
    loadRecommendations(state);
  }

  if (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      applySearchState();
    });
  }

  if (filterForm) {
    filterForm.addEventListener("submit", function (event) {
      event.preventDefault();
      applySearchState();
    });
  }

  loadResults(getStateFromInputs());
  loadRecommendations(getStateFromInputs());
});
