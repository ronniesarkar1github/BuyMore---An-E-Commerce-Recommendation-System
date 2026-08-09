document.addEventListener("DOMContentLoaded", function () {
  var form = document.getElementById("contactForm");
  if (!form) {
    return;
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var name = document.getElementById("contactName").value.trim();
    var email = document.getElementById("contactEmail").value.trim();
    var phone = document.getElementById("contactPhone").value.trim();
    var topic = document.getElementById("contactTopic").value.trim();
    var message = document.getElementById("contactMessage").value.trim();

    if (!/^[0-9]{10}$/.test(phone)) {
      window.shopShared.showPopup({
        type: "error",
        title: "Invalid Phone Number",
        message: "Enter a valid 10-digit phone number."
      });
      return;
    }

    var submitBtn = form.querySelector('button[type="submit"]');
    var originalText = submitBtn.innerText;
    submitBtn.innerText = "Submitting...";
    submitBtn.disabled = true;

    fetch("/api/contact", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: name,
        email: email,
        phone: phone,
        topic: topic,
        message: message
      })
    })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      submitBtn.innerText = originalText;
      submitBtn.disabled = false;
      if (data.success) {
        window.shopShared.showPopup({
          type: "success",
          title: "Request Submitted",
          message: "Thank you for contacting BuyMore. Our team will respond shortly."
        });
        form.reset();
      } else {
        window.shopShared.showPopup({
          type: "error",
          title: "Submission Failed",
          message: data.message || "Could not submit your request. Please try again."
        });
      }
    })
    .catch(function(err) {
      console.error(err);
      submitBtn.innerText = originalText;
      submitBtn.disabled = false;
      window.shopShared.showPopup({
        type: "error",
        title: "Error",
        message: "An unexpected error occurred."
      });
    });
  });
});
