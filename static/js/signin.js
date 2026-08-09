document.addEventListener("DOMContentLoaded", function () {
  // Tab switching
  var tabButtons = document.querySelectorAll(".auth-tabs .tab-btn");
  var passwordSection = document.getElementById("passwordSection");
  var forgotSection = document.getElementById("forgotSection");
  var forgotPasswordLink = document.getElementById("forgotPasswordLink");

  // Password Login Form
  var passwordLoginForm = document.getElementById("passwordLoginForm");

  // Forgot Password elements
  var sendForgotOtpBtn = document.getElementById("sendForgotOtp");
  var forgotOtpVerify = document.getElementById("forgotOtpVerify");
  var verifyForgotOtpBtn = document.getElementById("verifyForgotOtp");
  var newPasswordSection = document.getElementById("newPasswordSection");
  var resetPasswordBtn = document.getElementById("resetPassword");
  var resendForgotOtpBtn = document.getElementById("resendForgotOtp");
  var resendTimerSpan = document.getElementById("resendTimer");

  var currentForgotMethod = ""; // 'email' or 'phone'
  var currentForgotValue = "";

  // Tab switching
  tabButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var tab = btn.dataset.tab;
      tabButtons.forEach(function (b) { b.classList.remove("active"); });
      btn.classList.add("active");
      
      if (tab === "password") {
        passwordSection.classList.add("active");
        forgotSection.classList.remove("active");
      } else {
        passwordSection.classList.remove("active");
        forgotSection.classList.add("active");
        resetForgotForm();
      }
    });
  });

  // Forgot Password link - switch to forgot tab
  if (forgotPasswordLink) {
    forgotPasswordLink.addEventListener("click", function (e) {
      e.preventDefault();
      tabButtons.forEach(function (b) { 
        if (b.dataset.tab === "forgot") b.classList.add("active");
        else b.classList.remove("active");
      });
      passwordSection.classList.remove("active");
      forgotSection.classList.add("active");
      resetForgotForm();
    });
  }

  // Password Login
  if (passwordLoginForm) {
    passwordLoginForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var loginInput = document.getElementById("loginEmail").value.trim();
      var password = document.getElementById("loginPassword").value;

      if (!loginInput || !password) {
        window.shopShared.showPopup({
          type: "warn",
          title: "Missing Fields",
          message: "Please enter email/phone and password."
        });
        return;
      }

      // Call the login API
      fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ login: loginInput, password: password })
      })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (data.success) {
          localStorage.setItem("isLoggedIn", "true");
          localStorage.setItem("userName", data.user.name);
          localStorage.setItem("userEmail", data.user.email);
          window.shopShared.showToast("Login successful!");
          
          // Check for redirect URL (next parameter)
          var urlParams = new URLSearchParams(window.location.search);
          var nextUrl = urlParams.get("next") || "/account";
          
          setTimeout(function () {
            window.location.href = nextUrl;
          }, 500);
        } else {
          window.shopShared.showPopup({
            type: "error",
            title: "Login Failed",
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
        console.error("Login error:", error);
      });
    });
  }

  // Send Forgot Password OTP
  if (sendForgotOtpBtn) {
    sendForgotOtpBtn.addEventListener("click", function () {
      var input = document.getElementById("forgotInput").value.trim();
      
      if (!input) {
        window.shopShared.showPopup({
          type: "warn",
          title: "Missing Input",
          message: "Please enter your email or phone number."
        });
        return;
      }

      currentForgotMethod = "email";
      currentForgotValue = input;

      // Validate based on method
      if (!input.includes("@")) {
        window.shopShared.showPopup({
          type: "warn",
          title: "Invalid Email",
          message: "Please enter a valid email address."
        });
        return;
      }

      // Show loading
      sendForgotOtpBtn.disabled = true;
      sendForgotOtpBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Sending...';

      // Call API to send OTP
      fetch("/api/forgot_password/send_otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          method: currentForgotMethod, 
          value: input 
        })
      })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (data.success) {
          window.shopShared.showToast("OTP sent to email");
          document.getElementById("forgotEmailWrap").classList.add("hidden");
          forgotOtpVerify.classList.remove("hidden");
          
          startResendTimer();
        } else {
          window.shopShared.showPopup({
            type: "error",
            title: "Failed",
            message: data.message
          });
        }
      })
      .catch(function (error) {
        window.shopShared.showPopup({
          type: "error",
          title: "Error",
          message: "Failed to send OTP. Please try again."
        });
        console.error("Send OTP error:", error);
      })
      .finally(function () {
        sendForgotOtpBtn.disabled = false;
        sendForgotOtpBtn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Send OTP';
      });
    });
  }

  // Verify Forgot Password OTP
  if (verifyForgotOtpBtn) {
    verifyForgotOtpBtn.addEventListener("click", function () {
      var otp = document.getElementById("forgotOtp").value.trim();

      if (!otp || otp.length !== 6) {
        window.shopShared.showPopup({
          type: "warn",
          title: "Invalid OTP",
          message: "Please enter a valid 6-digit OTP."
        });
        return;
      }

      verifyForgotOtpBtn.disabled = true;
      verifyForgotOtpBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Verifying...';

      // Call API to verify OTP
      fetch("/api/forgot_password/verify_otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          method: currentForgotMethod, 
          value: currentForgotValue,
          otp: otp
        })
      })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (data.success) {
          window.shopShared.showToast("OTP verified!");
          document.getElementById("forgotOtpWrap").classList.add("hidden");
          newPasswordSection.classList.remove("hidden");
          verifyForgotOtpBtn.disabled = true;
          verifyForgotOtpBtn.innerHTML = '<i class="fa-solid fa-check"></i> Verified';
        } else {
          window.shopShared.showPopup({
            type: "error",
            title: "Invalid OTP",
            message: data.message
          });
        }
      })
      .catch(function (error) {
        window.shopShared.showPopup({
          type: "error",
          title: "Error",
          message: "Failed to verify OTP. Please try again."
        });
        console.error("Verify OTP error:", error);
      })
      .finally(function () {
        if (!newPasswordSection.classList.contains("hidden")) {
          // Already verified, don't re-enable
        } else {
          verifyForgotOtpBtn.disabled = false;
          verifyForgotOtpBtn.innerHTML = '<i class="fa-solid fa-check-circle"></i> Verify OTP';
        }
      });
    });
  }

  // Reset Password
  if (resetPasswordBtn) {
    resetPasswordBtn.addEventListener("click", function () {
      var newPass = document.getElementById("newPassword").value;
      var confirmPass = document.getElementById("confirmNewPassword").value;

      if (!newPass || !confirmPass) {
        window.shopShared.showPopup({
          type: "warn",
          title: "Missing Fields",
          message: "Please enter and confirm your new password."
        });
        return;
      }

      if (newPass.length < 6) {
        window.shopShared.showPopup({
          type: "warn",
          title: "Weak Password",
          message: "Password must be at least 6 characters."
        });
        return;
      }

      if (newPass !== confirmPass) {
        window.shopShared.showPopup({
          type: "warn",
          title: "Password Mismatch",
          message: "New password and confirm password do not match."
        });
        return;
      }

      resetPasswordBtn.disabled = true;
      resetPasswordBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Resetting...';

      // Call API to reset password
      fetch("/api/forgot_password/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          method: currentForgotMethod, 
          value: currentForgotValue,
          newPassword: newPass
        })
      })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (data.success) {
          window.shopShared.showToast("Your password has been reset. Please sign in.");
          document.querySelector(".tab-btn[data-tab='password']").click();
        } else {
          window.shopShared.showPopup({
            type: "error",
            title: "Failed",
            message: data.message
          });
        }
      })
      .catch(function (error) {
        window.shopShared.showPopup({
          type: "error",
          title: "Error",
          message: "Failed to reset password. Please try again."
        });
        console.error("Reset password error:", error);
      })
      .finally(function () {
        resetPasswordBtn.disabled = false;
        resetPasswordBtn.innerHTML = '<i class="fa-solid fa-save"></i> Reset Password';
      });
    });
  }

  // Resend OTP
  if (resendForgotOtpBtn) {
    resendForgotOtpBtn.addEventListener("click", function () {
      if (resendForgotOtpBtn.disabled) return;
      resendForgotOtpBtn.disabled = true;

      // Call API to resend OTP
      fetch("/api/forgot_password/send_otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          method: currentForgotMethod, 
          value: currentForgotValue 
        })
      })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (data.success) {
          window.shopShared.showToast("OTP resent to email");
          startResendTimer();
        } else {
          window.shopShared.showPopup({
            type: "error",
            title: "Failed",
            message: data.message
          });
          resendForgotOtpBtn.disabled = false;
        }
      })
      .catch(function (error) {
        console.error("Resend OTP error:", error);
        resendForgotOtpBtn.disabled = false;
      });
    });
  }

  // Resend timer
  function startResendTimer() {
    var countdown = 60;
    resendForgotOtpBtn.disabled = true;
    resendTimerSpan.textContent = "(" + countdown + "s)";
    
    var timer = setInterval(function () {
      countdown--;
      resendTimerSpan.textContent = "(" + countdown + "s)";
      if (countdown <= 0) {
        clearInterval(timer);
        resendForgotOtpBtn.disabled = false;
        resendTimerSpan.textContent = "";
      }
    }, 1000);
  }

  // Reset forgot form
  function resetForgotForm() {
    document.getElementById("forgotInput").value = "";
    document.getElementById("forgotOtp").value = "";
    document.getElementById("newPassword").value = "";
    document.getElementById("confirmNewPassword").value = "";
    document.getElementById("forgotEmailWrap").classList.remove("hidden");
    document.getElementById("forgotOtpWrap").classList.remove("hidden");
    forgotOtpVerify.classList.add("hidden");
    newPasswordSection.classList.add("hidden");
    currentForgotMethod = "";
    currentForgotValue = "";
  }
});

