let adminEmail = '';

async function handleLogin() {
    const email = document.getElementById('email').value;
    const btn = document.getElementById('login-btn');
    const error = document.getElementById('error-msg');

    if (!email) return error.innerText = 'Email Required';

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-circle-notch animate-spin mr-2"></i> Processing...';
    error.innerText = '';

    try {
        const res = await fetch('/admin/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        
        // Inspect response type
        const contentType = res.headers.get('content-type');
        if (!res.ok || !contentType || !contentType.includes('application/json')) {
            const errorText = !res.ok ? `Server Error (${res.status})` : 'Invalid Server Response';
            throw new Error(errorText);
        }

        const data = await res.json();

        if (data.success) {
            adminEmail = email;
            document.getElementById('login-step').classList.add('hidden');
            document.getElementById('otp-step').classList.remove('hidden');
            document.getElementById('step-desc').innerText = 'Security Code Dispatched';
            document.getElementById('step-desc').classList.replace('text-teal-600', 'text-amber-600');
        } else {
            error.innerText = data.message || 'Authorization Denied';
        }
    } catch (e) {
        console.error('Login Failure:', e);
        error.innerText = e.message.includes('Server Error') ? e.message : 'Network Connection Failure';
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>Request Access Code</span><i class="fas fa-arrow-right text-xs opacity-50 group-hover:translate-x-1 transition-transform"></i>';
    }
}

async function handleVerify() {
    const otp = document.getElementById('otp').value;
    const btn = document.getElementById('verify-btn');
    const error = document.getElementById('error-msg');

    if (otp.length !== 6) return error.innerText = 'Invalid Key Format';

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-circle-notch animate-spin mr-2"></i> Authenticating...';
    error.innerText = '';

    try {
        const res = await fetch('/admin/api/verify-otp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: adminEmail, otp })
        });
        const data = await res.json();

        if (data.success) {
            window.location.href = '/admin/';
        } else {
            error.innerText = data.message;
        }
    } catch (e) {
        error.innerText = 'Authorization Failure';
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>Secure Authorization</span>';
    }
}

function resendLogin() {
    document.getElementById('login-step').classList.remove('hidden');
    document.getElementById('otp-step').classList.add('hidden');
    document.getElementById('step-desc').innerText = 'Administrator Auth';
    document.getElementById('step-desc').classList.replace('text-amber-600', 'text-teal-600');
    document.getElementById('error-msg').innerText = '';
}
