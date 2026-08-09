(function () {
  var chatBody = document.getElementById("chatBody");
  var chatForm = document.getElementById("chatForm");
  var chatInput = document.getElementById("chatInput");
  var clearBtn = document.getElementById("clearChat");
  var shared = window.shopShared || {};
  var isVoiceEnabled = false;
  var recognition = null;

  // Initialize Speech Recognition
  if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
    var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US"; // Model is multilingual, but UI defaults to system lang

    recognition.onresult = function(event) {
      var transcript = event.results[0][0].transcript;
      sendMessage(transcript);
      document.getElementById("voiceBtn").classList.remove("recording");
    };

    recognition.onerror = function() {
      document.getElementById("voiceBtn").classList.remove("recording");
    };

    recognition.onend = function() {
      document.getElementById("voiceBtn").classList.remove("recording");
    };
  }

  // Session ID Management for persistent multi-turn conversational memory
  function getChatSessionId() {
    var sid = localStorage.getItem("buyMore_chatbot_session");
    if (!sid) {
      sid = "sess_" + Math.random().toString(36).substring(2, 10) + "_" + Date.now();
      localStorage.setItem("buyMore_chatbot_session", sid);
    }
    return sid;
  }

  function scrollChatToBottom() {
    chatBody.scrollTop = chatBody.scrollHeight;
  }

  function speakText(text) {
    if (!isVoiceEnabled || !window.speechSynthesis) return;
    window.speechSynthesis.cancel(); // Stop current speaking
    var utterance = new SpeechSynthesisUtterance(text);
    window.speechSynthesis.speak(utterance);
  }

  function createMessageShell(role) {
    var msg = document.createElement("div");
    msg.className = "chat-msg " + role;
    chatBody.appendChild(msg);
    return msg;
  }

  function addTextMessage(text, role) {
    var msg = createMessageShell(role);
    msg.textContent = text;
    scrollChatToBottom();
    return msg;
  }

  function addBotPayload(payload) {
    var msg = createMessageShell("bot");

    var text = document.createElement("p");
    text.className = "chat-text";
    
    var reply = (payload && payload.reply) || "Sorry, I could not generate a reply.";
    text.textContent = "BuyMore: " + reply;
    msg.appendChild(text);

    // Speak the reply if voice is enabled
    speakText(reply);

    if (payload && Array.isArray(payload.suggestions) && payload.suggestions.length) {
      var suggestionRow = document.createElement("div");
      suggestionRow.className = "chat-suggestions";

      payload.suggestions.slice(0, 5).forEach(function (suggestion) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "chat-suggestion";
        button.textContent = suggestion;
        button.addEventListener("click", function () {
          if (suggestion === "Speak to a human agent") {
            escalateSession();
          } else if (suggestion === "Go to checkout") {
            window.location.href = "/checkout";
          } else {
            sendMessage(suggestion);
          }
        });
        suggestionRow.appendChild(button);
      });

      msg.appendChild(suggestionRow);
    }

    if (payload && Array.isArray(payload.products) && payload.products.length) {
      var productGrid = document.createElement("div");
      productGrid.className = "chat-product-grid";
      productGrid.innerHTML = payload.products.slice(0, 4).map(function (product) {
        return shared.buildProductCardMarkup ? shared.buildProductCardMarkup(product) : "";
      }).join("");
      msg.appendChild(productGrid);
    }

    scrollChatToBottom();

    if (shared.bindAddToCartButtons) {
      shared.bindAddToCartButtons();
    }
    if (shared.bindAddToWishlistButtons) {
      shared.bindAddToWishlistButtons();
    }
    if (shared.bindProductCards) {
      shared.bindProductCards();
    }
  }

  function addBotGreeting() {
    addBotPayload({
      reply: "Hi there! I'm BuyMore, your personal shopping assistant. I'm here to help you find products, track orders, or answer any questions about our store. How can I help you today?",
      suggestions: ["Show trending products", "Track my order", "How do returns work?"]
    });
  }

  function addTypingState() {
    var msg = createMessageShell("bot typing");
    msg.textContent = "BuyMore is looking into that for you...";
    scrollChatToBottom();
    return msg;
  }

  function removeNode(node) {
    if (node && node.parentNode) {
      node.parentNode.removeChild(node);
    }
  }

  function escalateSession() {
    var typingNode = addTypingState();
    fetch("/api/escalate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ 
        session_id: getChatSessionId(),
        message: "User clicked 'Speak to a human agent'"
      })
    })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        removeNode(typingNode);
        if (data && data.success) {
          addBotPayload(data);
        }
      })
      .catch(function() {
        removeNode(typingNode);
      });
  }

  function sendMessage(text) {
    var value = String(text || "").trim();
    if (!value) {
      return;
    }

    addTextMessage("You: " + value, "user");
    chatInput.value = "";

    var typingNode = addTypingState();

    fetch("/api/support/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ 
        message: value,
        session_id: getChatSessionId() 
      })
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        removeNode(typingNode);
        if (data && data.success) {
          addBotPayload(data);
        } else {
          addBotPayload({
            reply: "Sorry, I am having trouble connecting to the intelligence engine.",
            suggestions: ["Show trending products", "Payment options", "How do returns work?"]
          });
        }
      })
      .catch(function (err) {
        console.error("[SupportChat] Network or Server Error:", err);
        removeNode(typingNode);
        addBotPayload({
          reply: "Sorry, I could not reach the server. Please check your connection or try again in a few moments.",
          suggestions: ["Try rephrasing", "Support hours"]
        });
      });
  }

  chatForm.addEventListener("submit", function (event) {
    event.preventDefault();
    sendMessage(chatInput.value);
  });

  clearBtn.addEventListener("click", function () {
    chatBody.innerHTML = "";
    // Regenerate session ID on clear to start a fresh context
    var sid = "sess_" + Math.random().toString(36).substring(2, 10) + "_" + Date.now();
    localStorage.setItem("buyMore_chatbot_session", sid);
    addBotGreeting();
  });

  document.querySelectorAll("[data-quick]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      sendMessage(btn.getAttribute("data-quick"));
    });
  });

  // Voice UI Bindings
  var voiceBtn = document.getElementById("voiceBtn");
  var speakToggle = document.getElementById("speakToggle");

  if (voiceBtn && recognition) {
    voiceBtn.addEventListener("click", function() {
      voiceBtn.classList.add("recording");
      recognition.start();
    });
  }

  if (speakToggle) {
    speakToggle.addEventListener("click", function() {
      isVoiceEnabled = !isVoiceEnabled;
      speakToggle.textContent = isVoiceEnabled ? "🔊" : "🔇";
      speakToggle.classList.toggle("active", isVoiceEnabled);
      if (!isVoiceEnabled && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    });
  }

  addBotGreeting();
})();
