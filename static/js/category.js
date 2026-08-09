document.addEventListener("DOMContentLoaded", function () {
  var cards = Array.from(document.querySelectorAll("[data-product-card]"));
  var search = document.getElementById("searchBox");

  if (search) {
    search.addEventListener("input", function () {
      var query = search.value.trim().toLowerCase();
      cards.forEach(function (card) {
        var name = (card.dataset.name || "").toLowerCase();
        card.style.display = name.includes(query) ? "block" : "none";
      });
    });
  }
});
