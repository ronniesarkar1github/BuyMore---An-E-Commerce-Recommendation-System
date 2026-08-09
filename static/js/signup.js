document.addEventListener("DOMContentLoaded", function () {
  var form = document.getElementById("signupForm");
  
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    
    var name = document.getElementById("name").value.trim();
    var email = document.getElementById("email").value.trim();
    var password = document.getElementById("password").value;
    var confirmPassword = document.getElementById("confirmPassword").value;
    
    // Client-side validation
    if (!name || !email || !password || !confirmPassword) {
      window.shopShared.showPopup({
        type: "warn",
        title: "Missing Fields",
        message: "Please fill in all fields."
      });
      return;
    }
    
    if (name.length < 2) {
      window.shopShared.showPopup({
        type: "warn",
        title: "Invalid Name",
        message: "Please enter your full name."
      });
      return;
    }
    
    if (!email.includes("@") || !email.includes(".")) {
      window.shopShared.showPopup({
        type: "warn",
        title: "Invalid Email",
        message: "Please enter a valid email address."
      });
      return;
    }
    
    if (password.length < 6) {
      window.shopShared.showPopup({
        type: "warn",
        title: "Weak Password",
        message: "Password must be at least 6 characters."
      });
      return;
    }
    
    if (password !== confirmPassword) {
      window.shopShared.showPopup({
        type: "warn",
        title: "Password Mismatch",
        message: "Passwords do not match. Please try again."
      });
      return;
    }
    
    // Show loading state
    var submitBtn = form.querySelector('button[type="submit"]');
    var originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Creating Account...';
    submitBtn.disabled = true;
    
    // Send registration request
    fetch("/api/register", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        name: name,
        email: email,
        password: password
      })
    })
    .then(function (response) {
      return response.json();
    })
    .then(function (data) {
      if (data.success) {
        window.shopShared.showPopup({
          type: "success",
          title: "Registration Successful",
          message: data.message,
          primaryText: "Go to Sign In",
          onPrimary: function () {
            window.location.href = "/signin";
          }
        });
      } else {
        window.shopShared.showPopup({
          type: "error",
          title: "Registration Failed",
          message: data.message
        });
      }
    })
    .catch(function (error) {
      window.shopShared.showPopup({
        type: "error",
        title: "Error",
        message: "Something went wrong. Please try again."
      });
      console.error("Registration error:", error);
    })
    .finally(function () {
      submitBtn.innerHTML = originalText;
      submitBtn.disabled = false;
    });
  });
});
